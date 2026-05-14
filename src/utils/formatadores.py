"""Formatadores de valores — LLE Índices."""
from __future__ import annotations


def formatar_brl(valor) -> str:
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def formatar_inteiro(valor) -> str:
    try:
        return f"{int(valor):,}".replace(",", ".")
    except Exception:
        return "0"


def formatar_pct(valor) -> str:
    try:
        return f"{float(valor):.2f}%"
    except Exception:
        return "0,00%"


def formatar_tempo(minutos) -> str:
    try:
        m = int(float(minutos))
        if m >= 60:
            h = m // 60
            mn = m % 60
            return f"{h}h {mn:02d}min"
        return f"{m} min"
    except Exception:
        return "-"


def nome_mes(mes_ano: str) -> str:
    """Converte '2026-04' em 'Abril/2026'."""
    meses = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março",
        "04": "Abril", "05": "Maio", "06": "Junho",
        "07": "Julho", "08": "Agosto", "09": "Setembro",
        "10": "Outubro", "11": "Novembro", "12": "Dezembro",
    }
    try:
        ano, mes = mes_ano.split("-")
        return f"{meses.get(mes, mes)}/{ano}"
    except Exception:
        return mes_ano
