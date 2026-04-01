"""
Motor de Cálculo - Folha de Pagamento 2026.

Módulo responsável por calcular INSS, IRRF e salário líquido
com conformidade às leis trabalhistas brasileiras 2026.

Todos os cálculos incluem DEBUG logs para auditoria completa.

Funções Principais:
- calcular_inss(salario_bruto: float) → float
- calcular_irrf(salario_bruto: float, inss_descontado: float, dependentes: int) → float
- calcular_liquido_folha(salario_bruto: float, dependentes: int, outros_descontos: float) → dict
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple
from modules.constants import (
    FAIXAS_INSS_2026,
    TETO_INSS,
    FAIXAS_IRRF_2026,
    DEDUCAO_POR_DEPENDENTE_IRRF,
    LIMITE_RENDIMENTO_ISENCAO,
    LIMITE_RENDIMENTO_REDUTOR,
    COEFICIENTE_REDUTOR_IRRF,
    PARCELA_REDUTOR_IRRF,
    DEDUCTIBLE_SIMPLIFICADO_IRRF,
    ALIQUOTA_FGTS_EMPREGADOR,
)


# ===============================================================
# FUNÇÕES DE CONVERSÃO E FORMATTING
# ===============================================================

def _to_decimal(valor) -> Decimal:
    """Converte valor variado para Decimal."""
    if isinstance(valor, Decimal):
        return valor
    try:
        return Decimal(str(valor))
    except:
        return Decimal("0.00")


def _format_debug_valor(descricao: str, valor: Decimal) -> None:
    """Imprime DEBUG log formatado."""
    print(f"DEBUG: {descricao} = R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))


# ===============================================================
# CÁLCULO DE INSS
# ===============================================================

def calcular_inss(salario_bruto: float) -> float:
    """
    Calcula INSS com alíquotas progressivas por faixa.
    
    A contribuição é calculada de forma progressiva, aplicando a alíquota
    correspondente a cada faixa de salário. O resultado é sempre limitado
    ao teto máximo estabelecido.
    
    Fonte: INSS 2026 - Tabela Oficial de Alíquotas Progressivas
    
    Fórmulas:
        Faixa 1 (até R$ 1.518,00):      salário × 7,5%
        Faixa 2 (até R$ 2.793,88):      (limite1 × 7,5%) + (excedente × 9,0%)
        Faixa 3 (até R$ 4.190,83):      (faixas anteriores) + (excedente × 12,0%)
        Faixa 4 (até R$ 8.157,41):      (faixas anteriores) + (excedente × 14,0%)
        
        * Limite máximo (teto): R$ 1.164,86
    
    Args:
        salario_bruto: Salário bruto em float (ex: 5000.50)
    
    Returns:
        Valor do INSS em float, limitado ao teto
    
    Example:
        >>> calcular_inss(5000.0)
        562.41
    """
    bruto = _to_decimal(salario_bruto)
    desconto_inss = Decimal("0.00")
    faixa_anterior = Decimal("0.00")
    
    print(f"\n--- CÁLCULO INSS ---")
    print(f"Salário Bruto: R$ {bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    for i, (teto_faixa, aliquota) in enumerate(FAIXAS_INSS_2026, 1):
        if bruto > faixa_anterior:
            # Calcular a porção do salário nesta faixa
            base_faixa = min(bruto, teto_faixa) - faixa_anterior
            desconto_faixa = base_faixa * aliquota
            desconto_inss += desconto_faixa
            
            print(f"  Faixa {i}: R$ {faixa_anterior:,.2f} a R$ {teto_faixa:,.2f} | Aliq. {aliquota * 100}% | Desc. R$ {desconto_faixa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            faixa_anterior = teto_faixa
        else:
            break
    
    # Aplicar teto máximo
    if desconto_inss > TETO_INSS:
        print(f"  ⚠️  Desconto acima do teto ({desconto_inss}), limitando a {TETO_INSS}")
        desconto_inss = TETO_INSS
    
    desconto_inss_final = desconto_inss.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"✓ INSS Total: R$ {desconto_inss_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    return float(desconto_inss_final)


# ===============================================================
# CÁLCULO DE IRRF
# ===============================================================

def calcular_irrf(
    salario_bruto: float,
    inss_descontado: float,
    dependentes: int = 0
) -> float:
    """
    Calcula IRRF com alíquotas progressivas, deduções por dependentes
    e aplicação de redutor para renda até R$ 7.350,00 (2026).
    
    Processo:
        1. Base Legal = Bruto - INSS - (Dependentes × R$ 189,59)
        2. Base Simplificada = Bruto - R$ 607,20
        3. Base de Cálculo = Mínimo entre Legal e Simplificada
        4. Aplicar alíquota progressiva + parcela a deduzir
        5. Aplicar redutor para renda até R$ 7.350,00
    
    Fonte: Receita Federal - Tabela Mensal 2026, Lei 9.250/95
    
    Faixas IRRF (sobre a base):
        Até R$ 2.428,80:                    Isento
        R$ 2.428,81 a R$ 2.826,65:          7,5% - R$ 182,16
        R$ 2.826,66 a R$ 3.751,05:          15,0% - R$ 394,16
        R$ 3.751,06 a R$ 4.664,68:          22,5% - R$ 675,49
        Acima de R$ 4.664,68:               27,5% - R$ 908,73
    
    Redutor (2026): Redução gradual para renda entre R$ 5.000 e R$ 7.350
    
    Args:
        salario_bruto: Salário bruto em float (ex: 5000.00)
        inss_descontado: Valor de INSS já descontado em float
        dependentes: Número de dependentes (filhos menores de 14 ou com deficiência)
    
    Returns:
        Valor do IRRF em float
    
    Example:
        >>> calcular_irrf(5000.0, 375.0, 1)
        0.0  # Isento devido ao redutor 2026
    """
    bruto = _to_decimal(salario_bruto)
    inss = _to_decimal(inss_descontado)
    dependentes = int(dependentes)
    
    print(f"\n--- CÁLCULO IRRF ---")
    print(f"Salário Bruto: R$ {bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"INSS Descontado: R$ {inss:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"Dependentes: {dependentes}")
    
    # Calcular base legal
    deducao_dependentes = DEDUCAO_POR_DEPENDENTE_IRRF * Decimal(str(dependentes))
    base_legal = bruto - inss - deducao_dependentes
    
    print(f"  Base Legal = {bruto:,.2f} - {inss:,.2f} - ({deducao_dependentes:,.2f}) = {base_legal:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Calcular base simplificada
    base_simplificada = bruto - DEDUCTIBLE_SIMPLIFICADO_IRRF
    print(f"  Base Simplificada = {bruto:,.2f} - {DEDUCTIBLE_SIMPLIFICADO_IRRF:,.2f} = {base_simplificada:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Base de cálculo é a menor entre legal e simplificada
    base_calculo = min(base_legal, base_simplificada)
    print(f"  Base para Cálculo (menor) = R$ {base_calculo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Verificar isençoes
    if base_calculo <= Decimal("0.00"):
        print(f"✓ IRRF: R$ 0,00 (base negativa/zero)")
        return 0.0
    
    # Regra de redução para renda até R$ 7.350,00 (2026)
    if bruto <= LIMITE_RENDIMENTO_ISENCAO:
        print(f"  ✓ Renda até R$ 5.000: ISENTO (Redutor 2026)")
        return 0.0
    
    # Encontrar faixa de IRRF
    faixa_info = None
    for teto, aliquota, parcela_deduzir in FAIXAS_IRRF_2026:
        if base_calculo <= teto:
            faixa_info = (teto, aliquota, parcela_deduzir)
            break
    
    if not faixa_info:
        faixa_info = FAIXAS_IRRF_2026[-1]
    
    teto_faixa, aliquota, parcela_deduzir = faixa_info
    
    # Calcular imposto bruto
    imposto_bruto = (base_calculo * aliquota) - parcela_deduzir
    imposto_bruto = max(Decimal("0.00"), imposto_bruto)
    
    print(f"  Faixa: até R$ {teto_faixa:,.2f} | Aliq. {aliquota * 100}% | Parcela Deduzir: R$ {parcela_deduzir:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"  Imposto Bruto = ({base_calculo:,.2f} × {aliquota}) - {parcela_deduzir:,.2f} = R$ {imposto_bruto:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    # Aplicar redutor para renda entre R$ 5.000 e R$ 7.350
    imposto_final = imposto_bruto
    if bruto <= LIMITE_RENDIMENTO_REDUTOR:
        reducao = PARCELA_REDUTOR_IRRF - (COEFICIENTE_REDUTOR_IRRF * bruto)
        reducao = max(Decimal("0.00"), reducao)
        imposto_final = max(Decimal("0.00"), imposto_bruto - reducao)
        print(f"  Redução (Renda R$ 5.000 a R$ 7.350): R$ {reducao:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        print(f"  IRRF após Redução: R$ {imposto_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    imposto_final = imposto_final.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    print(f"✓ IRRF Total: R$ {imposto_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    return float(imposto_final)


# ===============================================================
# CÁLCULO DE SALÁRIO LÍQUIDO
# ===============================================================

def calcular_liquido_folha(
    salario_bruto: float,
    dependentes: int = 0,
    outros_descontos: float = 0.0
) -> Dict[str, float]:
    """
    Calcula salário líquido completo com todos os descontos.
    
    Descontos incluídos:
        - INSS (progressivo)
        - IRRF (progressivo com deduções por dependentes e redutor)
        - Outros descontos (VT, VA, adiantamento, etc)
    
    Args:
        salario_bruto: Salário bruto em float
        dependentes: Número de dependentes (default: 0)
        outros_descontos: Outros descontos em float (default: 0.0)
    
    Returns:
        Dicionário com:
        {
            'salario_bruto': float,
            'inss': float,
            'irrf': float,
            'outros_descontos': float,
            'total_descontos': float,
            'salario_liquido': float,
            'dependentes': int,
            'aliquota_efetiva_inss': float,  # (INSS / Bruto) * 100
            'aliquota_efetiva_irrf': float,  # (IRRF / Bruto) * 100
        }
    
    Example:
        >>> resultado = calcular_liquido_folha(5000.0, dependentes=1)
        >>> print(resultado['salario_liquido'])
        4062.59
    """
    bruto = _to_decimal(salario_bruto)
    outros = _to_decimal(outros_descontos)
    
    print(f"\n{'='*70}")
    print(f"CÁLCULO COMPLETO - FOLHA DE PAGAMENTO")
    print(f"{'='*70}")
    
    # Passo 1: Calcular INSS
    inss = _to_decimal(calcular_inss(float(bruto)))
    
    # Passo 2: Calcular IRRF
    irrf = _to_decimal(calcular_irrf(float(bruto), float(inss), dependentes))
    
    # Passo 3: Calcular total de descontos
    total_descontos = inss + irrf + outros
    
    # Passo 4: Calcular salário líquido
    salario_liquido = bruto - total_descontos
    
    # Alíquotas efetivas
    aliq_inss = (inss / bruto * 100) if bruto > 0 else Decimal("0")
    aliq_irrf = (irrf / bruto * 100) if bruto > 0 else Decimal("0")
    
    print(f"\n{'='*70}")
    print(f"RESUMO FINAL")
    print(f"{'='*70}")
    print(f"Salário Bruto:          R$ {bruto:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"  INSS ({aliq_inss:.2f}%):          R$ {inss:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"  IRRF ({aliq_irrf:.2f}%):          R$ {irrf:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"  Outros Descontos:      R$ {outros:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"{'─'*70}")
    print(f"Total de Descontos:     R$ {total_descontos:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"{'='*70}")
    print(f"SALÁRIO LÍQUIDO:        R$ {salario_liquido:>10,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"{'='*70}")
    
    # Preparar resultado
    resultado = {
        'salario_bruto': float(bruto),
        'inss': float(inss),
        'irrf': float(irrf),
        'outros_descontos': float(outros),
        'total_descontos': float(total_descontos),
        'salario_liquido': float(salario_liquido),
        'dependentes': dependentes,
        'aliquota_efetiva_inss': float(aliq_inss),
        'aliquota_efetiva_irrf': float(aliq_irrf),
    }
    
    return resultado
