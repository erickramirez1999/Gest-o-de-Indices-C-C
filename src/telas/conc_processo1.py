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
       "Boleto Cód Barras": "#0071FE", "Transferência entre contas": "#6C757D",
       "TED": "#6C757D", "DOC": "#6C757D", "Sobrando (Monday)": "#DC3545",
       "Despesas": "#B00020", "Tarifas": "#B00020", "Aplicação": "#7B5800"}


def _card(x):
    return (f"<div style='border:1px solid #E8EDF5;border-left:5px solid {COR.get(x['tipo'],'#041747')};"
            f"border-radius:8px;padding:10px 12px;margin-bottom:8px;'>"
            f"<div style='font-size:12px;color:#6C757D;font-weight:600'>{x['tipo']}</div>"
            f"<div style='font-size:18px;font-weight:700;color:{COR.get(x['tipo'],'#041747')}'>{formatar_brl(x['valor'])}</div>"
            f"<div style='font-size:11px;color:#6C757D'>{x['qtd']} lançamentos</div></div>")


def renderizar_conc_processo1(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>🔄 Conciliação · Processo 1</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11;border-left:4px solid {AZUL_ESCURO};padding:12px;"
        f"border-radius:6px;margin-bottom:14px;'>Suba os arquivos do dia: <b>extrato bancário</b>, "
        f"<b>base de recebimentos</b> (com 'Identificador do pagamento') e, se tiver, o <b>faturados</b> "
        f"(Monday). O sistema classifica tudo, apura os <b>PIX que sobram</b> e, quando o faturados bate "
        f"por valor, identifica <b>código do parceiro, parceiro e nota</b> — mas continua sendo sobra (Monday).</div>",
        unsafe_allow_html=True)

    arquivos = st.file_uploader("Extrato + base + faturados (.xlsx / .xls)", type=["xlsx", "xls"],
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

    st.markdown("### Resumo")
    resumo = res["resumo"]
    cols = st.columns(4)
    for i, x in enumerate(resumo):
        cols[i % 4].markdown(_card(x), unsafe_allow_html=True)

    sob = res["sobra"]
    n_ident = sum(1 for s in sob if s.get("cod"))
    st.markdown(f"### PIX sobrando (Monday) — {resumo[7]['qtd']} · {formatar_brl(res['total_sobra'])}"
                + (f"  ·  {n_ident} identificados" if n_ident else ""))
    if sob:
        disp = pd.DataFrame([{
            "Data": s["data"], "Histórico": s["historico"],
            "Cód Parceiro": s.get("cod") or "", "Parceiro": s.get("nome") or "",
            "Nota": s.get("nota") or "", "Valor": formatar_brl(s["valor"]),
        } for s in sob])
        st.dataframe(disp, use_container_width=True, hide_index=True, height=420)

    ambiguos = res.get("sobra_ambigua", [])
    if ambiguos:
        st.markdown("#### 🟡 PIX ambíguos (mesmo valor de QR/PIX — não somar os dois; só um sobra)")
        linhas = [{"Valor": formatar_brl(g["valor"]), "Sobrando": f'{g["conta"]} de {len(g["candidatos"])}',
                   "Candidatos (lado a lado)": "   |   ".join(f'{c["data"]} · {c["historico"]}' for c in g["candidatos"])}
                  for g in ambiguos]
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    st.markdown("---")
    c1, c2, c3 = st.columns([1, 1, 1])
    data_conc = c1.date_input("Data da conciliação", value=date.today(), format="DD/MM/YYYY")
    data_label = data_conc.strftime("%d/%m/%Y")

    xlsx = gerar_xlsx_conciliacao(resumo, res["sobra"], data_label, sobra_ambigua=ambiguos)
    c2.download_button("📥 Baixar planilha", data=xlsx,
                       file_name=f"Conciliacao_{data_conc.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)

    if c3.button("💾 Salvar no histórico", type="primary", use_container_width=True):
        with st.spinner("Salvando..."):
            try:
                repo_conciliacao.salvar_conciliacao(data_conc.isoformat(), resumo, res["sobra"],
                                                    getattr(usuario, "id", None), sobra_ambigua=ambiguos)
            except Exception as e:
                st.error(f"Falha ao salvar: {getattr(e,'message',None) or repr(e)[:300]}")
                st.stop()
        st.success(f"✓ Conciliação de {data_label} salva no histórico.")
