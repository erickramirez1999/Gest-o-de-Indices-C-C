"""
Repositório de Inadimplência — Supabase.

Um snapshot por mês (mes_ano escolhido no upload), com dois grupos:
PISA e KING_TRIO. Ao salvar, substitui só os grupos presentes no envio.
Insert e select paginados (aguenta milhares de linhas).
"""
from __future__ import annotations
from typing import Optional

from src.banco.conexao import obter_conexao

AREA = "INADIMPLENCIA"
TABELA = "dados_inadimplencia"
CAMPOS = (
    "grupo", "posicao", "cod_cliente", "nome_cliente", "valor_em_aberto",
    "situacao", "tem_quebra", "tem_protesto", "terceirizada",
    "acordo_parcelas", "acordo_periodicidade", "acordo_valor_parcela",
    "acordo_responsavel", "acordo_data",
)


def _usuario_valido(usuario_id) -> Optional[int]:
    if usuario_id is None:
        return None
    try:
        r = obter_conexao().table("usuario").select("id").eq("id", usuario_id).execute()
        return usuario_id if r.data else None
    except Exception:
        return None


def salvar_inadimplencia(mes_ano: str, data_referencia: Optional[str],
                         registros: list[dict], usuario_id=None) -> int:
    if not registros:
        raise ValueError("Nenhum registro para gravar.")
    sb = obter_conexao()
    uid = _usuario_valido(usuario_id)

    ex = sb.table("upload_mes").select("id").eq("area", AREA).eq("mes_ano", mes_ano).execute()
    if ex.data:
        upload_id = ex.data[0]["id"]
        sb.table("upload_mes").update({"enviado_por_id": uid}).eq("id", upload_id).execute()
    else:
        r = sb.table("upload_mes").insert({
            "area": AREA, "mes_ano": mes_ano,
            "nome_arquivo": "inadimplencia", "enviado_por_id": uid,
        }).execute()
        upload_id = r.data[0]["id"]

    # substitui só os grupos que vieram
    grupos = {r["grupo"] for r in registros if r.get("grupo")}
    for g in grupos:
        sb.table(TABELA).delete().eq("mes_ano", mes_ano).eq("grupo", g).execute()

    linhas = []
    for r in registros:
        linha = {c: r.get(c) for c in CAMPOS}
        linha["upload_id"] = upload_id
        linha["mes_ano"] = mes_ano
        linha["data_referencia"] = data_referencia
        linhas.append(linha)

    for i in range(0, len(linhas), 500):
        sb.table(TABELA).insert(linhas[i:i + 500]).execute()
    return upload_id


def listar_referencias() -> list[str]:
    sb = obter_conexao()
    try:
        # pagina só a coluna mes_ano
        vistos, off, page = set(), 0, 1000
        while True:
            r = sb.table(TABELA).select("mes_ano").range(off, off + page - 1).execute()
            if not r.data:
                break
            vistos.update(x["mes_ano"] for x in r.data if x.get("mes_ano"))
            if len(r.data) < page:
                break
            off += page
        return sorted(vistos, reverse=True)
    except Exception:
        return []


def buscar_inadimplencia(mes_ano: Optional[str] = None) -> list[dict]:
    sb = obter_conexao()
    if mes_ano is None:
        refs = listar_referencias()
        if not refs:
            return []
        mes_ano = refs[0]
    todos, off, page = [], 0, 1000
    while True:
        r = sb.table(TABELA).select("*").eq("mes_ano", mes_ano).range(off, off + page - 1).execute()
        if not r.data:
            break
        todos += r.data
        if len(r.data) < page:
            break
        off += page
    return todos


def contar_inadimplencia() -> int:
    try:
        r = obter_conexao().table(TABELA).select("id", count="exact").limit(1).execute()
        return r.count or 0
    except Exception:
        return 0


# ============================================================
# SITUAÇÃO MANUAL (sobrepõe a classificação automática)
# ============================================================

TABELA_MANUAL = "inadimplencia_situacao_manual"


def buscar_situacoes_manuais(mes_ano: str) -> dict:
    """Retorna {cod_cliente: situacao} com os ajustes manuais do mês."""
    sb = obter_conexao()
    try:
        r = sb.table(TABELA_MANUAL).select("cod_cliente, situacao").eq("mes_ano", mes_ano).execute()
        return {str(x["cod_cliente"]): x["situacao"] for x in (r.data or [])}
    except Exception:
        return {}


def salvar_situacao_manual(mes_ano: str, cod_cliente: str, situacao: str, usuario_id=None) -> None:
    """Grava/atualiza o ajuste manual de um cliente (upsert por mes_ano+cod_cliente)."""
    sb = obter_conexao()
    uid = _usuario_valido(usuario_id)
    sb.table(TABELA_MANUAL).upsert({
        "mes_ano": mes_ano,
        "cod_cliente": str(cod_cliente),
        "situacao": situacao,
        "editado_por_id": uid,
    }, on_conflict="mes_ano,cod_cliente").execute()


def remover_situacao_manual(mes_ano: str, cod_cliente: str) -> None:
    """Remove o ajuste manual (volta a valer o automático)."""
    sb = obter_conexao()
    sb.table(TABELA_MANUAL).delete().eq("mes_ano", mes_ano).eq("cod_cliente", str(cod_cliente)).execute()
