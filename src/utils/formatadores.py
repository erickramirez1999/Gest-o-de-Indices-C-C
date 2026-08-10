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
    """Formata minutos como dias/horas/min (e segundos abaixo de 1 min)."""
    try:
        total = float(minutos)
        if total <= 0:
            return "0 min"
        if total < 1:  # menos de 1 minuto → segundos
            return f"{int(round(total * 60))}s"
        m = int(round(total))
        d, resto = divmod(m, 1440)
        h, mn = divmod(resto, 60)
        partes = []
        if d:
            partes.append(f"{d}d")
        if h:
            partes.append(f"{h}h")
        if mn or not partes:
            partes.append(f"{mn}min")
        return " ".join(partes)
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
