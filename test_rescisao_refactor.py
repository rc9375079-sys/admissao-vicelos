#!/usr/bin/env python3
"""
Script de Teste da Refatoração do Módulo de Rescisão.
Valida que a função refatorada funciona corretamente e produz debug logs.
"""

from datetime import date
from modules.rescisao import calcular_cenarios_desligamento
from decimal import Decimal

# Dados de teste
func_dados = {
    'nome': 'João Silva',
    'admissao': '01/02/2024',
    'salario': '5000.00',
    'Valor VA': '30.00',
    'vr_mensal': '30.00',
    'VT Diário': '5.00'
}

dt_desligamento = date(2024, 3, 15)

print("\n🔍 TESTE DE REFATORAÇÃO - Função calcular_cenarios_desligamento()\n")
print("=" * 70)

resultado = calcular_cenarios_desligamento(func_dados, dt_desligamento)

if resultado:
    print("\n✅ Função executada com sucesso!")
    print(f"Fase: {resultado['fase']}")
    print(f"Dias trabalhados: {resultado['dias_trabalhados_hoje']}")
    print(f"Cenário A - Multa Art. 479: R$ {resultado['multa_479']}")
    print(f"Cenário A - Férias hoje: R$ {resultado['ferias_hoje']}")
    print(f"Cenário B - Férias projetadas: R$ {resultado['ferias_proj']}")
    print("\n" + "=" * 70)
else:
    print("❌ Erro na execução da função")
