"""
Constantes e Tabelas Legais - Folha de Pagamento 2026.

Módulo centralizado com todas as faixas de tributação, alíquotas
e deduções conforme legislação vigente em 2026.

Fontes:
- INSS: Tabela oficial 2026 (alíquotas progressivas)
- IRRF: Receita Federal - Tabela Mensal 2026
- FGTS: Lei 8.036/90 - Alíquota 8%
- Dependentes: Lei 9.250/95 - Dedução por dependente
"""

from decimal import Decimal

# ===============================================================
# SEGURIDADE SOCIAL - INSS
# ===============================================================

# Fonte: Tabela INSS 2026 (Alíquotas Progressivas)
# Formato: (limite_teto, alíquota)
# Cálculo: Para cada faixa, aplica a alíquota sobre a porção do salário naquele intervalo
FAIXAS_INSS_2026 = [
    # Faixa 1: até R$ 1.518,00 → 7,5%
    (Decimal("1518.00"), Decimal("0.075")),
    # Faixa 2: de R$ 1.518,01 até R$ 2.793,88 → 9,0%
    (Decimal("2793.88"), Decimal("0.09")),
    # Faixa 3: de R$ 2.793,89 até R$ 4.190,83 → 12,0%
    (Decimal("4190.83"), Decimal("0.12")),
    # Faixa 4: de R$ 4.190,84 até R$ 8.157,41 → 14,0%
    (Decimal("8157.41"), Decimal("0.14"))
]

# Teto do INSS (máximo desconto mensal)
TETO_INSS = Decimal("1164.86")

# ===============================================================
# IMPOSTO DE RENDA DA PESSOA FÍSICA - IRRF
# ===============================================================

# Fonte: Receita Federal - Tabela Mensal 2026
# Formato: (limite_teto, alíquota, parcela_a_deduzir)
# Cálculo: (Base_Cálculo × Alíquota) - Parcela_Deduzir
FAIXAS_IRRF_2026 = [
    # Faixa 1: até R$ 2.428,80 → Isento
    (Decimal("2428.80"), Decimal("0.000"), Decimal("0.00")),
    # Faixa 2: de R$ 2.428,81 até R$ 2.826,65 → 7,5% - R$ 182,16
    (Decimal("2826.65"), Decimal("0.075"), Decimal("182.16")),
    # Faixa 3: de R$ 2.826,66 até R$ 3.751,05 → 15,0% - R$ 394,16
    (Decimal("3751.05"), Decimal("0.150"), Decimal("394.16")),
    # Faixa 4: de R$ 3.751,06 até R$ 4.664,68 → 22,5% - R$ 675,49
    (Decimal("4664.68"), Decimal("0.225"), Decimal("675.49")),
    # Faixa 5: acima de R$ 4.664,68 → 27,5% - R$ 908,73
    (Decimal("999999999.99"), Decimal("0.275"), Decimal("908.73"))
]

# Deduções por dependente na base de cálculo do IRRF
# Fonte: Lei 9.250/95 - Art. 2º
DEDUCAO_POR_DEPENDENTE_IRRF = Decimal("189.59")

# Limite de rendimento até o qual há redução adicional (Nova Tabela 2026)
# Benefício: Redutor progressivo para renda até R$ 7.350,00
LIMITE_RENDIMENTO_REDUTOR = Decimal("7350.00")
LIMITE_RENDIMENTO_ISENCAO = Decimal("5000.00")

# Coeficiente de redução gradual para renda entre R$ 5.000 e R$ 7.350
# Fórmula: Redução = 978,62 - (0,133145 × Rendimento)
COEFICIENTE_REDUTOR_IRRF = Decimal("0.133145")
PARCELA_REDUTOR_IRRF = Decimal("978.62")

# Deductible base (Simplificado vs Legal)
DEDUCTIBLE_SIMPLIFICADO_IRRF = Decimal("607.20")

# ===============================================================
# FGTS - FUNDO DE GARANTIA DO TEMPO DE SERVIÇO
# ===============================================================

# Fonte: CLT Art. 480-481 / Lei 8.036 - Contribuição do Empregador
ALIQUOTA_FGTS_EMPREGADOR = Decimal("0.08")  # 8% sobre bruto

# Multa por rescisão sem justa causa
MULTA_FGTS_RESCISAO_SJC = Decimal("0.40")  # 40% sobre saldo acumulado

# ===============================================================
# OUTROS DESCONTOS LEGAIS
# ===============================================================

# Vale Transporte (6% do salário, até a data de corte do mês)
ALIQUOTA_VALE_TRANSPORTE = Decimal("0.06")

# Vale Refeição / Alimentação (valores edital/lei por empresa)
# Estes valores devem ser parametrizados por empresa

# Contribuição Sindical (varia por categoria)
# Padrão: 1% do salário bruto para profissionais urbanos

# ===============================================================
# CONSTANTES VARIAS
# ===============================================================

DIAS_POR_MES = Decimal("30")
DIAS_UTEIS_POR_MES = 22
DIAS_UTEIS_PERCENTUAL = Decimal("0.7333")  # 22/30

# Timezone padrão do sistema
TIMEZONE_PADRAO = "America/Sao_Paulo"

# Localização padrão
LOCALE_PADRAO = "pt_BR"


def obter_faixa_inss(salario: Decimal) -> tuple:
    """
    Retorna a faixa de INSS correspondente ao salário.
    
    Args:
        salario: Salário em Decimal
    
    Returns:
        Tupla: (limite_teto, alíquota)
    """
    for teto, aliq in FAIXAS_INSS_2026:
        if salario <= teto:
            return (teto, aliq)
    return FAIXAS_INSS_2026[-1]


def obter_faixa_irrf(base_calculo: Decimal) -> tuple:
    """
    Retorna a faixa de IRRF correspondente à base de cálculo.
    
    Args:
        base_calculo: Base para cálculo em Decimal
    
    Returns:
        Tupla: (limite_teto, alíquota, parcela_deduzir)
    """
    for teto, aliq, parcela in FAIXAS_IRRF_2026:
        if base_calculo <= teto:
            return (teto, aliq, parcela)
    return FAIXAS_IRRF_2026[-1]
