"""
Repositório de Comparativos Semanais — módulo Crédito.

Salva e recupera comparativos entre 2 semanas (ou outros períodos).
Os dados são serializados em JSON pra não precisar guardar os arquivos.
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd

from src.banco.conexao import obter_conexao


def _df_para_json(df) -> list:
    """Converte um DataFrame em lista de dicts JSON-safe."""
    if df is None or (hasattr(df, "empty") and df.empty):
        return []
    # Converte tipos pandas problemáticos
    df_safe = df.copy()
    for col in df_safe.columns:
        if df_safe[col].dtype == "datetime64[ns]":
            df_safe[col] = df_safe[col].astype(str)
        elif df_safe[col].dtype == "object":
            df_safe[col] = df_safe[col].astype(str).replace("nan", None)
    return df_safe.to_dict(orient="records")


def _json_para_df(lista) -> pd.DataFrame:
    """Converte lista de dicts JSON em DataFrame."""
    if not lista:
        return pd.DataFrame()
    return pd.DataFrame(lista)


def _dados_para_json(dados: dict) -> dict:
    """Converte o dict de dados (vindo do leitor) em estrutura JSON pura."""
    return {
        "passaram_direto": _df_para_json(dados.get("passaram_direto", pd.DataFrame())),
        "liberados": _df_para_json(dados.get("liberados", pd.DataFrame())),
        "negados": _df_para_json(dados.get("negados", pd.DataFrame())),
        "limites": _df_para_json(dados.get("limites", pd.DataFrame())),
        "tempo_tela": _df_para_json(dados.get("tempo_tela", pd.DataFrame())),
        "arquivos_processados": dados.get("arquivos_processados", []),
        "erros": dados.get("erros", []),
    }


def _json_para_dados(dic: dict) -> dict:
    """Reverte de JSON pra dict com DataFrames."""
    return {
        "passaram_direto": _json_para_df(dic.get("passaram_direto", [])),
        "liberados": _json_para_df(dic.get("liberados", [])),
        "negados": _json_para_df(dic.get("negados", [])),
        "limites": _json_para_df(dic.get("limites", [])),
        "tempo_tela": _json_para_df(dic.get("tempo_tela", [])),
        "arquivos_processados": dic.get("arquivos_processados", []),
        "erros": dic.get("erros", []),
    }


def salvar_comparativo(
    titulo: str,
    rotulo_a: str,
    rotulo_b: str,
    dados_a: dict,
    dados_b: dict,
    usuario_id: Optional[int] = None,
    usuario_nome: Optional[str] = None,
) -> int:
    """
    Salva um comparativo no banco e retorna o ID criado.
    """
    sb = obter_conexao()

    # Valida criado_por_id contra a tabela usuario
    criado_por_id_validado = None
    if usuario_id is not None:
        try:
            res_user = sb.table("usuario").select("id").eq("id", int(usuario_id)).limit(1).execute()
            if res_user.data:
                criado_por_id_validado = int(usuario_id)
        except Exception:
            pass

    payload = {
        "titulo": titulo[:200] if titulo else "Comparativo Semanal",
        "rotulo_a": rotulo_a[:100] if rotulo_a else "Período A",
        "rotulo_b": rotulo_b[:100] if rotulo_b else "Período B",
        "dados_a_json": _dados_para_json(dados_a),
        "dados_b_json": _dados_para_json(dados_b),
        "criado_por_id": criado_por_id_validado,
        "criado_por_nome": usuario_nome[:100] if usuario_nome else None,
        "arquivos_a": "\n".join(dados_a.get("arquivos_processados", []))[:1000],
        "arquivos_b": "\n".join(dados_b.get("arquivos_processados", []))[:1000],
    }

    res = sb.table("dados_comparativos_credito").insert(payload).execute()
    if res.data:
        return res.data[0]["id"]
    raise RuntimeError("Erro ao salvar comparativo (banco não retornou ID).")


def listar_comparativos() -> list[dict]:
    """Lista todos os comparativos salvos (sem os JSONs pesados, só metadata)."""
    sb = obter_conexao()
    todos = []
    pagina = 0
    while True:
        inicio = pagina * 200
        fim = inicio + 199
        res = (sb.table("dados_comparativos_credito")
               .select("id, titulo, rotulo_a, rotulo_b, criado_em, criado_por_nome, arquivos_a, arquivos_b")
               .order("criado_em", desc=True)
               .range(inicio, fim)
               .execute())
        chunk = res.data or []
        if not chunk:
            break
        todos.extend(chunk)
        if len(chunk) < 200:
            break
        pagina += 1
        if pagina > 50:
            break
    return todos


def carregar_comparativo(comp_id: int) -> Optional[dict]:
    """Carrega comparativo completo pelo ID, retornando dict pronto pra usar."""
    sb = obter_conexao()
    res = sb.table("dados_comparativos_credito").select("*").eq("id", comp_id).limit(1).execute()
    if not res.data:
        return None
    row = res.data[0]
    return {
        "id": row["id"],
        "titulo": row["titulo"],
        "rotulo_a": row["rotulo_a"],
        "rotulo_b": row["rotulo_b"],
        "criado_em": row["criado_em"],
        "criado_por_nome": row.get("criado_por_nome"),
        "arquivos_a": row.get("arquivos_a"),
        "arquivos_b": row.get("arquivos_b"),
        "dados_a": _json_para_dados(row["dados_a_json"] or {}),
        "dados_b": _json_para_dados(row["dados_b_json"] or {}),
    }


def excluir_comparativo(comp_id: int) -> bool:
    """Remove um comparativo do banco."""
    sb = obter_conexao()
    res = sb.table("dados_comparativos_credito").delete().eq("id", comp_id).execute()
    return bool(res.data)
