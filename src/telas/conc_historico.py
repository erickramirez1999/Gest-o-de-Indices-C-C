"""Conciliação · Histórico (o que foi salvo, por data)."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from src.banco import repo_conciliacao
from src.servicos.conciliacao import gerar_xlsx_conciliacao
from src.utils.marca import AZUL_ESCURO
from src.utils.formatadores import formatar_brl


def _data_br(iso):
    try:
        y, m, d = str(iso)[:10].split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return str(iso)


def renderizar_conc_historico(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>📚 Conciliação · Histórico</h1>", unsafe_allow_html=True)

    regs = repo_conciliacao.listar_conciliacoes()
    if not regs:
        st.info("📭 Nenhuma conciliação salva ainda. Rode o **Processo 1** e clique em salvar.")
        return

    tabela = []
    for r in regs:
        tabela.append({
            "Data": _data_br(r["data_conciliacao"]),
            "QR Boleto": formatar_brl(r.get("valor_qrboleto") or 0),
            "PDV": formatar_brl(r.get("valor_pdv") or 0),
            "CobCloud": formatar_brl(r.get("valor_cobcloud") or 0),
            "Boleto CB": formatar_brl(r.get("valor_boletocb") or 0),
            "Sobrando": formatar_brl(r.get("valor_sobra") or 0),
            "Qtd sobra": int(r.get("qtd_sobra") or 0),
        })
    st.dataframe(pd.DataFrame(tabela), use_container_width=True, hide_index=True)

    st.markdown("### Ver uma conciliação")
    opcoes = {f"{_data_br(r['data_conciliacao'])}": r for r in regs}
    sel = st.selectbox("Data", list(opcoes.keys()))
    r = opcoes[sel]
    resumo = [
        {"tipo": "QR Boleto", "qtd": int(r.get("qtd_qrboleto") or 0), "valor": float(r.get("valor_qrboleto") or 0)},
        {"tipo": "PDV", "qtd": int(r.get("qtd_pdv") or 0), "valor": float(r.get("valor_pdv") or 0)},
        {"tipo": "CobCloud", "qtd": int(r.get("qtd_cobcloud") or 0), "valor": float(r.get("valor_cobcloud") or 0)},
        {"tipo": "Boleto Cód Barras", "qtd": int(r.get("qtd_boletocb") or 0), "valor": float(r.get("valor_boletocb") or 0)},
        {"tipo": "Sobrando (Monday)", "qtd": int(r.get("qtd_sobra") or 0), "valor": float(r.get("valor_sobra") or 0)},
    ]
    sobra_raw = repo_conciliacao.buscar_sobra(r["id"])
    sobra = [{"data": s.get("data"), "historico": s.get("historico"), "valor": float(s.get("valor") or 0)} for s in sobra_raw]
    desp_raw = repo_conciliacao.buscar_despesa(r["id"])
    despesas = sorted([{"data": d.get("data"), "historico": d.get("historico"), "valor": float(d.get("valor") or 0)}
                       for d in desp_raw], key=lambda d: d["valor"])
    aplic_raw = repo_conciliacao.buscar_aplicacao(r["id"])
    aplicacoes = sorted([{"data": a.get("data"), "historico": a.get("historico"), "valor": float(a.get("valor") or 0)}
                         for a in aplic_raw], key=lambda d: d["valor"])
    ambiguos = repo_conciliacao.buscar_ambigua(r["id"])

    metricas = [(x["tipo"], formatar_brl(x["valor"]), f"{x['qtd']} lçtos") for x in resumo]
    metricas.append(("Despesas", formatar_brl(r.get("valor_despesa") or 0), f"{int(r.get('qtd_despesa') or 0)} saídas"))
    metricas.append(("Aplicações", formatar_brl(r.get("valor_aplicacao") or 0), f"{int(r.get('qtd_aplicacao') or 0)} mov."))
    cols = st.columns(len(metricas))
    for col, (t, val, sub) in zip(cols, metricas):
        col.metric(t, val, sub)

    if sobra:
        df = pd.DataFrame(sobra)
        df["valor"] = df["valor"].map(formatar_brl)
        df.columns = ["Data", "Histórico", "Valor"]
        st.markdown("**PIX sobrando (Monday)**")
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)

    if despesas:
        dd = pd.DataFrame(despesas)
        dd["valor"] = dd["valor"].map(formatar_brl)
        dd.columns = ["Data", "Histórico", "Valor"]
        st.markdown("**🔴 Despesas (saídas do extrato)**")
        st.dataframe(dd, use_container_width=True, hide_index=True, height=280)

    if aplicacoes:
        da = pd.DataFrame(aplicacoes)
        da["valor"] = da["valor"].map(formatar_brl)
        da.columns = ["Data", "Histórico", "Valor"]
        st.markdown("**🟡 Aplicações (movimentação financeira)**")
        st.dataframe(da, use_container_width=True, hide_index=True, height=140)

    if ambiguos:
        st.markdown("**🟡 PIX ambíguos (só um sobra — não somar os dois)**")
        linhas = [{"Valor": formatar_brl(g["valor"]), "Sobrando": f'{g["conta"]} de {len(g["candidatos"])}',
                   "Candidatos": "   |   ".join(f'{c["data"]} · {c["historico"]}' for c in g["candidatos"])}
                  for g in ambiguos]
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    xlsx = gerar_xlsx_conciliacao(resumo, sobra, sel, despesas=despesas, aplicacoes=aplicacoes,
                                  sobra_ambigua=ambiguos)
    st.download_button("📥 Baixar planilha desta conciliação", data=xlsx,
                       file_name=f"Conciliacao_{r['data_conciliacao']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
