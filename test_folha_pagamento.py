#!/usr/bin/env python3
"""
Script de Validação - Módulo de Folha de Pagamento
Teste com R$ 5.000,00 e 1 dependente
"""

from modules.folha_pagamento import calcular_inss, calcular_irrf, calcular_liquido_folha

print("\n" + "="*70)
print("✅ TESTE DE VALIDAÇÃO - MÓDULO FOLHA_PAGAMENTO")
print("="*70)

print("\n📋 CENÁRIO DE TESTE:")
print("   Salário Bruto: R$ 5.000,00")
print("   Dependentes: 1")
print("   Outros Descontos: R$ 0,00")

try:
    resultado = calcular_liquido_folha(5000.00, dependentes=1, outros_descontos=0.0)
    
    print("\n" + "="*70)
    print("📊 RESULTADO FINAL:")
    print("="*70)
    print(f"✓ Salário Bruto:       R$ {resultado['salario_bruto']:.2f}".replace(".", ","))
    print(f"✓ INSS (-{resultado['aliquota_efetiva_inss']:.2f}%): R$ {resultado['inss']:.2f}".replace(".", ","))
    print(f"✓ IRRF (-{resultado['aliquota_efetiva_irrf']:.2f}%): R$ {resultado['irrf']:.2f}".replace(".", ","))
    print(f"✓ Salário Líquido:     R$ {resultado['salario_liquido']:.2f}".replace(".", ","))
    print("="*70)
    
    # Validações
    assert resultado['salario_bruto'] == 5000.00, "❌ Bruto incorreto"
    assert resultado['dependentes'] == 1, "❌ Dependentes incorreto"
    assert resultado['inss'] > 0, "❌ INSS não calculado"
    assert resultado['irrf'] == 0.0, "❌ IRRF deveria ser 0 (redutor 2026)"
    assert resultado['salario_liquido'] < resultado['salario_bruto'], "❌ Líquido maior que bruto!"
    
    print("\n✅ TODAS AS VALIDAÇÕES PASSARAM!")
    print("✅ Módulo pronto para integração em app.py")
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
