"""
Módulo de Cálculos para Rescisão de Contrato de Trabalho.

Este módulo implementa toda a lógica de cálculo para cenários de desligamento
em conformidade com a legislação trabalhista brasileira (CLT, 2026).

Regras Implementadas:
- Períodos de experiência (45 e 90 dias) com Multa Art. 479
- Cálculo proporcional de férias, 1/3 e 13º salário
- FGTS e multa por rescisão sem justa causa (40%)
- Projeção de demissão (manter até o fim do período)
- Fatiamento de caixa (folha mensal vs rescisão futura)
"""

from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar
from typing import Dict, Any, Optional


# ===============================================================
# CONSTANTES E TABELAS LEGAIS
# ===============================================================

# Fonte: CLT Art. 479 - Multa por rescisão durante período de experiência
MULTA_ART_479_PERCENTUAL = Decimal("0.50")  # 50% do salário diário

# Fonte: CLT Art. 480-481 / Lei 8.036 - Alíquota FGTS do empregador
ALIQUOTA_FGTS_EMPREGADOR = Decimal("0.08")  # 8% sobre bruto

# Fonte: Lei 10.166 - Multa FGTS para rescisão sem justa causa
MULTA_FGTS_SEM_JUSTA_CAUSA = Decimal("0.40")  # 40% sobre saldo acumulado

# Períodos de experiência
PERIODO_EXPERIENCIA_1 = 45  # dias
PERIODO_EXPERIENCIA_2 = 90  # dias

# Constantes de cálculo
DIAS_POR_MES = Decimal("30")
MESES_POR_ANO = Decimal("12")
DIAS_UTEIS_PERCENTUAL = Decimal("0.73")  # 22 dias úteis / 30 dias = ~0.73
DIAS_MINIMOS_PARA_AVO = 15  # dias (CLT Art. 146)


# ===============================================================
# FUNÇÕES DE CÁLCULO PURO (SEM IO)
# ===============================================================

def calcular_dias_trabalhados(dt_admissao: date, dt_calculo: date) -> int:
    """
    Calcula dias trabalhados entre admissão e data de cálculo.
    
    Inclui o dia de admissão mais todos os dias subsequentes até a data informada.
    Fonte: CLT Art. 476 - Contagem de tempo de serviço.
    
    Args:
        dt_admissao: Data de admissão
        dt_calculo: Data de cálculo (ex: data projetada de desligamento)
    
    Returns:
        Número total de dias trabalhados
    """
    dias = (dt_calculo - dt_admissao).days + 1
    print(f"DEBUG: Dias trabalhados = {dias} (de {dt_admissao} a {dt_calculo})")
    return dias


def classificar_fase_contratual(dias_trabalhados: int, dt_admissao: date, dt_calculo: date) -> tuple[str, Optional[date], int]:
    """
    Classifica em qual fase do contrato o funcionário se encontra.
    
    Retorna também a data-alvo (fim do período de experiência) e dias restantes.
    Fonte: CLT Art. 445 - Períodos de experiência.
    
    Args:
        dias_trabalhados: Total de dias desde admissão
        dt_admissao: Data de admissão
        dt_calculo: Data de cálculo
    
    Returns:
        Tupla: (fase_descricao, dt_alvo, dias_restantes)
    """
    if dias_trabalhados <= PERIODO_EXPERIENCIA_1:
        fase = "1º Período de Experiência (45 dias)"
        dt_alvo = dt_admissao + timedelta(days=PERIODO_EXPERIENCIA_1 - 1)
        dias_restantes = (dt_alvo - dt_calculo).days
    elif dias_trabalhados <= PERIODO_EXPERIENCIA_2:
        fase = "2º Período de Experiência (90 dias)"
        dt_alvo = dt_admissao + timedelta(days=PERIODO_EXPERIENCIA_2 - 1)
        dias_restantes = (dt_alvo - dt_calculo).days
    else:
        fase = "Contrato por Prazo Indeterminado"
        dt_alvo = None
        dias_restantes = 0
    
    print(f"DEBUG: Fase = {fase} | Dias restantes = {dias_restantes}")
    return (fase, dt_alvo, dias_restantes)


def calcular_multa_art_479(salario_diario: Decimal, dias_restantes: int) -> Decimal:
    """
    Calcula multa Art. 479 (50% do salário pelos dias restantes).
    
    Aplicável apenas se rescisão ocorre durante período de experiência.
    Fonte: CLT Art. 479 - Rescisão durante período de experiência.
    
    Args:
        salario_diario: Valor do salário diário
        dias_restantes: Dias até o término do período de experiência
    
    Returns:
        Valor da multa (Decimal)
    """
    if dias_restantes <= 0:
        multa = Decimal("0.00")
    else:
        multa = ((Decimal(str(dias_restantes)) * salario_diario) / 2).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    print(f"DEBUG: Multa Art. 479 (50% de {dias_restantes} dias) = R$ {multa}")
    return multa


def calcular_avos(dias: int) -> int:
    """
    Calcula número de avos (1/12 do ano) para férias/13º.
    
    Um avo é creditado a cada mês trabalhado, se tiver trabalhado
    15 dias ou mais naquele mês. Casos de menos de 15 dias não geram direito.
    Fonte: CLT Art. 146 e 151.
    
    Args:
        dias: Número total de dias trabalhados
    
    Returns:
        Número de avos (0 a 12)
    """
    meses_cheios = dias // 30
    dias_sobra = dias % 30
    avos = meses_cheios + (1 if dias_sobra >= DIAS_MINIMOS_PARA_AVO else 0)
    print(f"DEBUG: Avos calculados = {avos} (meses_cheios={meses_cheios}, dias_sobra={dias_sobra})")
    return avos


def calcular_ferias_proporcional(salario_mensal: Decimal, avos: int) -> Decimal:
    """
    Calcula férias proporcionais ao período trabalhado.
    
    Fórmula: (Salário / 12) * Número de Avos
    Fonte: CLT Art. 146 - Direito a férias proporcionais.
    
    Args:
        salario_mensal: Salário mensal bruto
        avos: Número de avos (1/12 do ano)
    
    Returns:
        Valor de férias proporcionais
    """
    ferias = (salario_mensal / MESES_POR_ANO) * Decimal(str(avos))
    ferias = ferias.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"DEBUG: Férias = ({salario_mensal} / 12) * {avos} = R$ {ferias}")
    return ferias


def calcular_terco_ferias(ferias: Decimal) -> Decimal:
    """
    Calcula 1/3 de férias (abono constitucional).
    
    Fonte: CF/88 Art. 7º, XVII - Direito ao 1/3 de férias.
    
    Args:
        ferias: Valor total de férias
    
    Returns:
        Valor do 1/3
    """
    terco = (ferias / Decimal("3")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"DEBUG: 1/3 Férias = {ferias} / 3 = R$ {terco}")
    return terco


def calcular_decimo_terceiro_proporcional(salario_mensal: Decimal, avos: int) -> Decimal:
    """
    Calcula 13º salário proporcional ao período trabalhado.
    
    Fórmula: (Salário / 12) * Número de Avos
    Fonte: Lei 4.090/62 - 13º salário.
    
    Args:
        salario_mensal: Salário mensal bruto
        avos: Número de avos (1/12 do ano)
    
    Returns:
        Valor proporção de 13º
    """
    decimo = (salario_mensal / MESES_POR_ANO) * Decimal(str(avos))
    decimo = decimo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"DEBUG: 13º Salário = ({salario_mensal} / 12) * {avos} = R$ {decimo}")
    return decimo


def calcular_fgts_estimado(dias_trabalhados: int, salario_diario: Decimal, decimo: Decimal) -> tuple[Decimal, Decimal]:
    """
    Calcula estimativa de FGTS acumulado e multa de 40% (sem justa causa).
    
    Base FGTS = (Salário diário * Dias trabalhados) + 13º proporcional
    Multa 40% = Saldo FGTS * 0.40 (apenas para rescisão sem justa causa)
    
    Fonte: Lei 8.036/90 - FGTS; CLT Art. 477 - Rescisão.
    
    Args:
        dias_trabalhados: Dias totais trabalhados
        salario_diario: Valor do salário diário
        decimo: Valor do 13º proporcional
    
    Returns:
        Tupla: (saldo_fgts, multa_40_percent)
    """
    base_fgts = (salario_diario * Decimal(str(dias_trabalhados))) + decimo
    saldo_fgts = (base_fgts * ALIQUOTA_FGTS_EMPREGADOR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    multa_fgts = (saldo_fgts * MULTA_FGTS_SEM_JUSTA_CAUSA).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    print(f"DEBUG: Base FGTS = R$ {base_fgts} | Saldo (8%) = R$ {saldo_fgts} | Multa (40%) = R$ {multa_fgts}")
    return (saldo_fgts, multa_fgts)


def calcular_beneficios_consumidos(
    salario_diario: Decimal, dias_trabalhados: int,
    va_mensal: Decimal, vr_mensal: Decimal, vt_diario: Decimal
) -> Dict[str, Decimal]:
    """
    Calcula custo de benefícios consumidos (VA, VR, VT) durante o período trabalhado.
    
    Pressupostos:
    - VT: Considerando 73% de dias úteis (22/30)
    - VA/VR: Proporcional aos dias trabalhados (excluindo fins de semana)
    
    Args:
        salario_diario: Valor do salário diário
        dias_trabalhados: Dias totais trabalhados
        va_mensal: Vale Alimentação mensal
        vr_mensal: Vale Refeição mensal
        vt_diario: Vale Transporte diário
    
    Returns:
        Dicionário com custos de VA, VR, VT
    """
    dias_uteis = (Decimal(str(dias_trabalhados)) * DIAS_UTEIS_PERCENTUAL).quantize(Decimal("1"))
    
    vt_gasto = (dias_uteis * vt_diario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    va_gasto = ((va_mensal / DIAS_POR_MES) * Decimal(str(dias_trabalhados))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vr_gasto = ((vr_mensal / DIAS_POR_MES) * Decimal(str(dias_trabalhados))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    print(f"DEBUG: Benefícios VT={vt_gasto}, VA={va_gasto}, VR={vr_gasto}")
    return {
        "vt_gasto": vt_gasto,
        "va_gasto": va_gasto,
        "vr_gasto": vr_gasto
    }


def calcular_projecao_futura(
    dt_admissao: date, dias_trabalhados: int,
    salario_diario: Decimal, salario_mensal: Decimal, dt_calculo: date
) -> Dict[str, Any]:
    """
    Projeta cenário futuro se o funcionário for mantido até fim do período.
    
    Calcula:
    - Novo número de avos ao atingir prazo
    - Férias, 1/3, 13º projetados
    - Fatiamento de salário (folha mensal vs rescisão futura)
    - VA/VR projetados apenas para mês de rescisão
    
    Args:
        dt_admissao: Data de admissão
        dias_trabalhados: Dias atuais (data de cálculo - admissão)
        salario_diario: Valor do salário diário
        salario_mensal: Valor do salário mensal
        dt_calculo: Data de cálculo
    
    Returns:
        Dicionário com projeções
    """
    # Determinar o novo total de dias ao fim do contrato
    if dias_trabalhados <= PERIODO_EXPERIENCIA_1:
        dt_alvo = dt_admissao + timedelta(days=PERIODO_EXPERIENCIA_1 - 1)
        total_dias_proj = PERIODO_EXPERIENCIA_1
    elif dias_trabalhados <= PERIODO_EXPERIENCIA_2:
        dt_alvo = dt_admissao + timedelta(days=PERIODO_EXPERIENCIA_2 - 1)
        total_dias_proj = PERIODO_EXPERIENCIA_2
    else:
        # Fora da experiência - usar data atual como base
        dt_alvo = None
        total_dias_proj = dias_trabalhados
    
    dias_restantes = (dt_alvo - dt_calculo).days if dt_alvo else 0
    
    # Calcular avos projetados
    avos_proj = calcular_avos(total_dias_proj)
    ferias_proj = calcular_ferias_proporcional(salario_mensal, avos_proj)
    terco_proj = calcular_terco_ferias(ferias_proj)
    decimo_proj = calcular_decimo_terceiro_proporcional(salario_mensal, avos_proj)
    
    # Fatiamento de caixa
    salario_folha_mensal = Decimal("0.00")
    salario_rescisao_futura = Decimal("0.00")
    dias_rescisao_futura = 0
    
    if dias_restantes > 0:
        # Encontrar quantos dias faltam até o final do mês atual
        ultimo_dia_mes_atual = calendar.monthrange(dt_calculo.year, dt_calculo.month)[1]
        dias_ate_fim_mes = (date(dt_calculo.year, dt_calculo.month, ultimo_dia_mes_atual) - dt_calculo).days
        
        if dt_alvo and dt_alvo.month == dt_calculo.month:
            # Rescisão no mesmo mês: toda a folha vai neste mês
            salario_folha_mensal = (Decimal(str(dias_restantes)) * salario_diario).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            dias_rescisao_futura = 0
        else:
            # Rescisão em mês posterior: dividir entre este e próximo
            salario_folha_mensal = (Decimal(str(dias_ate_fim_mes)) * salario_diario).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            dias_rescisao_futura = dias_restantes - dias_ate_fim_mes
            salario_rescisao_futura = (Decimal(str(dias_rescisao_futura)) * salario_diario).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
    
    print(f"DEBUG: Projeção = Folha mês atual: R$ {salario_folha_mensal}, Folha futura: R$ {salario_rescisao_futura}")
    
    return {
        "dt_alvo": dt_alvo.strftime("%d/%m/%Y") if dt_alvo else "N/A",
        "dias_restantes": dias_restantes,
        "avos_proj": avos_proj,
        "ferias_proj": ferias_proj,
        "terco_proj": terco_proj,
        "decimo_proj": decimo_proj,
        "salario_folha_mensal": salario_folha_mensal,
        "salario_rescisao_futura": salario_rescisao_futura,
        "dias_rescisao_futura": dias_rescisao_futura
    }


def calcular_cenarios_desligamento(
    func_dados: Dict[str, Any], dt_desligamento: date
) -> Optional[Dict[str, Any]]:
    """
    FUNÇÃO PRINCIPAL: Calcula cenários de rescisão (hoje vs. manter até prazo).
    
    Entrada: Dados do funcionário (admissão, salário, benefícios)
    Saída: Dicionário completo com Cenário A (desligar hoje) e Cenário B (manter)
    
    Legenda:
    - Cenário A: Custo imediato se desligar hoje
    - Cenário B: Custo futuro se aguardar fim do período
    
    Args:
        func_dados: Dict com chaves esperadas:
            - 'admissao' (str DD/MM/AAAA)
            - 'salario' (str ou Decimal)
            - 'Valor VA' (str ou Decimal)
            - 'vr_mensal' (str ou Decimal)
            - 'VT Diário' (str ou Decimal)
        dt_desligamento: Date da projeção de desligamento
    
    Returns:
        Dicionário completo de resultados ou None se erro na parsing de datas
    
    Example:
        >>> func = {
        ...     'admissao': '01/01/2024',
        ...     'salario': '5000.00',
        ...     'Valor VA': '30',
        ...     'vr_mensal': '30',
        ...     'VT Diário': '5'
        ... }
        >>> resultado = calcular_cenarios_desligamento(func, date(2024, 3, 15))
        >>> print(resultado['fase'])
        '1º Período de Experiência (45 dias)'
    """
    # ===== PARSING E INICIALIZAÇÃO =====
    try:
        dt_adm = datetime.strptime(func_dados.get("admissao", ""), "%d/%m/%Y").date()
    except Exception as e:
        print(f"DEBUG: Erro ao parsear data de admissão: {e}")
        return None
    
    # Converter valores para Decimal
    def _to_decimal_local(valor: Any) -> Decimal:
        if isinstance(valor, Decimal):
            return valor
        try:
            return Decimal(str(valor))
        except:
            return Decimal("0.00")
    
    salario = _to_decimal_local(func_dados.get("salario", "0"))
    va_mensal = _to_decimal_local(func_dados.get("Valor VA", "0"))
    vr_mensal = _to_decimal_local(func_dados.get("vr_mensal", "0"))
    vt_diario = _to_decimal_local(func_dados.get("VT Diário", "0"))
    
    valor_dia = (salario / DIAS_POR_MES).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    print(f"\n{'='*60}")
    print(f"SIMULAÇÃO DE RESCISÃO")
    print(f"Funcionário: {func_dados.get('nome', 'N/A')}")
    print(f"Admissão: {dt_adm.strftime('%d/%m/%Y')} | Simulação: {dt_desligamento.strftime('%d/%m/%Y')}")
    print(f"Salário: R$ {salario} | Valor Dia: R$ {valor_dia}")
    print(f"{'='*60}\n")
    
    # ===== CENÁRIO A: DESLIGAR HOJE =====
    dias_trabalhados_hoje = calcular_dias_trabalhados(dt_adm, dt_desligamento)
    fase, dt_alvo, dias_restantes = classificar_fase_contratual(dias_trabalhados_hoje, dt_adm, dt_desligamento)
    
    multa_479 = calcular_multa_art_479(valor_dia, dias_restantes)
    
    # Avos e direitos hoje
    avos_hoje = calcular_avos(dias_trabalhados_hoje)
    ferias_hoje = calcular_ferias_proporcional(salario, avos_hoje)
    terco_hoje = calcular_terco_ferias(ferias_hoje)
    decimo_hoje = calcular_decimo_terceiro_proporcional(salario, avos_hoje)
    
    # FGTS e multa
    saldo_fgts, multa_fgts_hoje = calcular_fgts_estimado(dias_trabalhados_hoje, valor_dia, decimo_hoje)
    
    # Benefícios consumidos
    beneficios_hoje = calcular_beneficios_consumidos(valor_dia, dias_trabalhados_hoje, va_mensal, vr_mensal, vt_diario)
    
    # Saldo de salário do mês atual
    salario_saldo_hoje = (Decimal(str(dt_desligamento.day)) * valor_dia).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    print(f"DEBUG: Saldo Salário (até dia {dt_desligamento.day}) = R$ {salario_saldo_hoje}\n")
    
    # ===== CENÁRIO B: MANTER ATÉ PRAZO =====
    projecao = calcular_projecao_futura(dt_adm, dias_trabalhados_hoje, valor_dia, salario, dt_desligamento)
    
    # VA/VR projetados (apenas para mês de rescisão)
    va_projetado = (
        (va_mensal / DIAS_POR_MES) * Decimal(str(projecao["dias_rescisao_futura"]))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    vr_projetado = (
        (vr_mensal / DIAS_POR_MES) * Decimal(str(projecao["dias_rescisao_futura"]))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    # ===== RETORNO FINAL =====
    resultado =  {
        # Diagnóstico Contratual
        "dias_trabalhados_hoje": dias_trabalhados_hoje,
        "fase": fase,
        "dt_alvo": dt_alvo.strftime("%d/%m/%Y") if dt_alvo else "N/A",
        "dias_restantes": dias_restantes,
        
        # Cenário A - Desligar Hoje
        "multa_479": multa_479,
        "avos_hoje": avos_hoje,
        "ferias_hoje": ferias_hoje,
        "terco_hoje": terco_hoje,
        "decimo_hoje": decimo_hoje,
        "multa_fgts_hoje": multa_fgts_hoje,
        "vt_gasto_hoje": beneficios_hoje["vt_gasto"],
        "va_gasto_hoje": beneficios_hoje["va_gasto"],
        "vr_gasto_hoje": beneficios_hoje["vr_gasto"],
        "salario_saldo_hoje": salario_saldo_hoje,
        
        # Cenário B - Manter até Prazo
        "avos_proj": projecao["avos_proj"],
        "ferias_proj": projecao["ferias_proj"],
        "terco_proj": projecao["terco_proj"],
        "decimo_proj": projecao["decimo_proj"],
        "salario_folha_mensal": projecao["salario_folha_mensal"],
        "salario_rescisao_futura": projecao["salario_rescisao_futura"],
        "dias_rescisao_futura": projecao["dias_rescisao_futura"],
        "va_projetado": va_projetado,
        "vr_projetado": vr_projetado,
        
        # Meta (para referência UI)
        "va_mensal_cheio": va_mensal,
        "vr_mensal_cheio": vr_mensal
    }
    
    print(f"\n✅ Cálculos completos. Total de linhas de debug acima = referência para auditoria.")
    return resultado
