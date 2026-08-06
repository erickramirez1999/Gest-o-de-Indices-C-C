"""Atendimento · Upload (Cobrança)."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from src.banco import repo_atendimento
from src.servicos.leitor_atendimento import ler_atendimentos
from src.utils.marca import AZUL_ESCURO
from src.utils.formatadores import formatar_inteiro


def renderizar_atend_upload(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>💬 Atendimento · Upload</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11;border-left:4px solid {AZUL_ESCURO};padding:12px;"
        f"border-radius:6px;margin-bottom:14px;'>Suba o(s) CSV de <b>Atendimentos encerrados por finalização</b> "
        f"(colunas Dia; Motivo; Total de Finalizações). Cada ano enviado <b>substitui</b> o ano correspondente.</div>",
        unsafe_allow_html=True)

    arquivos = st.file_uploader("CSV de atendimentos", type=["csv"], accept_multiple_files=True, key="atend_arqs")
    if not arquivos:
        return

    lista = [(a.getvalue(), a.name) for a in arquivos]
    with st.spinner("Lendo..."):
        res = ler_atendimentos(lista)
    for e in res["erros"]:
        st.error(e)
    for a in res["arquivos"]:
        st.caption(f"✓ {a}")
    if not res["registros"]:
        return

    df = pd.DataFrame(res["registros"])
    st.success(f"{formatar_inteiro(df['total'].sum())} finalizações · {df['motivo'].nunique()} motivos · anos: {', '.join(map(str, res['anos']))}")
    prev = df.groupby("motivo")["total"].sum().sort_values(ascending=False).reset_index()
    prev.columns = ["Motivo", "Total"]
    prev["Total"] = prev["Total"].map(formatar_inteiro)
    st.dataframe(prev, use_container_width=True, hide_index=True, height=380)

    if st.button("💾 Salvar", type="primary"):
        with st.spinner("Salvando..."):
            try:
                n = repo_atendimento.salvar_atendimentos(res["registros"], getattr(usuario, "id", None))
            except Exception as e:
                st.error(f"Falha ao salvar: {getattr(e,'message',None) or repr(e)[:300]}")
                st.stop()
        st.success(f"✓ {formatar_inteiro(n)} linhas salvas (anos {', '.join(map(str, res['anos']))}).")
