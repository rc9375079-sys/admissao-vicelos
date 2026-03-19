import os
import io
import json
from unittest.mock import patch, MagicMock
from streamlit.testing.v1 import AppTest

def test_app_loads_correctly():
    """
    Testa se o formulário público carrega sem erros e renderiza os componentes iniciais básicos.
    """
    at = AppTest.from_file("public_admissao.py")
    at.run()
    
    assert not at.exception, f"O aplicativo lançou uma exceção: {at.exception}"
    assert "🏗️ Admissão Inteligente - Vicelos" in at.title[0].value, "O título da página está incorreto ou ausente."
    assert len(at.button) >= 1, "Não encontrou os botões esperados no formulário."
    
    # Campo Nome Completo é o primeiro text_input
    assert at.text_input[0].label == "Nome Completo *", "Primeiro input não é 'Nome Completo *'"
    assert at.text_input[0].value == "", "Campo nome não começou vazio."

@patch("public_admissao.processar_documentos_ia")
def test_ia_extraction_success(mock_processar):
    """
    Testa se os dados de sessão provenientes da IA refletem nos inputs da tela.
    """
    at = AppTest.from_file("public_admissao.py")
    
    fake_ia_data = {
        "Nome Completo": "João Fake Silva",
        "CPF": "123.456.789-00",
        "Data de Nascimento": "01/01/1990",
        "Logradouro": "Rua das Flores"
    }
    
    at.run()
    at.session_state["ia_data"] = fake_ia_data
    at.run()
    
    assert at.text_input[0].value == "João Fake Silva", "Nome Completo da IA não preencheu."
    
    cpf_input = next(ti for ti in at.text_input if ti.label == "CPF *")
    assert cpf_input.value == "123.456.789-00", "CPF da IA não preencheu."
    
    end_input = next(ti for ti in at.text_input if ti.label == "Endereço (Rua/Av) *")
    assert end_input.value == "Rua das Flores", "Endereço da IA não preencheu."

@patch("public_admissao.salvar_uploads_na_pasta")
def test_submission_fails_without_required(mock_salvar, mock_exportar, mock_gerar):
    """
    Garante que o formulário bloqueie a submissão se campos obrigatórios ou uploads estiverem faltando.
    """
    at = AppTest.from_file("public_admissao.py")
    at.run()
    
    # Simula o aceite na checkbox
    checkbox = next(cb for cb in at.checkbox if cb.label.startswith("Li e concordo"))
    checkbox.set_value(True).run()
    
    # Clica em submeter ("Validar e GERAR KIT DE ADMISSÃO" technically might be the second button if "Extrair..." is the first, but "Extrair..." only appears if uploads exist. However, form_submit_button might be treated differently)
    # in Streamlit 1.x, form_submit_button is just a regular button or form submit. 
    submit_btn = next((btn for btn in at.button if "Validar e GERAR KIT" in btn.label), None)
    if submit_btn:
        submit_btn.click().run()
        
    assert at.error, "O sistema não mostrou mensagens de erro de validação."
    assert not mock_gerar.called, "Geração de kit chamada mesmo com campos faltando."
