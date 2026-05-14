"""Tela Cobrança — Índices de Cobrança (Baixas)."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_LARANJA = "#FF8C00"
COR_AMARELO = "#FAC318"

FAIXAS_ORDEM = ["0-30", "31-60", "60-91", "91-180", "181-360", "+360"]


def renderizar_indices_cobranca(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>💰 Índices de Cobrança</h1>",
        unsafe_allow_html=True,
    )

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("COBRANCA")

    if not meses:
        st.info("Nenhum dado disponível. Faça o upload do primeiro mês.")
        return

    opcoes = {m["mes_ano"]: nome_mes(m["mes_ano"]) for m in meses}
    mes_sel = st.selectbox("📅 Selecionar mês", list(opcoes.keys()), format_func=lambda x: opcoes[x])

    baixas = repo_dados.buscar_baixas(mes_sel)
    if not baixas:
        st.warning("Nenhum dado de cobrança baixada encontrado para este mês.")
        return

    df = pd.DataFrame(baixas)
    _dashboard_cobranca(df, nome_mes(mes_sel))


def _dashboard_cobranca(df: pd.DataFrame, periodo: str):
    import plotly.graph_objects as go

    total_baixas = len(df)
    total_recebido = df["vlr_liquido"].sum() if "vlr_liquido" in df.columns else 0
    ticket_medio = total_recebido / total_baixas if total_baixas else 0
    total_juros_multa = df["juros_multa"].sum() if "juros_multa" in df.columns else 0
    dias_medio = df["dias_atraso"].mean() if "dias_atraso" in df.columns else 0

    top_cob = ""
    if "cobrador" in df.columns:
        top = df.groupby("cobrador")["vlr_liquido"].sum()
        if not top.empty:
            top_cob = top.idxmax()

    st.markdown(f"**{periodo}** · {total_baixas:,} baixas registradas")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, "Total Baixas", f"{total_baixas:,}", "títulos baixados", COR_AZUL),
        (c2, "Total Recebido", formatar_brl(total_recebido), "valor líquido", COR_VERDE),
        (c3, "Ticket Médio", formatar_brl(ticket_medio), "por baixa", COR_AZUL),
        (c4, "Juros + Multa", formatar_brl(total_juros_multa), "total cobrado", COR_AMARELO),
        (c5, "Dias Médios Atraso", f"{dias_medio:.0f} dias", "média geral", COR_VERMELHO),
        (c6, "Top Cobrador", top_cob.split(" ")[0] if top_cob else "-", "maior volume", COR_VERDE),
    ]
    for col, titulo, valor, sub, cor in kpis:
        with col:
            st.markdown(card_kpi(titulo, valor, sub, cor), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráficos
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Recebido por Cobrador</h4>", unsafe_allow_html=True)
        if "cobrador" in df.columns:
            por_cob = (
                df.groupby("cobrador")
                .agg(total=("vlr_liquido", "sum"), qtd=("vlr_liquido", "count"))
                .reset_index()
                .sort_values("total", ascending=True)
            )
            fig = go.Figure(go.Bar(
                x=por_cob["total"], y=por_cob["cobrador"],
                orientation="h",
                marker_color=AZUL_VIVO,
                text=[formatar_brl(v) for v in por_cob["total"]],
                textposition="outside",
            ))
            fig.update_layout(
                height=260, margin=dict(l=0, r=80, t=10, b=10),
                plot_bgcolor="white", showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_g2:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Aging — Faixa de Atraso</h4>", unsafe_allow_html=True)
        if "faixa_aging" in df.columns:
            aging = (
                df.dropna(subset=["faixa_aging"])
                .groupby("faixa_aging")["vlr_liquido"]
                .sum()
                .reindex(FAIXAS_ORDEM, fill_value=0)
                .reset_index()
            )
            cores = [COR_VERDE, COR_AMARELO, COR_LARANJA, COR_VERMELHO, COR_VERMELHO, "#8B0000"]
            fig2 = go.Figure(go.Bar(
                x=aging["faixa_aging"], y=aging["vlr_liquido"],
                marker_color=cores,
                text=[formatar_brl(v) for v in aging["vlr_liquido"]],
                textposition="outside",
            ))
            fig2.update_layout(
                height=260, margin=dict(l=0, r=0, t=10, b=10),
                plot_bgcolor="white", showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Tabela por cobrador
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Resumo por Cobrador</h3>", unsafe_allow_html=True)

    if "cobrador" in df.columns:
        resumo = (
            df.groupby("cobrador").apply(lambda g: pd.Series({
                "Qtd Baixas": len(g),
                "Total Recebido": formatar_brl(g["vlr_liquido"].sum()),
                "Ticket Médio": formatar_brl(g["vlr_liquido"].mean()),
                "Vlr Original": formatar_brl(g["vlr_desdobrado"].sum()) if "vlr_desdobrado" in g.columns else "-",
                "Juros + Multa": formatar_brl(g["juros_multa"].sum()) if "juros_multa" in g.columns else "-",
                "Dias Médio Atraso": f"{g['dias_atraso'].mean():.0f}" if "dias_atraso" in g.columns else "-",
            }))
            .reset_index()
            .rename(columns={"cobrador": "Cobrador"})
        )
        st.dataframe(resumo, use_container_width=True, hide_index=True)

    # Aging por cobrador
    if "cobrador" in df.columns and "faixa_aging" in df.columns:
        st.markdown("---")
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Aging por Cobrador</h3>", unsafe_allow_html=True)
        aging_cob = (
            df.dropna(subset=["faixa_aging"])
            .groupby(["cobrador", "faixa_aging"])["vlr_liquido"]
            .sum()
            .unstack(fill_value=0)
            .reindex(columns=FAIXAS_ORDEM, fill_value=0)
        )
        aging_cob["Total"] = aging_cob.sum(axis=1)
        aging_fmt = aging_cob.apply(lambda col: col.map(formatar_brl))
        st.dataframe(aging_fmt, use_container_width=True)
