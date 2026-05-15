"""Repositório de uploads e dados mensais — LLE Índices."""
from __future__ import annotations
from typing import Optional
from src.banco.conexao import obter_conexao

import math
import pandas as pd

def _limpar_registro(r: dict) -> dict:
    """Converte tipos numpy/pandas para tipos Python nativos serializáveis."""
    def _v(v):
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        # numpy/pandas numéricos
        if hasattr(v, 'item'):
            v = v.item()
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return None
            # Converte floats inteiros (2.0, 3.0) para int
            if v == int(v):
                return int(v)
            return float(v)
        if isinstance(v, int):
            return int(v)
        if isinstance(v, bool):
            return v
        return str(v) if not isinstance(v, str) else v
    return {k: _v(val) for k, val in r.items()}



# ============================================================
# UPLOADS
# ============================================================

def registrar_upload(area: str, mes_ano: str, nome_arquivo: str, usuario_id: int) -> int:
    """Registra ou substitui o upload de um mês. Retorna o ID."""
    sb = obter_conexao()
    # Remove upload anterior do mesmo mês/área se existir
    ex = sb.table("upload_mes").select("id").eq("area", area).eq("mes_ano", mes_ano).execute()
    if ex.data:
        old_id = ex.data[0]["id"]
        _deletar_dados_do_upload(old_id, area)
        sb.table("upload_mes").delete().eq("id", old_id).execute()

    r = sb.table("upload_mes").insert({
        "area": area,
        "mes_ano": mes_ano,
        "nome_arquivo": nome_arquivo,
        "enviado_por_id": usuario_id,
    }).execute()
    return r.data[0]["id"]


def _deletar_dados_do_upload(upload_id: int, area: str) -> None:
    sb = obter_conexao()
    if area == "COBRANCA":
        sb.table("dados_cobranca_acordo").delete().eq("upload_id", upload_id).execute()
        sb.table("dados_cobranca_baixa").delete().eq("upload_id", upload_id).execute()
        sb.table("dados_cobranca_performance").delete().eq("upload_id", upload_id).execute()
    else:
        sb.table("dados_credito_liberacao").delete().eq("upload_id", upload_id).execute()
        sb.table("dados_credito_limite").delete().eq("upload_id", upload_id).execute()


def listar_meses_disponiveis(area: str) -> list[dict]:
    """Retorna lista de meses com upload, ordenado do mais recente."""
    sb = obter_conexao()
    r = sb.table("upload_mes").select("id,mes_ano,nome_arquivo,enviado_em").eq(
        "area", area
    ).order("mes_ano", desc=True).execute()
    return r.data


def mes_existe(area: str, mes_ano: str) -> bool:
    sb = obter_conexao()
    r = sb.table("upload_mes").select("id").eq("area", area).eq("mes_ano", mes_ano).execute()
    return bool(r.data)


# ============================================================
# COBRANÇA — INSERÇÃO
# ============================================================

def inserir_acordos(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    for i in range(0, len(limpos), 500):
        obter_conexao().table("dados_cobranca_acordo").insert(limpos[i:i+500]).execute()


def inserir_baixas(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    for i in range(0, len(limpos), 500):
        obter_conexao().table("dados_cobranca_baixa").insert(limpos[i:i+500]).execute()


def inserir_performance(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    for i in range(0, len(limpos), 500):
        obter_conexao().table("dados_cobranca_performance").insert(limpos[i:i+500]).execute()


# ============================================================
# CRÉDITO — INSERÇÃO
# ============================================================

def inserir_liberacoes(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    for i in range(0, len(limpos), 500):
        obter_conexao().table("dados_credito_liberacao").insert(limpos[i:i+500]).execute()


def inserir_limites(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    for i in range(0, len(limpos), 500):
        obter_conexao().table("dados_credito_limite").insert(limpos[i:i+500]).execute()


def inserir_tempo_tela(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    limpos = [_limpar_registro({**r, "upload_id": upload_id, "mes_ano": mes_ano}) for r in registros]
    obter_conexao().table("dados_credito_tempo_tela").insert(limpos).execute()


def inserir_limites(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    for r in registros:
        r["upload_id"] = upload_id
        r["mes_ano"] = mes_ano
    obter_conexao().table("dados_credito_limite").insert(registros).execute()


# ============================================================
# COBRANÇA — CONSULTA
# ============================================================

def buscar_acordos(mes_ano: str) -> list[dict]:
    r = obter_conexao().table("dados_cobranca_acordo").select("*").eq("mes_ano", mes_ano).execute()
    return r.data


def buscar_baixas(mes_ano: str) -> list[dict]:
    r = obter_conexao().table("dados_cobranca_baixa").select("*").eq("mes_ano", mes_ano).execute()
    return r.data


def buscar_performance(mes_ano: str) -> list[dict]:
    r = obter_conexao().table("dados_cobranca_performance").select("*").eq("mes_ano", mes_ano).execute()
    return r.data


# ============================================================
# CRÉDITO — CONSULTA
# ============================================================

def buscar_liberacoes(mes_ano: str) -> list[dict]:
    r = obter_conexao().table("dados_credito_liberacao").select("*").eq("mes_ano", mes_ano).execute()
    return r.data


def inserir_tempo_tela(upload_id: int, mes_ano: str, registros: list[dict]) -> None:
    if not registros:
        return
    for r in registros:
        r["upload_id"] = upload_id
        r["mes_ano"] = mes_ano
    obter_conexao().table("dados_credito_tempo_tela").insert(registros).execute()


def buscar_tempo_tela(mes_ano: str) -> list[dict]:
    r = obter_conexao().table("dados_credito_tempo_tela").select("*").eq("mes_ano", mes_ano).execute()
    return r.data
    r = obter_conexao().table("dados_credito_limite").select("*").eq("mes_ano", mes_ano).execute()
    return r.data


# ============================================================
# HISTÓRICO GERAL (todos os meses)
# ============================================================

def historico_cobranca_acordos() -> list[dict]:
    r = obter_conexao().table("dados_cobranca_acordo").select(
        "mes_ano,negociador,valor_total,cancelado,qtd_parcelas"
    ).execute()
    return r.data


def historico_cobranca_baixas() -> list[dict]:
    r = obter_conexao().table("dados_cobranca_baixa").select(
        "mes_ano,cobrador,vlr_liquido,dias_atraso,faixa_aging"
    ).execute()
    return r.data


def historico_credito_liberacoes() -> list[dict]:
    r = obter_conexao().table("dados_credito_liberacao").select(
        "mes_ano,tipo,vlr_pedido,analista"
    ).execute()
    return r.data


def historico_credito_limites() -> list[dict]:
    r = obter_conexao().table("dados_credito_limite").select(
        "mes_ano,variacao,novo_limite,analista"
    ).execute()
    return r.data
