"""Repositório da Conciliação — Supabase."""
from __future__ import annotations
from typing import Optional
from src.banco.conexao import obter_conexao

TAB = "conciliacao"
TAB_SOBRA = "conciliacao_sobra"


def _usuario_valido(uid):
    if uid is None:
        return None
    try:
        r = obter_conexao().table("usuario").select("id").eq("id", uid).execute()
        return uid if r.data else None
    except Exception:
        return None


def salvar_conciliacao(data_conciliacao: str, resumo: list[dict], sobra: list[dict],
                       usuario_id=None, despesas: list[dict] | None = None,
                       aplicacoes: list[dict] | None = None,
                       sobra_ambigua: list[dict] | None = None) -> int:
    """Salva (substitui) a conciliação de uma data. Retorna o id."""
    sb = obter_conexao()
    uid = _usuario_valido(usuario_id)
    despesas = despesas or []
    aplicacoes = aplicacoes or []
    sobra_ambigua = sobra_ambigua or []
    r = {x["tipo"]: x for x in resumo}
    def q(t): return int(r.get(t, {}).get("qtd") or 0)
    def v(t): return float(r.get(t, {}).get("valor") or 0)

    ex = sb.table(TAB).select("id").eq("data_conciliacao", data_conciliacao).execute()
    if ex.data:
        sb.table(TAB).delete().eq("id", ex.data[0]["id"]).execute()

    ins = sb.table(TAB).insert({
        "data_conciliacao": data_conciliacao,
        "qtd_qrboleto": q("QR Boleto"), "valor_qrboleto": v("QR Boleto"),
        "qtd_pdv": q("PDV"), "valor_pdv": v("PDV"),
        "qtd_cobcloud": q("CobCloud"), "valor_cobcloud": v("CobCloud"),
        "qtd_boletocb": q("Boleto Cód Barras"), "valor_boletocb": v("Boleto Cód Barras"),
        "qtd_sobra": q("Sobrando (Monday)"), "valor_sobra": v("Sobrando (Monday)"),
        "qtd_despesa": len(despesas), "valor_despesa": round(sum(float(d["valor"]) for d in despesas), 2),
        "qtd_aplicacao": len(aplicacoes), "valor_aplicacao": round(sum(float(a["valor"]) for a in aplicacoes), 2),
        "criado_por_id": uid,
    }).execute()
    cid = ins.data[0]["id"]

    linhas = [{"conciliacao_id": cid, "tipo": "SOBRA", "data": s["data"],
               "historico": s["historico"], "valor": float(s["valor"])} for s in sobra]
    linhas += [{"conciliacao_id": cid, "tipo": "DESPESA", "data": d["data"],
                "historico": d["historico"], "valor": float(d["valor"])} for d in despesas]
    linhas += [{"conciliacao_id": cid, "tipo": "APLICACAO", "data": a["data"],
                "historico": a["historico"], "valor": float(a["valor"])} for a in aplicacoes]
    for g in sobra_ambigua:
        for cand in g["candidatos"]:
            linhas.append({"conciliacao_id": cid, "tipo": "AMBIGUA", "conta": int(g["conta"]),
                           "data": cand["data"], "historico": cand["historico"], "valor": float(g["valor"])})
    for i in range(0, len(linhas), 500):
        if linhas[i:i + 500]:
            sb.table(TAB_SOBRA).insert(linhas[i:i + 500]).execute()
    return cid


def listar_conciliacoes() -> list[dict]:
    sb = obter_conexao()
    try:
        r = sb.table(TAB).select("*").order("data_conciliacao", desc=True).execute()
        return r.data or []
    except Exception:
        return []


def buscar_sobra(conciliacao_id: int) -> list[dict]:
    return _buscar_detalhe(conciliacao_id, "SOBRA")


def buscar_despesa(conciliacao_id: int) -> list[dict]:
    return _buscar_detalhe(conciliacao_id, "DESPESA")


def buscar_aplicacao(conciliacao_id: int) -> list[dict]:
    return _buscar_detalhe(conciliacao_id, "APLICACAO")


def buscar_ambigua(conciliacao_id: int) -> list[dict]:
    rows = _buscar_detalhe(conciliacao_id, "AMBIGUA")
    grupos = {}
    for r in rows:
        v = round(float(r.get("valor") or 0), 2)
        g = grupos.setdefault(v, {"valor": v, "conta": int(r.get("conta") or 1), "candidatos": []})
        g["candidatos"].append({"data": r.get("data"), "historico": r.get("historico"), "valor": v})
    return sorted(grupos.values(), key=lambda g: -g["valor"])


def _buscar_detalhe(conciliacao_id: int, tipo: str) -> list[dict]:
    sb = obter_conexao()
    todos, off, page = [], 0, 1000
    while True:
        r = (sb.table(TAB_SOBRA).select("*").eq("conciliacao_id", conciliacao_id)
             .eq("tipo", tipo).order("valor", desc=True).range(off, off + page - 1).execute())
        if not r.data:
            break
        todos += r.data
        if len(r.data) < page:
            break
        off += page
    return todos


def contar() -> int:
    try:
        return obter_conexao().table(TAB).select("id", count="exact").limit(1).execute().count or 0
    except Exception:
        return 0
