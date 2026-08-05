"""Repositório da Conciliação — Supabase."""
from __future__ import annotations
from src.banco.conexao import obter_conexao

TAB = "conciliacao"
TAB_SOBRA = "conciliacao_sobra"

# tipo do resumo -> sufixo da coluna no header
COL = {
    "QR Boleto": "qrboleto", "PDV": "pdv", "CobCloud": "cobcloud",
    "Boleto Cód Barras": "boletocb", "Transferência entre contas": "transfconta",
    "TED": "ted", "DOC": "doc", "Sobrando (Monday)": "sobra",
    "Despesas": "despesa", "Tarifas": "tarifa", "Aplicação": "aplicacao",
}


def _usuario_valido(uid):
    if uid is None:
        return None
    try:
        r = obter_conexao().table("usuario").select("id").eq("id", uid).execute()
        return uid if r.data else None
    except Exception:
        return None


def salvar_conciliacao(data_conciliacao: str, resumo: list[dict], sobra: list[dict],
                       usuario_id=None, sobra_ambigua: list[dict] | None = None, **_ignore) -> int:
    sb = obter_conexao()
    uid = _usuario_valido(usuario_id)
    sobra_ambigua = sobra_ambigua or []

    header = {"data_conciliacao": data_conciliacao, "criado_por_id": uid}
    for x in resumo:
        col = COL.get(x["tipo"])
        if not col:
            continue
        header[f"qtd_{col}"] = int(x.get("qtd") or 0)
        header[f"valor_{col}"] = float(x.get("valor") or 0)

    ex = sb.table(TAB).select("id").eq("data_conciliacao", data_conciliacao).execute()
    if ex.data:
        sb.table(TAB).delete().eq("id", ex.data[0]["id"]).execute()
    cid = sb.table(TAB).insert(header).execute().data[0]["id"]

    # só guardamos detalhe do que sobra (claros + ambíguos), já com a origem identificada
    linhas = [{"conciliacao_id": cid, "tipo": "SOBRA", "data": s["data"], "historico": s["historico"],
               "valor": float(s["valor"]), "cod_parceiro": (str(s["cod"]) if s.get("cod") else None),
               "nome_parceiro": s.get("nome") or None, "nota": (str(s["nota"]) if s.get("nota") else None)}
              for s in sobra]
    for g in sobra_ambigua:
        ident = g.get("ident", [])
        for k, cand in enumerate(g["candidatos"]):
            fr = ident[k] if k < len(ident) else None
            linhas.append({"conciliacao_id": cid, "tipo": "AMBIGUA", "conta": int(g["conta"]),
                           "data": cand["data"], "historico": cand["historico"], "valor": float(g["valor"]),
                           "cod_parceiro": (str(fr["cod"]) if fr else None),
                           "nome_parceiro": (fr["nome"] if fr else None),
                           "nota": (str(fr["nota"]) if fr else None)})
    for i in range(0, len(linhas), 500):
        if linhas[i:i + 500]:
            sb.table(TAB_SOBRA).insert(linhas[i:i + 500]).execute()
    return cid


def listar_conciliacoes() -> list[dict]:
    sb = obter_conexao()
    try:
        return sb.table(TAB).select("*").order("data_conciliacao", desc=True).execute().data or []
    except Exception:
        return []


def reconstruir_resumo(r: dict) -> list[dict]:
    """Monta o resumo (na ordem) a partir das colunas do header."""
    ordem = ["QR Boleto", "PDV", "CobCloud", "Boleto Cód Barras", "Transferência entre contas",
             "TED", "DOC", "Sobrando (Monday)", "Despesas", "Tarifas", "Aplicação"]
    out = []
    for tipo in ordem:
        col = COL[tipo]
        out.append({"tipo": tipo, "qtd": int(r.get(f"qtd_{col}") or 0), "valor": float(r.get(f"valor_{col}") or 0)})
    return out


def buscar_sobra(conciliacao_id: int) -> list[dict]:
    rows = _buscar_detalhe(conciliacao_id, "SOBRA")
    return [{"data": r.get("data"), "historico": r.get("historico"), "valor": float(r.get("valor") or 0),
             "cod": r.get("cod_parceiro"), "nome": r.get("nome_parceiro"), "nota": r.get("nota")} for r in rows]


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
