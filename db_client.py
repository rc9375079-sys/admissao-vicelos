import os
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, List, Dict

import psycopg2
from psycopg2.extras import RealDictCursor


def _conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "vicelos_erp"),
        user=os.getenv("DB_USER", "renancarvalho"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def _to_decimal(raw: Optional[str]) -> Decimal:
    if raw is None or raw == "":
        return Decimal("0.00")
    try:
        if isinstance(raw, (int, float, Decimal)):
            return Decimal(str(raw))
        txt = str(raw).replace("R$", "").strip()
        # Remove thousands separator if it's dot and decimal is comma (Brazilian format)
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
        elif "," in txt:
            txt = txt.replace(",", ".")
        return Decimal(txt)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def upsert_entidade(nome: str, cpf: str, tipo: str = "funcionario") -> str:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entidades (tipo, nome, cpf_cnpj)
            VALUES (%s, %s, %s)
            ON CONFLICT (cpf_cnpj) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id;
            """,
            (tipo, nome, cpf),
        )
        return cur.fetchone()[0]


def get_or_create_cargo(nome: str, cbo: Optional[str], salario_base: Optional[Decimal]) -> Optional[str]:
    nome_clean = nome.strip() if nome else "Cargo não informado"
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id FROM cargos
            WHERE nome = %s AND (cbo IS NOT DISTINCT FROM %s);
            """,
            (nome_clean, cbo),
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute(
            """
            INSERT INTO cargos (id, nome, cbo, salario_base)
            VALUES (gen_random_uuid(), %s, %s, %s)
            RETURNING id;
            """,
            (nome_clean, cbo, salario_base),
        )
        return cur.fetchone()["id"]


def upsert_funcionario(entidade_id: str, cargo_id: Optional[str], data_admissao: Optional[date], salario_atual: Optional[Decimal], ctps_numero: Optional[str], centro_custo_id: Optional[str] = None, banco: Optional[str] = None, agencia: Optional[str] = None, conta: Optional[str] = None) -> str:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO funcionarios (id, entidade_id, cargo_id, data_admissao, salario_atual, ctps_numero, centro_custo_id, banco, agencia, conta)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (entidade_id) DO UPDATE
            SET cargo_id = EXCLUDED.cargo_id,
                data_admissao = COALESCE(EXCLUDED.data_admissao, funcionarios.data_admissao),
                salario_atual = COALESCE(EXCLUDED.salario_atual, funcionarios.salario_atual),
                ctps_numero = COALESCE(EXCLUDED.ctps_numero, funcionarios.ctps_numero),
                centro_custo_id = COALESCE(EXCLUDED.centro_custo_id, funcionarios.centro_custo_id),
                banco = COALESCE(EXCLUDED.banco, funcionarios.banco),
                agencia = COALESCE(EXCLUDED.agencia, funcionarios.agencia),
                conta = COALESCE(EXCLUDED.conta, funcionarios.conta)
            RETURNING id;
            """,
            (entidade_id, cargo_id, data_admissao, salario_atual, ctps_numero, centro_custo_id, banco, agencia, conta),
        )
        return cur.fetchone()[0]


def save_admission_record(dados: dict) -> Optional[str]:
    """
    Recebe o dicionário do formulário e garante persistência mínima:
    - entidades (tipo=funcionario)
    - cargos (opcional)
    - funcionarios (FK entidade/cargo)
    """
    nome = (dados.get("nome") or dados.get("Nome Completo") or "").strip()
    cpf = (dados.get("cpf") or dados.get("CPF") or "").strip()
    if not nome or not cpf:
        return None

    cargo_nome = dados.get("cargo") or dados.get("Cargo") or "Cargo não informado"
    cbo = dados.get("cbo") or dados.get("CBO")
    salario = _to_decimal(dados.get("salario") or dados.get("salario_base") or dados.get("Salario"))
    ctps = dados.get("CTPS Numero") or dados.get("ctps_num") or dados.get("ctps")

    data_inicio_txt = dados.get("data_inicio") or dados.get("Data de Admissao") or dados.get("data_admissao")
    data_inicio = None
    if data_inicio_txt:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                data_inicio = datetime.strptime(data_inicio_txt, fmt).date()
                break
            except Exception:
                continue

    entidade_id = upsert_entidade(nome, cpf, tipo="funcionario")
    cargo_id = get_or_create_cargo(cargo_nome, cbo, salario)
    return upsert_funcionario(entidade_id, cargo_id, data_inicio, salario, ctps)


def get_funcionarios_financeiro() -> List[Dict]:
    """
    Busca funcionários no Postgres integrando dados de entidades e cargos.
    """
    sql = """
    SELECT 
        e.id as entidade_id,
        e.nome, 
        e.cpf_cnpj as cpf, 
        f.data_admissao as admissao, 
        c.nome as cargo, 
        c.cbo, 
        f.salario_atual as salario,
        f.ctps_numero as ctps,
        f.banco, 
        f.agencia,
        f.conta,
        f.oposicao, 
        f.vt_diario as "VT Diário",
        f.va_mensal as "Valor VA",
        f.vr_mensal as "Valor VR",
        f.descontar_vt as "Descontar VT",
        f.descontar_va as "Descontar VA",
        cc.nome as obra
    FROM funcionarios f
    JOIN entidades e ON f.entidade_id = e.id
    LEFT JOIN cargos c ON f.cargo_id = c.id
    LEFT JOIN centros_de_custo cc ON f.centro_custo_id = cc.id
    WHERE e.tipo = 'funcionario'
    ORDER BY e.nome ASC;
    """
    lista = []
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        for row in cur.fetchall():
            # Formatação para compatibilidade com app.py
            item = dict(row)
            if item['admissao']:
                item['admissao'] = item['admissao'].strftime('%d/%m/%Y')
            else:
                item['admissao'] = ""
            
            # Garantir que valores numéricos sejam strings formatadas se o app.py as tratar assim
            # No futuro, o app.py usará Decimal diretamente.
            item['salario'] = str(item['salario']) if item['salario'] else "0.00"
            item['VT Diário'] = str(item.get('VT Diário', '0'))
            item['Valor VA'] = str(item.get('Valor VA', '0'))
            item['Valor VR'] = str(item.get('Valor VR', '0'))
            lista.append(item)
    return lista


def health_check() -> tuple[bool, str]:
    """Tenta abrir conexão e fazer SELECT 1."""
    try:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return True, "OK"
    except Exception as e:
        return False, str(e)


# --------------------------------------------------------------------
# NFSe ingestion helpers
# --------------------------------------------------------------------

def _get_plano_conta_ids(cur) -> Dict[str, str]:
    cur.execute("SELECT codigo, id FROM plano_de_contas WHERE codigo IN ('R01','A01','A02','A03');")
    mapping = {row[0]: row[1] for row in cur.fetchall()}
    missing = [c for c in ['R01','A01','A02','A03'] if c not in mapping]
    if missing:
        raise ValueError(f"Contas não encontradas: {missing}")
    return mapping


def _get_first_conta_bancaria(cur) -> Optional[str]:
    cur.execute("SELECT id FROM contas_bancarias WHERE ativa IS TRUE LIMIT 1;")
    row = cur.fetchone()
    return row[0] if row else None


def import_nfse_rows(rows: List[Dict]) -> Dict:
    """
    Recebe lista de dicts já normalizados (valores Decimal, datas date) e insere:
      - entidades (cliente)
      - centros_de_custo (opcional)
      - lancamentos + lancamento_itens
      - movimentacoes_financeiras (se valor_recebido > 0)
    Retorna resumo com contagens e erros.
    """
    resumo = {"lancamentos_criados": 0, "movimentacoes_criadas": 0, "erros": []}
    with _conn() as conn, conn.cursor() as cur:
        contas = _get_plano_conta_ids(cur)
        conta_bancaria_id = _get_first_conta_bancaria(cur)

        for idx, r in enumerate(rows):
            try:
                nome = (r.get("tomador_nome") or "").strip()
                cpf = (r.get("tomador_cpf") or "").strip()
                if not nome or not cpf:
                    resumo["erros"].append(f"Linha {idx+1}: faltam tomador/CPF")
                    continue

                # entidade
                cur.execute(
                    """
                    INSERT INTO entidades (tipo, nome, cpf_cnpj)
                    VALUES ('cliente', %s, %s)
                    ON CONFLICT (cpf_cnpj) DO UPDATE SET nome=EXCLUDED.nome
                    RETURNING id;
                    """,
                    (nome, cpf),
                )
                entidade_id = cur.fetchone()[0]

                # centro de custo (opcional)
                centro_id = None
                obra_codigo = r.get("obra_codigo")
                if obra_codigo:
                    cur.execute(
                        """
                        INSERT INTO centros_de_custo (id,codigo,nome,tipo,status)
                        VALUES (gen_random_uuid(), %s, %s, 'obra', 'ativo')
                        ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome
                        RETURNING id;
                        """,
                        (obra_codigo, obra_codigo),
                    )
                    centro_id = cur.fetchone()[0]

                data_comp = r.get("data_fato")
                if data_comp is None:
                    resumo["erros"].append(f"Linha {idx+1}: data do fato inválida")
                    continue

                valor_serv = r.get("valor_servicos") or Decimal("0")
                iss_ret = r.get("iss_retido") or Decimal("0")
                inss_ret = r.get("inss_retido") or Decimal("0")
                deducoes = r.get("deducoes") or Decimal("0")
                ret_tec = r.get("retencao_tecnica") or Decimal("0")
                # valor líquido efetivo recebido
                valor_liq_receb = r.get("valor_recebido") or Decimal("0")
                # saldo AR = líquido + retenção técnica
                valor_ar = valor_liq_receb + ret_tec
                if valor_ar < 0:
                    valor_ar = Decimal("0")

                # lancamento
                descricao = (r.get("descricao") or "")[:500]
                numero_doc = (r.get("numero") or "")[:60]

                cur.execute(
                    """
                    INSERT INTO lancamentos (id, data_competencia, descricao, entidade_id, centro_custo_id, numero_documento)
                    VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (data_comp, descricao, entidade_id, centro_id, numero_doc),
                )
                lanc_id = cur.fetchone()[0]

                # itens
                items = []
                # crédito receita
                items.append((lanc_id, contas["R01"], "credito", valor_serv))
                # débito AR
                if valor_ar > 0:
                    items.append((lanc_id, contas["A03"], "debito", valor_ar))
                # débitos retenções
                if iss_ret > 0:
                    items.append((lanc_id, contas["A02"], "debito", iss_ret))
                if inss_ret > 0:
                    items.append((lanc_id, contas["A01"], "debito", inss_ret))

                inserted_items = []
                for li in items:
                    cur.execute(
                        """
                        INSERT INTO lancamento_itens (id, lancamento_id, conta_id, tipo_partida, valor)
                        VALUES (gen_random_uuid(), %s, %s, %s, %s)
                        RETURNING id, conta_id, tipo_partida, valor;
                        """,
                        li,
                    )
                    inserted_items.append(cur.fetchone())

                # movimento financeiro (entrada) se houver valor recebido
                valor_receb = r.get("valor_recebido") or Decimal("0")
                if valor_receb > 0 and conta_bancaria_id:
                    # pegar item AR (A03) para vincular
                    item_ar = next((it for it in inserted_items if it[1] == contas["A03"]), None)
                    if item_ar:
                        cur.execute(
                            """
                            INSERT INTO movimentacoes_financeiras
                            (id, lancamento_item_id, conta_bancaria_id, data_pagamento, valor_pago, tipo_movimento)
                            VALUES (gen_random_uuid(), %s, %s, %s, %s, 'entrada');
                            """,
                            (item_ar[0], conta_bancaria_id, r.get("data_pagamento") or data_comp, valor_receb),
                        )
                        resumo["movimentacoes_criadas"] += 1

                resumo["lancamentos_criados"] += 1

            except Exception as e:
                resumo["erros"].append(f"Linha {idx+1}: {e}")

    return resumo
def save_payroll_record(entidade_id: str, competencia: str, data_pagamento: date, valor_liquido: Decimal, obra: str = "") -> bool:
    """
    Grava o resultado do processamento da folha no ERP (tabelas lancamentos e lancamento_itens).
    Utiliza partidas dobradas: Débito em Custo e Crédito em Salários a Pagar.
    """
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # 1. Obter ID do Centro de Custo pela Obra
                centro_custo_id = None
                if obra:
                    cur.execute("SELECT id FROM centros_de_custo WHERE nome = %s OR codigo = %s LIMIT 1", (obra, obra))
                    res_cc = cur.fetchone()
                    if res_cc: centro_custo_id = res_cc[0]

                # 2. Criar o Lançamento Principal (Cabeçalho)
                # O ID é gerado automaticamente (UUID)
                cur.execute("""
                    INSERT INTO lancamentos (data_competencia, descricao, entidade_id, centro_custo_id, numero_documento)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    competencia, 
                    f"FOLHA DE PAGAMENTO - {competencia} - {obra}", 
                    entidade_id, 
                    centro_custo_id, 
                    f"FOLHA-{competencia.replace('/', '')}"
                ))
                lancamento_id = cur.fetchone()[0]

                # 3. Criar Partidas (Débitos e Créditos)
                
                # A. DÉBITO: Custo de Salários (4.1.1.02.000001 - Salários e Ordenados)
                cur.execute("SELECT id FROM plano_de_contas WHERE codigo = '4.1.1.02.000001' LIMIT 1")
                row_deb = cur.fetchone()
                if not row_deb:
                    # Fallback para conta administrativa
                    cur.execute("SELECT id FROM plano_de_contas WHERE codigo = '4.2.2.01.000001' LIMIT 1")
                    row_deb = cur.fetchone()
                
                if not row_deb: raise Exception("Conta de Custo de Salários não encontrada no Plano de Contas.")
                conta_debito_id = row_deb[0]

                # B. CRÉDITO: Salários a Pagar (2.1.5.01.000001)
                cur.execute("SELECT id FROM plano_de_contas WHERE codigo = '2.1.5.01.000001' LIMIT 1")
                row_cre = cur.fetchone()
                if not row_cre: raise Exception("Conta de Salários a Pagar (2.1.5.01.000001) não encontrada.")
                conta_credito_id = row_cre[0]

                # Executar Inserts nos Itens
                # Débito
                cur.execute(
                    "INSERT INTO lancamento_itens (lancamento_id, conta_id, tipo_partida, valor, status_vencimento) VALUES (%s, %s, %s, %s, %s)",
                    (lancamento_id, conta_debito_id, 'debito', valor_liquido, 'pendente')
                )
                # Crédito
                cur.execute(
                    "INSERT INTO lancamento_itens (lancamento_id, conta_id, tipo_partida, valor, data_vencimento, status_vencimento) VALUES (%s, %s, %s, %s, %s, %s)",
                    (lancamento_id, conta_credito_id, 'credito', valor_liquido, data_pagamento, 'pendente')
                )

                return True
    except Exception as e:
        print(f"Erro ao persistir folha no ERP: {e}")
        return False
    finally:
        conn.close()
