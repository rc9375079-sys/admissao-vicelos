"""
Módulo de Formatação de Valores para Exibição.

Contém funções para formatar moedas, datas e outros valores
conforme padrão PT-BR (localização Brasil).
"""

from decimal import Decimal
from datetime import date, datetime
from typing import Union


def formatar_moeda(valor: Union[str, int, float, Decimal]) -> str:
    """
    Formata um valor numérico como moeda em Real (R$ 1.234,56).
    
    Padrão PT-BR:
    - Separador de milhares: ponto (.)
    - Separador decimal: vírgula (,)
    - Retorna string com format R$ XYZW,AB
    
    Args:
        valor: Valor a formatar (string, int, float ou Decimal)
    
    Returns:
        String formatada como moeda (ex: "1.234,56")
    
    Example:
        >>> formatar_moeda("1234.56")
        '1.234,56'
        >>> formatar_moeda(Decimal("5000.00"))
        '5.000,00'
    """
    if not valor or valor == 0 or valor == "0,00":
        return "0,00"
    
    # Converter para Decimal se for string ou número
    if isinstance(valor, str):
        try:
            # Tentar remover formatação anterior se houver
            valor_limpo = valor.replace("R$", "").replace(".", "").replace(",", ".").strip()
            valor = Decimal(valor_limpo)
        except:
            return "0,00"
    elif isinstance(valor, (int, float)):
        valor = Decimal(str(valor))
    
    if not isinstance(valor, Decimal):
        return "0,00"
    
    # Formatar com separador de milhares (ponto) e decimal (vírgula)
    formatado = f"{valor:,.2f}"  # Usa ponto como separador de milhares
    formatado = formatado.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
    
    return formatado


def formatar_data(data: Union[str, date, datetime], formato: str = "%d/%m/%Y") -> str:
    """
    Formata uma data conforme padrão PT-BR (DD/MM/AAAA).
    
    Args:
        data: Data a formatar (string, date ou datetime)
        formato: Formato desejado (default: "%d/%m/%Y")
    
    Returns:
        String formatada da data
    
    Example:
        >>> from datetime import date
        >>> formatar_data(date(2024, 3, 15))
        '15/03/2024'
    """
    if isinstance(data, str):
        try:
            # Tentar parsear como ISO primeiro
            data = datetime.fromisoformat(data).date()
        except:
            # Se falhar, tentar parsear como DD/MM/AAAA
            try:
                data = datetime.strptime(data, "%d/%m/%Y").date()
            except:
                return data
    
    if isinstance(data, datetime):
        data = data.date()
    
    if isinstance(data, date):
        return data.strftime(formato)
    
    return str(data)
