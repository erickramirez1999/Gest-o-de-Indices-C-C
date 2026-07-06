"""
Tela Inadimplência · Upload.

Sobe os 3 arquivos do mês (Em Aberto PISA, Em Aberto King+Trio e a planilha
de histórico), escolhe o MÊS de referência e grava. O valor vem das planilhas
Em Aberto; a situação, do histórico (casado por Cód.Parceiro).
"""
from __future__ import annotations
from datetime import date

import pandas as pd
import streamlit as st

from src.banco import repo_inadimplencia
from src.servicos.leitor_inadimplencia import ler_inadimplencia
from src.utils.marca import AZUL_ESCURO
from src.utils.formatadores import formatar_brl, nome_mes

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def renderizar_inad_upload(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>📥 Inadimplência · Carregar</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11;border-left:4px solid {AZUL_ESCURO};"
        f"padding:12px;border-radius:6px;margin-bottom:14px;'>"
        f"Suba os <b>3 arquivos</b> do mês:<br>"
        f"• <b>Em Aberto PISA</b> (.xls) — valor por cliente<br>"
        f"• <b>Em Aberto King/Trio</b> (.xls) — valor por cliente<br>"
        f"• <b>Planilha de histórico</b> (.xls) — situação (acordo, terceirizada, ação judicial…)<br>"
        f"<i>O valor vem das planilhas Em Aberto; a situação, do histórico, casados pelo código do cliente.</i>"
        f"</div>", unsafe_allow_html=True)

    # ---- MÊS de referência ----
    hoje = date.today()
    c1, c2 = st.columns(2)
    mes = c1.selectbox("Mês de referência", MESES, index=hoje.month - 1)
    ano = c2.selectbox("Ano", list(range(hoje.year - 3, hoje.year + 1))[::-1], index=0)
    mes_ano = f"{ano}-{MESES.index(mes) + 1:02d}"
    st.caption(f"Este carregamento será salvo em **{nome_mes(mes_ano)}**.")

    arquivos = st.file_uploader("Arquivos (.xls / .xlsx)", type=["xls", "xlsx"],
                                accept_multiple_files=True, key="inad_arqs")
    if not arquivos:
        return

    lista = [(a.getvalue(), a.name) for a in arquivos]
    with st.spinner("Lendo e cruzando os arquivos..."):
        resultado = ler_inadimplencia(lista)

    for e in resultado["erros"]:
        st.error(e)
    for a in resultado["arquivos_processados"]:
        st.caption(f"✓ {a}")

    regs = resultado["registros"]
    if not regs:
        st.warning("Nenhum dado reconhecido. Confira se subiu as planilhas Em Aberto.")
        return

    df = pd.DataFrame(regs)
    tem_hist = df["situacao"].ne("Sem Registro").any()
    if not tem_hist:
        st.warning("⚠️ Não identifiquei a planilha de **histórico** — todos ficaram como 'Sem Registro'. "
                   "Suba também a planilha de histórico para trazer as situações.")

    cA, cB, cC = st.columns(3)
    cA.metric("Clientes", f"{df['cod_cliente'].nunique()}")
    cB.metric("PISA", f"{int((df.grupo=='PISA').sum())}", formatar_brl(df[df.grupo=='PISA']['valor_em_aberto'].sum()))
    cC.metric("King+Trio", f"{int((df.grupo=='KING_TRIO').sum())}", formatar_brl(df[df.grupo=='KING_TRIO']['valor_em_aberto'].sum()))

    st.markdown("**Situações identificadas (Top 40 de cada grupo):**")
    top = df[df["posicao"] <= 40]
    st.dataframe(top["situacao"].value_counts().rename_axis("Situação").reset_index(name="Clientes"),
                 use_container_width=True, hide_index=True)

    st.markdown("**Prévia — maiores dívidas:**")
    prev = df.sort_values("valor_em_aberto", ascending=False).head(8).copy()
    prev["Grupo"] = prev["grupo"].map({"PISA": "PISA", "KING_TRIO": "King+Trio"})
    prev["Dívida"] = prev["valor_em_aberto"].map(formatar_brl)
    prev["Selos"] = prev.apply(lambda r: ("🔴 Protesto " if r["tem_protesto"] else "") + ("⚠️ Quebra" if r["tem_quebra"] else ""), axis=1)
    st.dataframe(prev[["Grupo", "nome_cliente", "situacao", "Dívida", "Selos"]]
                 .rename(columns={"nome_cliente": "Cliente", "situacao": "Situação"}),
                 use_container_width=True, hide_index=True)

    if st.button(f"✅ Salvar em {nome_mes(mes_ano)}", type="primary", use_container_width=True, key="btn_inad"):
        with st.spinner("Salvando..."):
            try:
                repo_inadimplencia.salvar_inadimplencia(mes_ano, None, regs, getattr(usuario, "id", None))
            except Exception as e:
                st.error(
                    "Falha ao salvar.\n\n"
                    f"**code:** {getattr(e,'code',None)}\n\n**message:** {getattr(e,'message',None)}\n\n"
                    f"**hint:** {getattr(e,'hint',None)}\n\n**raw:** {repr(e)[:600]}")
                st.stop()
        st.success(f"✓ Inadimplência de **{nome_mes(mes_ano)}** salva! "
                   f"{df['cod_cliente'].nunique()} clientes.")
