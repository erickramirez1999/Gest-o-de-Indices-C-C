"""Tela Crédito — Reanálises de Limite."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_AMARELO = "#FAC318"


def renderizar_reanalises(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🔄 Reanálises de Limite de Crédito</h1>",
        unsafe_allow_html=True,
    )

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("CREDITO")

    if not meses:
        st.info("Nenhum dado disponível. Faça o upload do primeiro mês.")
        return

    opcoes = {m["mes_ano"]: nome_mes(m["mes_ano"]) for m in meses}
    mes_sel = st.selectbox("📅 Selecionar mês", list(opcoes.keys()), format_func=lambda x: opcoes[x])

    limites = repo_dados.buscar_limites(mes_sel)
    if not limites:
        st.warning("Nenhum dado de reanálises encontrado para este mês.")
        return

    df = pd.DataFrame(limites)
    _dashboard_limites(df, nome_mes(mes_sel))


def _dashboard_limites(df: pd.DataFrame, periodo: str):
    import plotly.graph_objects as go

    total = len(df)
    total_anterior = df["limite_anterior"].sum() if "limite_anterior" in df.columns else 0
    total_novo = df["novo_limite"].sum() if "novo_limite" in df.columns else 0
    total_var = df["variacao"].sum() if "variacao" in df.columns else 0
    maior_aum = df["variacao"].max() if "variacao" in df.columns else 0
    qtd_analistas = df["analista"].nunique() if "analista" in df.columns else 0

    st.markdown(f"**{periodo}** · {total} reanálises realizadas")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, "Total Reanálises", str(total), "no período", COR_AZUL),
        (c2, "Limite Anterior", formatar_brl(total_anterior), "soma total", "#6C757D"),
        (c3, "Novo Limite", formatar_brl(total_novo), "soma total", COR_VERDE),
        (c4, "Variação Total", formatar_brl(total_var), "aumento concedido", COR_AMARELO),
        (c5, "Analistas", str(qtd_analistas), "realizaram reanálises", COR_AZUL),
    ]
    for col, titulo, valor, sub, cor in kpis:
        with col:
            st.markdown(card_kpi(titulo, valor, sub, cor), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráfico consolidado: Limite Anterior x Novo x Variação
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Consolidado de Limites</h4>", unsafe_allow_html=True)
        fig = go.Figure(go.Bar(
            x=["Limite Anterior", "Novo Limite", "Variação"],
            y=[total_anterior, total_novo, total_var],
            marker_color=[COR_AMARELO, COR_VERDE, COR_AZUL],
            text=[formatar_brl(v) for v in [total_anterior, total_novo, total_var]],
            textposition="outside",
        ))
        fig.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=10),
            plot_bgcolor="white", showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_g2:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Por Analista</h4>", unsafe_allow_html=True)
        if "analista" in df.columns:
            por_analista = (
                df.groupby("analista")
                .agg(qtd=("variacao", "count"), variacao=("variacao", "sum"))
                .reset_index()
                .sort_values("variacao", ascending=True)
            )
            fig2 = go.Figure(go.Bar(
                x=por_analista["variacao"], y=por_analista["analista"],
                orientation="h",
                marker_color=COR_VERDE,
                text=[formatar_brl(v) for v in por_analista["variacao"]],
                textposition="outside",
            ))
            fig2.update_layout(
                height=280, margin=dict(l=0, r=80, t=10, b=10),
                plot_bgcolor="white", showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Tabela por analista
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Detalhamento por Analista</h3>", unsafe_allow_html=True)

    if "analista" in df.columns:
        resumo = (
            df.groupby("analista").apply(lambda g: pd.Series({
                "Qtd Reanálises": len(g),
                "Limite Anterior": formatar_brl(g["limite_anterior"].sum()),
                "Novo Limite": formatar_brl(g["novo_limite"].sum()),
                "Variação Total": formatar_brl(g["variacao"].sum()),
                "Maior Aumento": formatar_brl(g["variacao"].max()),
            }))
            .reset_index()
            .rename(columns={"analista": "Analista"})
        )
        st.dataframe(resumo, use_container_width=True, hide_index=True)

    # Top reanálises
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Top 20 Maiores Aumentos</h3>", unsafe_allow_html=True)

    cols_show = ["analista", "nome", "cod_parceiro", "limite_anterior", "novo_limite", "variacao", "data_inclusao"]
    cols_ex = [c for c in cols_show if c in df.columns]
    top20 = df.nlargest(20, "variacao")[cols_ex].copy()
    for col in ["limite_anterior", "novo_limite", "variacao"]:
        if col in top20.columns:
            top20[col] = top20[col].apply(formatar_brl)
    st.dataframe(top20, use_container_width=True, hide_index=True)
