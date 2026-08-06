"""Repositório de Atendimento — Supabase."""
from __future__ import annotations
from src.banco.conexao import obter_conexao

TAB = "atendimento"


def _usuario_valido(uid):
    if uid is None:
        return None
    try:
        r = obter_conexao().table("usuario").select("id").eq("id", uid).execute()
        return uid if r.data else None
    except Exception:
        return None


def salvar_atendimentos(registros: list[dict], usuario_id=None) -> int:
    """Substitui os dados dos ANOS presentes no arquivo e insere os novos."""
    if not registros:
        return 0
    sb = obter_conexao()
    uid = _usuario_valido(usuario_id)
    anos = sorted({r["ano"] for r in registros})
    for ano in anos:
        sb.table(TAB).delete().eq("ano", ano).execute()
    linhas = [{"data": r["data"], "mes_ano": r["mes_ano"], "ano": r["ano"],
               "motivo": r["motivo"], "total": int(r["total"]), "criado_por_id": uid}
              for r in registros]
    for i in range(0, len(linhas), 500):
        sb.table(TAB).insert(linhas[i:i + 500]).execute()
    return len(linhas)


def buscar_atendimentos(ano: int | None = None) -> list[dict]:
    sb = obter_conexao()
    todos, off, page = [], 0, 1000
    while True:
        q = sb.table(TAB).select("*")
        if ano is not None:
            q = q.eq("ano", ano)
        r = q.order("data").range(off, off + page - 1).execute()
        if not r.data:
            break
        todos += r.data
        if len(r.data) < page:
            break
        off += page
    return todos


def listar_anos() -> list[int]:
    sb = obter_conexao()
    try:
        anos = set()
        off, page = 0, 1000
        while True:
            r = sb.table(TAB).select("ano").range(off, off + page - 1).execute()
            if not r.data:
                break
            anos.update(x["ano"] for x in r.data)
            if len(r.data) < page:
                break
            off += page
        return sorted(anos, reverse=True)
    except Exception:
        return []


def contar() -> int:
    try:
        return obter_conexao().table(TAB).select("id", count="exact").limit(1).execute().count or 0
    except Exception:
        return 0
