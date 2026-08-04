"""Conciliação · Processo 1 (diária)."""
from __future__ import annotations
from datetime import date

import pandas as pd
import streamlit as st

from src.banco import repo_conciliacao
from src.servicos.conciliacao import processar_conciliacao, gerar_xlsx_conciliacao
from src.utils.marca import AZUL_ESCURO
from src.utils.formatadores import formatar_brl

COR = {"QR Boleto": "#0F8C3B", "PDV": "#0071FE", "CobCloud": "#041747",
       "Boleto Cód Barras": "#0071FE", "Sobrando (Monday)": "#DC3545"}


def renderizar_conc_processo1(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>🔄 Conciliação · Processo 1</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11;border-left:4px solid {AZUL_ESCURO};padding:12px;"
        f"border-radius:6px;margin-bottom:14px;'>Suba os <b>2 arquivos do dia</b>: o <b>extrato bancário</b> "
        f"e a <b>base de recebimentos</b> (com 'Identificador do pagamento'). O sistema classifica QR Boleto, "
        f"PDV e CobCloud, e apura os <b>PIX que sobram</b> (para buscar no Monday).</div>",
        unsafe_allow_html=True)

    arquivos = st.file_uploader("Extrato + base (.xlsx)", type=["xlsx", "xls"],
                                accept_multiple_files=True, key="conc_arqs")
    if not arquivos:
        return

    lista = [(a.getvalue(), a.name) for a in arquivos]
    with st.spinner("Conciliando..."):
        res = processar_conciliacao(lista)

    for e in res["erros"]:
        st.error(e)
    for a in res["arquivos"]:
        st.caption(f"✓ {a}")
    if not res["ok"]:
        return

    st.markdown("### Resumo por tipo")
    cols = st.columns(len(res["resumo"]))
    for col, x in zip(cols, res["resumo"]):
        col.markdown(
            f"<div style='border:1px solid #E8EDF5;border-left:5px solid {COR.get(x['tipo'],'#041747')};"
            f"border-radius:8px;padding:10px 12px;'>"
            f"<div style='font-size:12px;color:#6C757D;font-weight:600'>{x['tipo']}</div>"
            f"<div style='font-size:20px;font-weight:700;color:{COR.get(x['tipo'],'#041747')}'>{formatar_brl(x['valor'])}</div>"
            f"<div style='font-size:11px;color:#6C757D'>{x['qtd']} lançamentos</div></div>",
            unsafe_allow_html=True)

    st.markdown(f"### PIX sobrando (Monday) — {len(res['sobra'])} · {formatar_brl(res['total_sobra'])}")
    df = pd.DataFrame(res["sobra"])
    if not df.empty:
        disp = df.copy()
        disp["valor"] = disp["valor"].map(formatar_brl)
        disp.columns = ["Data", "Histórico", "Valor"]
        st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

    despesas = res.get("despesas", [])
    total_desp = res.get("total_despesa", 0.0)
    st.markdown(f"### 🔴 Despesas — saídas do extrato ({len(despesas)}) · {formatar_brl(total_desp)}")
    st.caption("Saídas em vermelho no extrato, exceto aplicações. Para conferir com o banco.")
    if despesas:
        dd = pd.DataFrame(despesas)
        dd["valor"] = dd["valor"].map(formatar_brl)
        dd.columns = ["Data", "Histórico", "Valor"]
        st.dataframe(dd, use_container_width=True, hide_index=True, height=300)

    aplicacoes = res.get("aplicacoes", [])
    total_aplic = res.get("total_aplicacao", 0.0)
    if aplicacoes:
        st.markdown(f"### 🟡 Aplicações — movimentação financeira ({len(aplicacoes)}) · {formatar_brl(total_aplic)}")
        st.caption("Aplicações/resgates separados das despesas (não são gasto).")
        da = pd.DataFrame(aplicacoes)
        da["valor"] = da["valor"].map(formatar_brl)
        da.columns = ["Data", "Histórico", "Valor"]
        st.dataframe(da, use_container_width=True, hide_index=True, height=140)

    st.markdown("---")
    c1, c2, c3 = st.columns([1, 1, 1])
    data_conc = c1.date_input("Data da conciliação", value=date.today(), format="DD/MM/YYYY")
    data_label = data_conc.strftime("%d/%m/%Y")

    xlsx = gerar_xlsx_conciliacao(res["resumo"], res["sobra"], data_label,
                                  despesas=despesas, aplicacoes=aplicacoes)
    c2.download_button("📥 Baixar planilha", data=xlsx,
                       file_name=f"Conciliacao_{data_conc.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

    if c3.button("💾 Salvar no histórico", type="primary", use_container_width=True):
        with st.spinner("Salvando..."):
            try:
                repo_conciliacao.salvar_conciliacao(data_conc.isoformat(), res["resumo"], res["sobra"],
                                                    getattr(usuario, "id", None),
                                                    despesas=despesas, aplicacoes=aplicacoes)
            except Exception as e:
                st.error(f"Falha ao salvar: {getattr(e,'message',None) or repr(e)[:300]}")
                st.stop()
        st.success(f"✓ Conciliação de {data_label} salva no histórico.")
