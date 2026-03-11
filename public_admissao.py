"""
Formulário público de admissão (apenas o fluxo do candidato).
- Gera pasta e documentos no Drive a partir dos modelos
- Preenche a planilha Base_de_Dados_Funcionarios
- Exporta PDFs e entrega ZIP para upload manual ao D4Sign
Variáveis lidas de env:
  GEMINI_API_KEY (opcional, não usada aqui)
  D4SIGN_TOKEN, D4SIGN_CRYPT, D4SIGN_COFRE (usadas só se quiser automatizar depois)
"""
import os
import io
import json
import zipfile
import time
from datetime import datetime, date, timedelta

import gspread
import requests
import streamlit as st
import google.generativeai as genai
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import base64

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
API_KEY_GEMINI = os.getenv("GEMINI_API_KEY", "")
if not API_KEY_GEMINI:
    try:
        API_KEY_GEMINI = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

ZAPSIGN_TOKEN = os.getenv("ZAPSIGN_TOKEN", "")
if not ZAPSIGN_TOKEN:
    try:
        ZAPSIGN_TOKEN = st.secrets.get("ZAPSIGN_TOKEN", "")
    except Exception:
        pass
DATA_INICIO_PADRAO = os.getenv("DATA_INICIO_PADRAO", datetime.now().strftime('%d/%m/%Y'))

ID_PASTA_RAIZ = "1_w4HGrBnylar-vkiQTDT6ozW8KiGITZs"
ID_PLANILHA = "1-VH1zGyTeEfJnvBhnq6ZlkyGF-G--FKXTwGHfrCvfRE"
ID_MODELO_HOLERITE = "1PwSXH2NOxxPer4MOchV9zfpeyyemIrULas7J8c1jTrk"
MODELOS_ADMISSAO = {
    "01. Contrato de Trabalho": "1877g_glh9TZ5DFRrUpVPQD_R-s099tFVCljREUlPZs0",
    "02. Ficha de EPI": "18U92SoGwqDKalMRnkVay-pfo0QVOG-1ZF0nHiaRcFhk",
    "03. Acordo Compensação": "1DMfVczX6oqxZVYbGRdCEC5EiospyEUcBuJh5dwaCTfI",
    "04. Acordo Prorrogação": "1XuOQ1Z9MIeotWrbYnsH7XoSCzc24_FJ6MtYt9f3L0eA",
}

# ------------------------------------------------------------
# Infra Google
# ------------------------------------------------------------

def conectar_google():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents'
    ]
    
    # Garantir que ele procure as chaves na mesma pasta onde este script (public_admissao.py) está salvo
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    token_pickle = os.path.join(BASE_DIR, 'token.json')
    client_secret_json = os.path.join(BASE_DIR, 'client_secret.json')
    service_acc_json = os.path.join(BASE_DIR, 'service_account.json')
    
    # Estratégia de Deploy Nuvem: Cria os arquivos JSON físicos no servidor a partir dos Secrets
    if not os.path.exists(token_pickle) and "GOOGLE_TOKEN_JSON" in st.secrets:
        with open(token_pickle, "w") as f:
            f.write(st.secrets["GOOGLE_TOKEN_JSON"])
    
    if not os.path.exists(client_secret_json) and "GOOGLE_CLIENT_SECRET" in st.secrets:
        with open(client_secret_json, "w") as f:
            f.write(st.secrets["GOOGLE_CLIENT_SECRET"])

    creds = None
    if os.path.exists(token_pickle):
        creds = Credentials.from_authorized_user_file(token_pickle, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_json, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_pickle, 'w') as token:
            token.write(creds.to_json())
            
    # O gspread autentica com o service_account separado (conforme código anterior vindo do app.py, se existir)
    # se não, mantemos original. O erro foi no client_secret.
    gc = gspread.authorize(creds)
    return build('drive', 'v3', credentials=creds), build('docs', 'v1', credentials=creds), gc

# ------------------------------------------------------------
# Geração de kit e exportação
# ------------------------------------------------------------
def processar_documentos_ia(arquivos_upload):
    if not API_KEY_GEMINI:
        raise ValueError("Chave de API do Gemini não configurada. Defina GEMINI_API_KEY nas variáveis de ambiente ou no arquivo .streamlit/secrets.toml.")
    genai.configure(api_key=API_KEY_GEMINI)
    modelo = genai.GenerativeModel('gemini-2.5-flash', generation_config={"response_mime_type": "application/json"})
    arquivos_ia = []
    status_bar = st.progress(0, text="Enviando arquivos para a IA...")
    for i, arq in enumerate(arquivos_upload):
        with open(f"temp_{arq.name}", "wb") as f: f.write(arq.getbuffer())   
        arquivo_up = genai.upload_file(path=f"temp_{arq.name}")
        while arquivo_up.state.name == "PROCESSING": time.sleep(10); arquivo_up = genai.get_file(arquivo_up.name)
        arquivos_ia.append(arquivo_up); os.remove(f"temp_{arq.name}")
        status_bar.progress((i + 1) / len(arquivos_upload), text=f"Lendo: {arq.name}")

    prompt = """Você é um sistema automatizado de RH. Sua única função é extrair dados dos documentos fornecidos e preencher o template JSON abaixo.
Os documentos podem incluir CNH, RG, CRNM de estrangeiros CTPS, Comprovante de Endereço, Título de Eleitor, Certificado de Reservista e Certidões (Nascimento/Casamento).
REGRAS:
1. "Nome Completo", "CPF", "RG", "Data de Nascimento": CNH, RG ou CRNM.
2. "Nome da Mae" e "Nome do Pai": CNH, RG, CRNM ou Certidão.
3. Endereço: Comprovante de residência. Ignore o endereço da empresa emissora (ex: Sabesp) e extraia O ENDEREÇO DO CONSUMIDOR. Tente desmembrar em Logradouro, Número, Bairro, Cidade e CEP. Se houver mais de um comprovante, escolha o mais recente.
4. "CTPS Numero": Se CTPS Digital, use o CPF. Deixe Série e UF vazios.
5. "Orgao Emissor RG" e "UF RG": Separe as letras do Estado (ex: SSP e SP). Para estrangeiros, deixe vazio.
6. "Titulo de Eleitor", "Zona", "Secao": Título de Eleitor.
7. "Reservista": Certificado militar.
8. "Estado Civil": Siga a regra documental rigorosamente:
  - Se o documento apresentado for uma "Certidão de Nascimento" (e não houver averbação de casamento), preencha "SOLTEIRO(A)".
  - Se o documento for uma "Certidão de Casamento", preencha "CASADO(A)"
9. "Validacao Vacina Antitetanica": Verifique a Carteira de Vacinação. Se ela contiver de forma clara o nome do titular (condizente com o Nome Completo extraído dos outros documentos) E nela constar o registro claro da vacina "Antitetânica" (ou Dupla Adulto / dT), preencha estritamente com a palavra "OK". Caso contrário, descreva o problema, exemplo: "Nome do titular não identificado na carteira" ou "Falta registro da vacina Antitetânica".

    JSON ESPERADO:
    {
      "Nome Completo": "", "Data de Nascimento": "", "Local de Nascimento": "", "Estado Civil": "",
      "CPF": "", "RG": "", "Orgao Emissor RG": "", "UF RG": "", "Nome da Mae": "", "Nome do Pai": "",
      "CEP": "", "Logradouro": "", "Numero Endereco": "", "Complemento": "", "Bairro": "",
      "Cidade": "", "Estado": "", "PIS": "", "CTPS Numero": "", "CTPS Serie": "", "CTPS UF": "",
      "Titulo de Eleitor": "", "Zona": "", "Secao": "", "Reservista": "", "Validacao Vacina Antitetanica": ""
    }
    """
    res = modelo.generate_content([prompt] + arquivos_ia, request_options={"timeout": 600})
    return json.loads(res.text)

def gerar_kit_admissional(dados_finais):
    drive_service, docs_service, gc = conectar_google()
    salario_raw = dados_finais.get('salario', '0,00')
    try: 
        from num2words import num2words
        sal_extenso = num2words(float(salario_raw.replace('.','').replace(',','.')), lang='pt_BR', to='currency')
    except Exception: 
        sal_extenso = "Valor não identificado"
    
    try:
        dt_inicio = datetime.strptime(dados_finais.get('data_inicio', datetime.now().strftime('%d/%m/%Y')), '%d/%m/%Y')
    except Exception:
        dt_inicio = datetime.now()
    dt_fim_30 = dt_inicio + timedelta(days=29) # Termina no 30º dia
    dt_fim_90 = dt_inicio + timedelta(days=89) # Termina no 90º dia (30 + 60)
    
    tags = {
        '{{NOME}}': dados_finais.get('nome', '').upper(),
        '{{NACIONALIDADE}}': dados_finais.get('nacionalidade', 'Brasileiro').upper(),
        '{{ESTADO_CIVIL}}': dados_finais.get('estado_civil', dados_finais.get('Estado Civil', 'Solteiro(a)')).upper(),
        '{{PROFISSAO}}': dados_finais.get('cargo', ''),
        '{{RG}}': dados_finais.get('rg', dados_finais.get('RG', '')),
        '{{CPF}}': dados_finais.get('cpf', dados_finais.get('CPF', '')),
        '{{PIS}}': dados_finais.get('pis', dados_finais.get('PIS', '')),
        '{{ENDERECO_COMPLETO}}': f"{dados_finais.get('Logradouro', dados_finais.get('logradouro', ''))} {dados_finais.get('Numero Endereco', dados_finais.get('numero', ''))}, {dados_finais.get('Bairro', dados_finais.get('bairro', ''))}, {dados_finais.get('Cidade', dados_finais.get('cidade', ''))}-{dados_finais.get('Estado', dados_finais.get('estado', ''))}",
        '{{CTPS_NUM}}': dados_finais.get('CTPS Numero', dados_finais.get('ctps_num', '')),
        '{{CTPS_SERIE}}': dados_finais.get('CTPS Serie', dados_finais.get('ctps_serie', '')),
        '{{FUNCAO}}': dados_finais.get('cargo', ''),
        '{{SALARIO}}': dados_finais.get('salario', ''),
        '{{SALARIO_EXTENSO}}': sal_extenso,
        '{{DATA_INICIO}}': dados_finais.get('data_inicio', ''),
        '{{DATA_ADMISSAO}}': dados_finais.get('data_inicio', ''),  # aliases para modelos diferentes
        '{{ADMISSAO_DATA}}': dados_finais.get('data_inicio', ''),
        '{{FIM_45}}': dt_fim_30.strftime('%d/%m/%Y'), # Mantém onome do antigo mas injeta 30 dias
        '{{FIM_90}}': dt_fim_90.strftime('%d/%m/%Y'),
        '{{DATA_HOJE}}': f"São Paulo, {datetime.now().day} de {datetime.now().strftime('%B')} de {datetime.now().year}",
    }

    metadata = {'name': f"Admissão - {tags['{{NOME}}']}", 'mimeType': 'application/vnd.google-apps.folder', 'parents': [ID_PASTA_RAIZ]}
    pasta = drive_service.files().create(body=metadata, fields='id').execute()
    id_pasta = pasta.get('id'); link_pasta = f"https://drive.google.com/drive/folders/{id_pasta}"

    progresso = st.progress(0); contador = 0
    for nome_doc, id_modelo in MODELOS_ADMISSAO.items():
        copia = drive_service.files().copy(fileId=id_modelo, body={'name': f"{nome_doc} - {tags['{{NOME}}']}", 'parents': [id_pasta]}).execute()
        reqs = [{'replaceAllText': {'containsText': {'text': k, 'matchCase': True}, 'replaceText': str(v)}} for k, v in tags.items()]
        docs_service.documents().batchUpdate(documentId=copia.get('id'), body={'requests': reqs}).execute()
        contador += 1; progresso.progress(contador / len(MODELOS_ADMISSAO))

    aba = gc.open_by_key(ID_PLANILHA).worksheet('Base_de_Dados_Funcionarios')
    col_mat = aba.col_values(1)
    maior = 0
    for v in col_mat[1:]:
        if v.isdigit() and int(v) > maior: maior = int(v)
    nova_mat = f"{(maior + 1):06d}"

    linha = [""] * 65
    linha[0] = nova_mat; linha[1] = nova_mat; linha[2] = tags['{{NOME}}']
    linha[3] = dados_finais.get('Data de Nascimento', dados_finais.get('nascimento', ''))
    linha[4] = tags['{{NACIONALIDADE}}']
    linha[5] = dados_finais.get('Local de Nascimento', dados_finais.get('local_nasc', ''))
    linha[6] = tags['{{ESTADO_CIVIL}}']
    linha[7] = dados_finais.get('raca', '')
    linha[8] = tags['{{RG}}']
    linha[9] = dados_finais.get('Data Expedicao RG', dados_finais.get('data_rg', ''))
    linha[10] = dados_finais.get('Orgao Emissor RG', dados_finais.get('orgao_rg', ''))
    linha[11] = dados_finais.get('UF RG', dados_finais.get('uf_rg', ''))
    linha[12] = tags['{{CPF}}']
    linha[13] = tags['{{PIS}}']
    linha[14] = tags['{{CTPS_NUM}}']
    linha[15] = tags['{{CTPS_SERIE}}']
    linha[16] = dados_finais.get('CTPS UF', dados_finais.get('ctps_uf', ''))
    linha[17] = dados_finais.get('CTPS Data', '')
    linha[18] = dados_finais.get('Titulo de Eleitor', dados_finais.get('titulo', ''))
    linha[19] = dados_finais.get('Zona', dados_finais.get('zona', ''))
    linha[20] = dados_finais.get('Secao', dados_finais.get('secao', ''))
    linha[21] = dados_finais.get('Municipio Titulo', '')
    linha[22] = dados_finais.get('Reservista', dados_finais.get('reservista', ''))
    linha[23] = dados_finais.get('Nome da Mae', dados_finais.get('mae', ''))
    linha[24] = dados_finais.get('Nome do Pai', dados_finais.get('pai', ''))
    linha[25] = dados_finais.get('Logradouro', dados_finais.get('logradouro', ''))
    linha[26] = dados_finais.get('Numero Endereco', dados_finais.get('numero', ''))
    linha[27] = dados_finais.get('Complemento', dados_finais.get('complemento', ''))
    linha[28] = dados_finais.get('Bairro', dados_finais.get('bairro', ''))
    linha[29] = dados_finais.get('Cidade', dados_finais.get('cidade', ''))
    linha[30] = dados_finais.get('Estado', dados_finais.get('estado', ''))
    linha[31] = dados_finais.get('CEP', dados_finais.get('cep', ''))
    linha[32] = dados_finais.get('telefone', '')
    linha[33] = dados_finais.get('celular', '')
    linha[34] = dados_finais.get('email', '')
    linha[35] = dados_finais.get('escolaridade', '')
    linha[36] = dados_finais.get('curso', '')
    linha[37] = dados_finais.get('conjuge', '')
    linha[38] = dados_finais.get('conjuge_cpf', '')
    linha[39] = dados_finais.get('conjuge_dt', '')
    linha[40] = dados_finais.get('dep1_nome', '')
    linha[41] = dados_finais.get('dep1_dt', '')
    linha[42] = dados_finais.get('dep1_parent', '')
    linha[43] = dados_finais.get('dep2_nome', '')
    linha[44] = dados_finais.get('dep2_dt', '')
    linha[45] = dados_finais.get('dep2_parent', '')
    linha[46] = dados_finais.get('banco', '')
    linha[47] = dados_finais.get('agencia', '')
    linha[48] = dados_finais.get('conta', '')
    linha[49] = dados_finais.get('tipo_conta', '')
    linha[50] = dados_finais.get('vt_optin', '')
    linha[51] = f"{dados_finais.get('linha_ida', '')} / {dados_finais.get('linha_volta', '')}".strip(" /")
    linha[52] = dados_finais.get('vt_diario', '0,00')
    linha[53] = dados_finais.get('plano_saude', '')
    linha[54] = tags['{{DATA_INICIO}}']
    linha[55] = tags['{{FUNCAO}}']
    linha[56] = dados_finais.get('cbo', '')
    linha[57] = tags['{{SALARIO}}']
    linha[58] = dados_finais.get('va', '')
    linha[59] = dados_finais.get('vr', '')
    linha[60] = link_pasta
    linha[61] = ''
    linha[62] = 'ATIVO'
    linha[63] = ''
    linha[64] = dados_finais.get('obra', '')
    aba.append_row(linha)

    return link_pasta, id_pasta


def exportar_pdfs_da_pasta(folder_id: str):
    drive_service, _, _ = conectar_google()
    res = drive_service.files().list(q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'", fields="files(id, name)").execute()
    pdfs = []
    for f in res.get('files', []):
        request = drive_service.files().export_media(fileId=f['id'], mimeType='application/pdf')
        pdf_bytes = request.execute()
        pdfs.append((f"{f['name']}.pdf", pdf_bytes))
    return pdfs


def salvar_uploads_na_pasta(folder_id: str, uploads: dict):
    drive_service, _, _ = conectar_google()
    for key, file in uploads.items():
        if file is None:
            continue
        mimetype = getattr(file, "type", None) or "application/octet-stream"
        media_body = MediaIoBaseUpload(io.BytesIO(file.getbuffer()), mimetype=mimetype, resumable=False)
        drive_service.files().create(body={'name': file.name, 'parents': [folder_id]}, media_body=media_body, fields='id').execute()


def preparar_pacote_para_d4sign(pdfs):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in pdfs:
            zf.writestr(nome, conteudo)
    buf.seek(0)
    return buf.getvalue()

def enviar_documento_zapsign(arquivo_pdf_bytes, nome_arquivo, email_funcionario, cpf_funcionario, celular_funcionario, nome_funcionario):
    """
    Envia um arquivo em bytes para a ZapSign e dispara para o WhatsApp e E-mail do funcionário com assinatura ancorada.
    """
    import base64
    import traceback
    
    if not nome_arquivo.lower().endswith('.pdf'):
        nome_arquivo += '.pdf'

    url_upload = f"https://api.zapsign.com.br/api/v1/docs/?api_token={ZAPSIGN_TOKEN}"
    
    try:
        base64_pdf = base64.b64encode(arquivo_pdf_bytes).decode('utf-8')
        
        # Formatar celular para extrair apenas numeros
        celular_str = str(celular_funcionario)
        celular = "".join(filter(str.isdigit, celular_str))
        if len(celular) == 11 or len(celular) == 10:
            country_code = "55"
            number = celular
        elif len(celular) >= 12:
            country_code = str(celular[:2])
            number = str(celular[2:])
        else:
            country_code = "55"
            number = ""

        payload = {
            "name": nome_arquivo,
            "base64_pdf": base64_pdf,
            "sandbox": False, # Produção Real: Sem marca d'água e com Validade Jurídica
            "signers": [
                {
                    "name": nome_funcionario,
                    "email": email_funcionario,
                    "auth_mode": "tokenWhatsapp", # Autenticação via WhatsApp
                    "send_automatic_email": True,
                    "send_automatic_whatsapp": True, # Ativa envio direto pro Whatsapp
                    "phone_country": country_code,
                    "phone_number": number,
                    "signature_placement": "<<assinatura_funcionario>>" # Âncora no template PDF
                },
                {
                    "name": "RH Vicelos",
                    "email": "contato@viceloseng.com.br",
                    "auth_mode": "assinaturaTela", # Assinatura simples para a empresa
                    "send_automatic_email": True,
                    "send_automatic_whatsapp": False,
                    "signature_placement": "<<assinatura_empresa>>" # Âncora do RH
                }
            ]
        }
        
        req_up = requests.post(url_upload, json=payload)
        
        if req_up.status_code != 200:
            raise ValueError(f"Status {req_up.status_code}. Retorno ZapSign: {req_up.text}")
            
        uuid_documento = req_up.json().get("token")
        
    except Exception as e:
        raise ValueError(f"Falha gravíssima ao conectar na API ZapSign: {e}\nTrace: {traceback.format_exc()}")
        
    return uuid_documento

# ------------------------------------------------------------
# Formulário público
# ------------------------------------------------------------

def render_public_form():
    st.set_page_config(page_title="Admissão Vicelos", page_icon="🏗️", layout="wide")
    st.title("🏗️ Processo Admissional Vicelos Engenharia")

    if "ia_data" not in st.session_state:
        st.session_state["ia_data"] = {}
    if "em_processamento" not in st.session_state:
        st.session_state["em_processamento"] = False

    REQUIRED_UPLOADS = {
        "Documento de Identidade (RG ou CNH)": "rg_cnh",
        "CPF": "cpf",
        "Comprovante de Endereço": "endereco",
        "Certidão de Nascimento ou Casamento": "certidao",
        "Carteira de Vacinação (com Antitetânica)": "vacinacao"
    }
    OPTIONAL_UPLOADS = {
        "CTPS (frente/verso ou digital)": "ctps",
        "Título de Eleitor": "titulo",
        "Certificado de Reservista (se houver)": "reservista",
    }

    st.subheader("1. Envio de Documentos")
    st.info("Faça o upload dos seus documentos abaixo e clique em 'Extrair Dados' para o preenchimento automático. Após valide os preenchimentos.")
    st.caption("⚠️ Os itens marcados com asterisco (*) são de preenchimento obrigatório.")
    
    uploads = {}
    u1, u2 = st.columns(2)
    with u1:
        for label, key in REQUIRED_UPLOADS.items():
            uploads[key] = st.file_uploader(f"{label} *", type=["pdf", "png", "jpg", "jpeg"], key=f"up_{key}")
    with u2:
        for label, key in OPTIONAL_UPLOADS.items():
            uploads[key] = st.file_uploader(label, type=["pdf", "png", "jpg", "jpeg", "zip"], key=f"up_{key}")

    uploaded_files_list = [f for f in uploads.values() if f is not None]
    if uploaded_files_list:
        if st.button("✨ Extrair Dados com IA"):
            try:
                dados_extraidos = processar_documentos_ia(uploaded_files_list)
                st.session_state["ia_data"] = dados_extraidos
                st.success("Dados extraídos com sucesso! Por favor, revise e complete as informações abaixo.")
            except Exception as e:
                st.error(f"Erro na ponte com a IA: {e}")

    ia = st.session_state["ia_data"]

    st.markdown("---")
    with st.form("form_admissao", clear_on_submit=False):
        st.subheader("2. Revisão de Dados Pessoais")
        c1, c2, c3, c4 = st.columns(4)
        nome = c1.text_input("Nome Completo *", value=ia.get("Nome Completo", ""))
        
        dt_val = None
        if ia.get("Data de Nascimento"):
            try:
                dt_val = datetime.strptime(ia.get("Data de Nascimento"), '%d/%m/%Y').date()
            except:
                pass
        dt_nasc = c2.date_input("Data de Nascimento", min_value=date(1950, 1, 1), max_value=date.today(), format="DD/MM/YYYY", value=dt_val)
        
        nacionalidade = c3.text_input("Nacionalidade", value="BRASILEIRO")
        local_nasc = c4.text_input("Local de Nascimento (Cidade/UF)", value=ia.get("Local de Nascimento", ""))

        c5, c6, c7 = st.columns(3)
        ec_val = ia.get("Estado Civil", "").capitalize()
        ec_options = ["Solteiro(a)", "Casado(a)", "Divorciado(a)", "Viúvo(a)"]
        ec_index = next((i for i, opt in enumerate(ec_options) if ec_val.startswith(opt[:5])), None)
        estado_civil = c5.selectbox("Estado Civil", ec_options, index=ec_index)
        
        raca = c6.selectbox("Raça/Cor", ["Branca", "Parda", "Preta", "Amarela", "Indígena", "Prefiro não informar"], index=None)
        celular = c7.text_input("Celular / Whatsapp *")

        c8, c9, c10 = st.columns(3)
        telefone = c8.text_input("Telefone Fixo")
        email = c9.text_input("E-mail *")
        pis = c10.text_input("PIS *", value=ia.get("PIS", ""), help="O número do PIS pode ser encontrado na sua CTPS digital.")

        st.markdown("---")
        st.subheader("Auditoria de Saúde (IA)")
        validacao_vacina = ia.get("Validacao Vacina Antitetanica", "")
        if validacao_vacina:
            if validacao_vacina.upper() == "OK":
                st.success("✅ **Carteira de Vacinação validada pela IA:** Nome do titular confere e dose da vacina Antitetânica (dT) identificada com sucesso.")
            else:
                st.warning(f"⚠️ **Observação na Carteira de Vacinação detectada pela IA:** {validacao_vacina}. O documento será enviado para análise no RH.")
        else:
            st.info("ℹ️ O upload da Carteira de Vacinação será exigido no fim do formulário. A validação das vacinas obrigatórias será feita manualmente pelo RH caso a foto esteja ilegível.")

        st.markdown("---")
        st.subheader("Formação Acadêmica")
        g1, g2 = st.columns(2)
        escolaridade = g1.selectbox("Escolaridade", ["Ensino Fundamental Incompleto", "Ensino Fundamental Completo", "Ensino Médio Incompleto", "Ensino Médio Completo", "Ensino Superior Incompleto", "Ensino Superior Completo", "Pós-Graduação/Especialização", "Mestrado", "Doutorado"], index=None)
        curso = g2.text_input("Curso (se aplicável)", help="Caso tenha ensino superior ou técnico, informe o nome do curso.")

        st.markdown("---")
        st.subheader("Documentos")
        d1, d2, d3, d4 = st.columns(4)
        rg = d1.text_input("RG *", value=ia.get("RG", ""))
        
        dt_rg = d2.date_input("Data de Expedição RG", min_value=date(1950, 1, 1), max_value=date.today(), format="DD/MM/YYYY", value=None)
        orgao_rg = d3.text_input("Órgão Emissor - UF (RG)", value=ia.get("Orgao Emissor RG", ""))
        uf_rg = d4.text_input("UF (RG)", value=ia.get("UF RG", ""))

        d5, d6, d7 = st.columns(3)
        cpf = d5.text_input("CPF *", value=ia.get("CPF", ""))
        titulo = d6.text_input("Título de Eleitor ", value=ia.get("Titulo de Eleitor", ""))
        zona = d7.text_input("Zona", value=ia.get("Zona", ""))

        d8, d9, d10 = st.columns(3)
        secao = d8.text_input("Seção", value=ia.get("Secao", ""))
        mun_titulo = d9.text_input("Município/UF (Título)")
        reservista = d10.text_input("Reservista ", value=ia.get("Reservista", ""))

        st.caption("Nota: Os dados de CTPS são extraídos automaticamente via CPF (CTPS Digital).")

        st.markdown("---")
        st.subheader("Endereço")
        e1, e2, e3, e4 = st.columns([2, 1, 1, 1])
        logradouro = e1.text_input("Endereço (Rua/Av) *", value=ia.get("Logradouro", ""))
        numero = e2.text_input("Número", value=ia.get("Numero Endereco", ""))
        complemento = e3.text_input("Complemento", value=ia.get("Complemento", ""))
        bairro = e4.text_input("Bairro", value=ia.get("Bairro", ""))
        e5, e6, e7 = st.columns([2, 1, 1])
        cidade = e5.text_input("Cidade", value=ia.get("Cidade", ""))
        uf = e6.text_input("UF", value=ia.get("Estado", ""))
        cep = e7.text_input("CEP", value=ia.get("CEP", ""))

        st.markdown("---")
        st.subheader("Família e Dependentes")
        st.caption("💡 Preencha os dados do cônjuge apenas se tiver certidão de casamento. Dependentes são filhos menores que 14 anos ou com deficiência comprovada.")
        f1, f2, f3 = st.columns(3)
        conjuge = f1.text_input("Nome do Cônjuge")
        conjuge_cpf = f2.text_input("CPF do Cônjuge")
        conjuge_dt = f3.date_input("Data de Nasc. Cônjuge", min_value=date(1950, 1, 1), max_value=date.today(), format="DD/MM/YYYY", value=None)

        dep1, dep2, dep3 = st.columns(3)
        dep1_nome = dep1.text_input("Dependente 1 Nome")
        dep1_dt = dep2.date_input("Dependente 1 Data Nasc", min_value=date(1950, 1, 1), max_value=date.today(), format="DD/MM/YYYY", value=None)
        dep1_parent = dep3.text_input("Dependente 1 Parentesco")

        st.markdown("---")
        st.subheader("Dados Bancários")
        st.caption("Preencha apenas quando a sua conta no Banco Inter estiver aberta ou caso já possua conta.")
        b1, b2, b3 = st.columns(3)
        banco = b1.text_input("Banco *", value="077", disabled=True)
        agencia = b2.text_input("Agência *", value="0001", disabled=True)
        conta = b3.text_input("Conta *")
        b3.caption("Apenas dígitos (sem pontos ou traços)")

        st.markdown("---")
        st.subheader("Transporte")
        st.caption("⚖️ Até 6% de desconto em folha conforme Lei 7.418/85.")
        vt_optin = st.radio("Deseja receber Vale Transporte? *", ["Sim", "Não"], horizontal=True, index=None)
        i1, i2 = st.columns(2)
        linha_ida = i1.text_input("Linha de Transporte (Ida)")
        valor_ida = i2.text_input("Valor da Passagem (Ida)")
        v1, v2 = st.columns(2)
        linha_volta = v1.text_input("Linha de Transporte (Volta)")
        valor_volta = v2.text_input("Valor da Passagem (Volta)")



        st.markdown("---")
        st.subheader("Finalização")
        
        # LGPD Expander
        with st.expander("📝 Termo de Consentimento para Tratamento de Dados Pessoais (LGPD)", expanded=False):
            st.markdown(f"""
            Este documento registra a sua manifestação livre, informada e inequívoca para o tratamento de seus dados pessoais pela **VICELOS ENGENHARIA E CONSTRUÇÃO LTDA**, em conformidade com a Lei nº 13.709 (LGPD).

            **1. Identificação das Partes**
            * **Controlador:** VICELOS ENGENHARIA E CONSTRUÇÃO LTDA (CNPJ: 37.742.513/0001-88)
            * **Titular:** {nome if nome else '[NOME DO TITULAR]'} (CPF: {cpf if cpf else '[CPF DO TITULAR]'})

            **2. Dados Coletados**
            Você autoriza a Vicelos a realizar o tratamento (coleta, armazenamento e utilização) dos seguintes dados e documentos:
            * Nome completo, data de nascimento e estado civil;
            * RG, CPF, CNH e PIS (números e imagens);
            * Fotografia 3x4;
            * Endereço completo e nível de escolaridade;
            * Dados de contato (Telefone, WhatsApp e E-mail);
            * Dados bancários para fins de pagamento.

            **3. Finalidade do Tratamento**
            Seus dados serão utilizados exclusivamente para:
            * Viabilizar o processo de admissão e registro profissional;
            * Cumprimento de obrigações trabalhistas, previdenciárias e fiscais (eSocial);
            * Gestão de benefícios (saúde, transporte, etc.);
            * Comunicação direta entre a empresa e o colaborador.

            **4. Segurança e Confidencialidade**
            A Vicelos compromete-se a manter seus dados em ambiente seguro e utilizá-los apenas para os fins descritos. Seus dados poderão ser mantidos após o fim do contrato para cumprimento de obrigações legais.

            **5. Seus Direitos**
            Você poderá, a qualquer momento, solicitar informações sobre o tratamento de seus dados ou revogar este consentimento, ciente de que isso poderá impactar a manutenção do vínculo contratual.

            ---
            *Ao marcar a caixa de seleção abaixo, você declara estar ciente e de acordo com os termos acima, confirmando este registro como sua assinatura digital para o acordo.*
            """)
        
        declaracao = st.checkbox("Li e concordo com os termos descritos acima, declaro que as informações são verdadeiras e autorizo o tratamento de dados para admissão (LGPD).")
        submitted = st.form_submit_button("Extrair dados e gerar Contrato")

    if submitted:
        if st.session_state["em_processamento"]:
            st.warning("⏳ O aplicativo já está gerando seus arquivos. O botão de enviar será bloqueado nesta tela para impedir duplicação de contratos por múltiplos cliques.")
            return

        missing_files = [lbl for lbl, k in REQUIRED_UPLOADS.items() if uploads.get(k) is None]
        if not nome or not cpf or not email or not pis or not celular or not rg or not logradouro or not bairro or not cidade or not numero or not cep or vt_optin is None:
            st.error("🚨 Preencha os campos obrigatórios básicos.")
            return
        if missing_files:
            st.error(f"🚨 Anexe os documentos obrigatórios: {', '.join(missing_files)}")
            return
        if not declaracao:
            st.error("🚨 Marque a declaração de veracidade.")
            return
            
        st.session_state["em_processamento"] = True

        # Calcula VT diário somando ida+volta se forem números
        def _to_float(val):
            try:
                return float(str(val).replace('R$', '').replace('.', '').replace(',', '.'))
            except Exception:
                return 0.0

        vt_valor = _to_float(valor_ida) + _to_float(valor_volta)
        vt_valor_str = f"{vt_valor:.2f}".replace('.', ',') if vt_valor > 0 else (valor_ida or "0,00")

        # Valores implícitos (empresa)
        cargo = os.getenv("CARGO_PADRAO", "Pintor de Obras")
        cbo = os.getenv("CBO_PADRAO", "7166-10")
        salario_base = os.getenv("SALARIO_PADRAO", "2.664,75")
        tipo_conta = os.getenv("TIPO_CONTA_PADRAO", "Salário")
        va = os.getenv("VA_PADRAO", "0,00")
        vr = os.getenv("VR_PADRAO", "0,00")
        plano_saude = os.getenv("PLANO_SAUDE_PADRAO", "Não")

        dados_finais = {
            'nome': nome,
            'cpf': cpf,
            'rg': rg,
            'pis': pis,
            'cargo': cargo,
            'salario': salario_base,
            'vt_diario': vt_valor_str,
            'data_inicio': DATA_INICIO_PADRAO,
            'obra': '',
            'nacionalidade': nacionalidade,
            'estado_civil': estado_civil,
            'Logradouro': logradouro,
            'Numero Endereco': numero,
            'Bairro': bairro,
            'Cidade': cidade,
            'Estado': uf,
            'CEP': cep,
            'Complemento': complemento,
            'Data de Nascimento': dt_nasc.strftime('%d/%m/%Y') if dt_nasc else '',
            'Local de Nascimento': local_nasc,
            'Orgao Emissor RG': orgao_rg,
            'UF RG': uf_rg,
            'Titulo de Eleitor': titulo,
            'Zona': zona,
            'Secao': secao,
            'Reservista': reservista,
            'mae': ia.get("Nome da Mae", ""), 
            'pai': ia.get("Nome do Pai", ""),
            'CTPS Numero': ia.get("CTPS Numero", ""),
            'CTPS Serie': ia.get("CTPS Serie", ""),
            'CTPS UF': ia.get("CTPS UF", ""),
            'email': email,
            'telefone': telefone,
            'celular': celular,
            'vt_optin': vt_optin,
            'linha_ida': linha_ida,
            'valor_ida': valor_ida,
            'linha_volta': linha_volta,
            'valor_volta': valor_volta,
            'va': "485,00",
            'vr': "120,00",
            'plano_saude': "NÃO",
            'banco': banco,
            'agencia': agencia,
            'conta': conta,
            'tipo_conta': "Corrente",
            'escolaridade': escolaridade or "",
            'curso': curso or "",
            'conjuge': conjuge,
            'conjuge_cpf': conjuge_cpf,
            'conjuge_dt': conjuge_dt.strftime('%d/%m/%Y') if conjuge_dt else '',
            'dep1_nome': dep1_nome,
            'dep1_dt': dep1_dt.strftime('%d/%m/%Y') if dep1_dt else '',
            'dep1_parent': dep1_parent,
            'dep2_nome': '',
            'dep2_dt': '',
            'dep2_parent': '',
        }

        with st.spinner("Gerando kit no Drive e preenchendo planilha..."):
            link_pasta, pasta_id = gerar_kit_admissional(dados_finais)

        with st.spinner("Exportando e mesclando PDFs para assinatura unificada..."):
            pdfs = exportar_pdfs_da_pasta(pasta_id)
            
            # Novo fluxo: envia direto pro D4Sign em vez de apenas baixar ZIP
            # Mantemos a geração do ZIP como backup local do RH
            zip_bytes = preparar_pacote_para_d4sign(pdfs)
            
            # --- Mesclar PDFs em um único arquivo para economizar créditos do D4Sign ---
            import io
            from PyPDF2 import PdfMerger
            
            merger = PdfMerger()
            for nome_arq, conteudo_pdf in pdfs:
                # Adiciona cada PDF ao merger lendo os bytes originais
                merger.append(io.BytesIO(conteudo_pdf))
            
            # Salvar o PDF mesclado num buffer de memória
            merged_pdf_buffer = io.BytesIO()
            merger.write(merged_pdf_buffer)
            merger.close()
            
            kit_completo_bytes = merged_pdf_buffer.getvalue()
            nome_kit_unico = f"Kit_Admissional_{nome.replace(' ', '_')}.pdf"
            # ----------------------------------------------------------------------------
            
            progresso_zapsign = st.progress(0, text="Disparando Kit Único para assinatura ZapSign...")
            try:
                # O envio agora mapeia o celular e a âncora ZapSign
                celular_extracao = dados_finais.get("celular", dados_finais.get("Celular", ""))
                enviar_documento_zapsign(kit_completo_bytes, nome_kit_unico, email, cpf, celular_extracao, nome)
                progresso_zapsign.progress(1.0, text=f"Enviado: {nome_kit_unico}")
            except Exception as e:
                st.error(f"Erro ao enviar o Kit Único para ZapSign. Detalhes: {e}")
                progresso_zapsign.progress(1.0, text="Falha no envio")

        with st.spinner("Salvando uploads originais no Drive..."):
            salvar_uploads_na_pasta(pasta_id, uploads)

        st.success("🎉 Processo concluído! Seus dados foram enviados para criação do contrato, aguarde o link para assinatura no seu Whatsapp.")


if __name__ == "__main__":
    render_public_form()
