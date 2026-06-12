"""
Repositório de Cadastros.

CRUD pra cadastros do Sankhya com canal de origem.
- Upload em lote (planilha xlsx do Sankhya)
- Listagens agregadas (por canal, por mês, por ano)
- Upsert por código de parceiro (1 cadastro = 1 parceiro)
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from src.banco.conexao import obter_conexao


# ============================================================
# CANAIS DE ORIGEM (taxonomia LLE)
# ============================================================

CANAIS_ORIGEM = {
    "KING OURO":       {"cor": "#FAC318", "emoji": "👑"},
    "LLE":             {"cor": "#041747", "emoji": "🏢"},
    "LLE CONSTRUTORA": {"cor": "#0F8C3B", "emoji": "🏗️"},
    "TRIO":            {"cor": "#7B1FA2", "emoji": "🔺"},
    "(sem canal)":     {"cor": "#9E9E9E", "emoji": "❓"},
}


def cor_canal(canal: Optional[str]) -> str:
    return CANAIS_ORIGEM.get(canal or "(sem canal)", {}).get("cor", "#9E9E9E")


def emoji_canal(canal: Optional[str]) -> str:
    return CANAIS_ORIGEM.get(canal or "(sem canal)", {}).get("emoji", "❓")


# ============================================================
# UPSERT EM LOTE
# ============================================================

def upsert_cadastros_em_lote(
    registros: list[dict],
    nome_arquivo_origem: Optional[str] = None,
    criado_por_id: Optional[int] = None,
) -> dict:
    """
    Insere/atualiza cadastros em lote.

    Cada registro deve ter:
      - cod_parceiro (int)
      - nome_parceiro (str)
      - canal_origem (str ou None)
      - data_cadastramento (date)

    Retorna dict com: criados, atualizados, ignorados, total
    """
    if not registros:
        return {"criados": 0, "atualizados": 0, "ignorados": 0, "total": 0}

    sb = obter_conexao()

    # Lista códigos de parceiros já existentes
    cods = list({r["cod_parceiro"] for r in registros if r.get("cod_parceiro")})
    existentes_res = (sb.table("dados_cadastros")
                      .select("cod_parceiro")
                      .in_("cod_parceiro", cods)
                      .execute())
    existentes_set = {r["cod_parceiro"] for r in (existentes_res.data or [])}

    criados = 0
    atualizados = 0
    ignorados = 0

    # Processa em lotes de 500 (Supabase tem limites)
    lote = []
    for r in registros:
        if not r.get("cod_parceiro") or not r.get("data_cadastramento"):
            ignorados += 1
            continue

        payload = {
            "cod_parceiro": int(r["cod_parceiro"]),
            "nome_parceiro": str(r["nome_parceiro"] or "").strip(),
            "canal_origem": (str(r["canal_origem"]).strip()
                             if r.get("canal_origem") and pd.notna(r["canal_origem"])
                             else None),
            "data_cadastramento": (r["data_cadastramento"].isoformat()
                                   if hasattr(r["data_cadastramento"], "isoformat")
                                   else str(r["data_cadastramento"])),
            "nome_arquivo_origem": nome_arquivo_origem,
            "criado_por_id": criado_por_id,
        }
        lote.append(payload)

        if r["cod_parceiro"] in existentes_set:
            atualizados += 1
        else:
            criados += 1

    if lote:
        # Upsert por cod_parceiro
        sb.table("dados_cadastros").upsert(lote, on_conflict="cod_parceiro").execute()

    return {
        "criados": criados,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "total": len(registros),
    }


# ============================================================
# LISTAGEM / DASHBOARD
# ============================================================

def listar_cadastros() -> list[dict]:
    sb = obter_conexao()
    res = (sb.table("dados_cadastros")
           .select("*")
           .order("data_cadastramento", desc=True)
           .execute())
    return res.data or []


def excluir_cadastros_em_lote(ids: list[int]) -> int:
    """Remove uma lista de cadastros pelo ID."""
    if not ids:
        return 0
    sb = obter_conexao()
    res = sb.table("dados_cadastros").delete().in_("id", ids).execute()
    return len(res.data) if res.data else 0


def excluir_todos_cadastros() -> int:
    """Limpa toda a tabela. Operação destrutiva."""
    sb = obter_conexao()
    res = sb.table("dados_cadastros").delete().neq("id", 0).execute()
    return len(res.data) if res.data else 0
