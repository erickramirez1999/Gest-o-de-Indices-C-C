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
    callback_progresso=None,
) -> dict:
    """
    Insere/atualiza cadastros em lote.

    Cada registro deve ter:
      - cod_parceiro (int)
      - nome_parceiro (str)
      - canal_origem (str ou None)
      - data_cadastramento (date)

    Retorna dict com: criados, atualizados, ignorados, total, erros
    """
    if not registros:
        return {"criados": 0, "atualizados": 0, "ignorados": 0, "total": 0, "erros": []}

    sb = obter_conexao()

    # Lista códigos de parceiros já existentes (em lotes pra evitar URL muito grande)
    cods = list({int(r["cod_parceiro"]) for r in registros if r.get("cod_parceiro")})
    existentes_set = set()
    for i in range(0, len(cods), 500):
        chunk = cods[i:i + 500]
        try:
            res = (sb.table("dados_cadastros")
                   .select("cod_parceiro")
                   .in_("cod_parceiro", chunk)
                   .execute())
            existentes_set.update(r["cod_parceiro"] for r in (res.data or []))
        except Exception:
            pass

    criados = 0
    atualizados = 0
    ignorados = 0
    erros_detalhe = []

    # Sanitiza e monta payload
    def _sanitizar_texto(s):
        """Remove caracteres que quebram JSON: NUL, controle, etc."""
        if s is None or (isinstance(s, float) and pd.isna(s)):
            return None
        s = str(s)
        # Remove NUL e caracteres de controle exceto \n, \r, \t
        s = "".join(c for c in s if c == "\n" or c == "\r" or c == "\t" or ord(c) >= 32)
        return s.strip() or None

    lote = []
    for r in registros:
        if not r.get("cod_parceiro") or not r.get("data_cadastramento"):
            ignorados += 1
            continue

        # Trata data
        data = r["data_cadastramento"]
        if hasattr(data, "date"):
            data_iso = data.date().isoformat()
        elif hasattr(data, "isoformat"):
            data_iso = data.isoformat()
        else:
            data_iso = str(data)

        # Trata canal — vira None se for NaN/vazio
        canal_raw = r.get("canal_origem")
        if canal_raw is None or (isinstance(canal_raw, float) and pd.isna(canal_raw)):
            canal = None
        else:
            canal = _sanitizar_texto(canal_raw)

        nome = _sanitizar_texto(r.get("nome_parceiro")) or "(sem nome)"

        payload = {
            "cod_parceiro": int(r["cod_parceiro"]),
            "nome_parceiro": nome[:500],   # limita a 500 chars por garantia
            "canal_origem": canal,
            "data_cadastramento": data_iso,
            "nome_arquivo_origem": _sanitizar_texto(nome_arquivo_origem),
            "criado_por_id": int(criado_por_id) if criado_por_id else None,
        }
        lote.append(payload)

        if int(r["cod_parceiro"]) in existentes_set:
            atualizados += 1
        else:
            criados += 1

    # Upsert em LOTES PEQUENOS (100 por vez)
    # NÃO faz fallback 1-a-1: se um lote falhar, tenta o próximo.
    # No fim, conta no banco quantos realmente entraram pra ter números corretos.
    if lote:
        TAMANHO_LOTE = 100
        total_lotes = (len(lote) + TAMANHO_LOTE - 1) // TAMANHO_LOTE
        lotes_falhados_seguidos = 0
        primeiro_erro_lote = None
        lotes_falhos = 0

        for idx_lote, i in enumerate(range(0, len(lote), TAMANHO_LOTE)):
            chunk = lote[i:i + TAMANHO_LOTE]

            if callback_progresso:
                callback_progresso(idx_lote + 1, total_lotes, len(chunk))

            try:
                sb.table("dados_cadastros").upsert(chunk, on_conflict="cod_parceiro").execute()
                lotes_falhados_seguidos = 0
            except Exception as e:
                lotes_falhados_seguidos += 1
                lotes_falhos += 1
                if primeiro_erro_lote is None:
                    primeiro_erro_lote = str(e)[:500]
                    # Guarda info do primeiro lote falho pra diagnóstico
                    erros_detalhe.append({
                        "cod_parceiro": f"Lote {idx_lote+1} ({chunk[0]['cod_parceiro']}..{chunk[-1]['cod_parceiro']})",
                        "nome": f"{len(chunk)} linhas",
                        "erro": str(e)[:300],
                    })

                # Se 3 lotes seguidos falharem, é erro sistêmico — para
                if lotes_falhados_seguidos >= 3:
                    erros_detalhe.append({
                        "cod_parceiro": "PARADO",
                        "nome": f"3 lotes seguidos falharam, abortando",
                        "erro": primeiro_erro_lote,
                    })
                    break

        # Conta REAL no banco pra ter números precisos
        try:
            total_no_banco = sb.table("dados_cadastros").select("id", count="exact").execute()
            qtd_real = total_no_banco.count or 0
        except Exception:
            qtd_real = -1

        # Recalcula criados/atualizados com base no que está no banco vs o que existia antes
        criados_real = qtd_real - len(existentes_set) if qtd_real >= 0 else criados
        atualizados_real = max(0, (len(lote) - lotes_falhos * TAMANHO_LOTE) - criados_real)

        return {
            "criados": max(0, criados_real),
            "atualizados": max(0, atualizados_real),
            "ignorados": ignorados,
            "total": len(registros),
            "erros": erros_detalhe,
            "lotes_falhos": lotes_falhos,
            "total_no_banco": qtd_real,
        }

    # Sem nenhum lote pra processar
    return {
        "criados": criados,
        "atualizados": atualizados,
        "ignorados": ignorados,
        "total": len(registros),
        "erros": erros_detalhe,
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
