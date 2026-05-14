"""Tela Cobrança — Índices de Acordo."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, formatar_pct, nome_mes
from src.utils.estilo import card_kpi


COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_LARANJA = "#FF8C00"
COR_AMARELO = "#FAC318"


def renderizar_indices_acordo(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📋 Índices de Acordo</h1>",
        unsafe_allow_html=True,
    )

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("COBRANCA")

    if not meses:
        st.info("Nenhum dado de Cobrança disponível. Faça o upload do primeiro mês.")
        return

    opcoes = {m["mes_ano"]: nome_mes(m["mes_ano"]) for m in meses}
    mes_sel = st.selectbox(
        "📅 Selecionar mês",
        list(opcoes.keys()),
        format_func=lambda x: opcoes[x],
    )

    acordos = repo_dados.buscar_acordos(mes_sel)
    if not acordos:
        st.warning("Nenhum dado de acordo encontrado para este mês.")
        return

    df = pd.DataFrame(acordos)
    _dashboard_acordos(df, nome_mes(mes_sel), usuario)


def _dashboard_acordos(df: pd.DataFrame, periodo: str, usuario):
    import plotly.graph_objects as go
    import plotly.express as px

    # KPIs gerais
    total = len(df)
    cancelados = df["cancelado"].sum() if "cancelado" in df.columns else 0
    ativos = total - cancelados
    valor_total = df["valor_total"].sum() if "valor_total" in df.columns else 0
    ticket_medio = valor_total / ativos if ativos else 0
    parcelas_media = df[~df["cancelado"]]["qtd_parcelas"].mean() if "qtd_parcelas" in df.columns else 0
    pct_cancel = cancelados / total * 100 if total else 0

    st.markdown(f"**{periodo}** · {total} acordos registrados")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, "Total Acordos", str(total), "no período", COR_AZUL),
        (c2, "Valor Total", formatar_brl(valor_total), "acordos ativos", COR_VERDE),
        (c3, "Ticket Médio", formatar_brl(ticket_medio), "por acordo ativo", COR_AZUL),
        (c4, "Cancelamentos", f"{pct_cancel:.1f}%", f"{int(cancelados)} acordos", COR_VERMELHO),
        (c5, "Parcelas Média", f"{parcelas_media:.1f}x", "por acordo ativo", COR_AZUL),
        (c6, "Acordos Ativos", str(int(ativos)), "sem cancelamento", COR_VERDE),
    ]
    for col, titulo, valor, sub, cor in kpis:
        with col:
            st.markdown(card_kpi(titulo, valor, sub, cor), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráficos
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Acordos por Cobrador</h4>", unsafe_allow_html=True)
        if "negociador" in df.columns:
            por_neg = (
                df[~df["cancelado"]]
                .groupby("negociador")
                .agg(qtd=("valor_total", "count"), valor=("valor_total", "sum"))
                .reset_index()
                .sort_values("valor", ascending=False)
            )
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=por_neg["negociador"], y=por_neg["valor"],
                marker_color=AZUL_VIVO,
                text=[formatar_brl(v) for v in por_neg["valor"]],
                textposition="outside",
            ))
            fig.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=10),
                showlegend=False, plot_bgcolor="white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_graf2:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Forma de Pagamento</h4>", unsafe_allow_html=True)
        if "forma_pagto" in df.columns:
            por_forma = df[~df["cancelado"]].groupby("forma_pagto").size().reset_index(name="qtd")
            fig2 = go.Figure(go.Pie(
                labels=por_forma["forma_pagto"],
                values=por_forma["qtd"],
                hole=0.45,
                marker_colors=[AZUL_ESCURO, AZUL_VIVO, AMARELO, VERDE],
            ))
            fig2.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=10),
                showlegend=True,
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Por cobrador detalhado
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Por Cobrador</h3>", unsafe_allow_html=True)

    if "negociador" in df.columns:
        resumo = (
            df.groupby("negociador").apply(lambda g: pd.Series({
                "Total Acordos": len(g),
                "Ativos": int((~g["cancelado"]).sum()),
                "Cancelados": int(g["cancelado"].sum()),
                "% Cancel.": f"{g['cancelado'].mean()*100:.1f}%",
                "Valor Total": formatar_brl(g.loc[~g["cancelado"], "valor_total"].sum()),
                "Ticket Médio": formatar_brl(
                    g.loc[~g["cancelado"], "valor_total"].sum() / max((~g["cancelado"]).sum(), 1)
                ),
                "Parcelas Média": f"{g.loc[~g['cancelado'], 'qtd_parcelas'].mean():.1f}x" if "qtd_parcelas" in g.columns else "-",
            }))
            .reset_index()
            .rename(columns={"negociador": "Cobrador"})
        )
        st.dataframe(resumo, use_container_width=True, hide_index=True)

    # Top 10 maiores acordos
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Top 10 Maiores Acordos</h3>", unsafe_allow_html=True)

    cols_show = ["negociador", "devedor", "data_acordo", "forma_pagto",
                 "qtd_parcelas", "valor_parcela", "valor_total", "status"]
    cols_ex = [c for c in cols_show if c in df.columns]
    top10 = df.nlargest(10, "valor_total")[cols_ex].copy()
    if "valor_total" in top10.columns:
        top10["valor_total"] = top10["valor_total"].apply(formatar_brl)
    if "valor_parcela" in top10.columns:
        top10["valor_parcela"] = top10["valor_parcela"].apply(formatar_brl)
    st.dataframe(top10, use_container_width=True, hide_index=True)

    # Exportar PPT
    st.markdown("---")
    _botao_exportar_ppt_acordo(df, periodo)


def _botao_exportar_ppt_acordo(df: pd.DataFrame, periodo: str):
    from src.servicos.gerador_ppt import gerar_ppt_cobranca

    cancelados = int(df["cancelado"].sum()) if "cancelado" in df.columns else 0
    ativos = len(df) - cancelados
    valor_total = float(df["valor_total"].sum()) if "valor_total" in df.columns else 0
    top_cob = ""
    if "negociador" in df.columns:
        top = df[~df["cancelado"]].groupby("negociador")["valor_total"].sum()
        if not top.empty:
            top_cob = top.idxmax()

    dados = {
        "acordos": {
            "total_acordos": len(df),
            "valor_total": valor_total,
            "ticket_medio": valor_total / ativos if ativos else 0,
            "pct_cancelamento": cancelados / len(df) * 100 if len(df) else 0,
            "parcelas_media": float(df[~df["cancelado"]]["qtd_parcelas"].mean()) if "qtd_parcelas" in df.columns else 0,
            "top_cobrador": top_cob,
        },
        "df_acordos": df,
    }

    if st.button("📊 Exportar PPT", key="ppt_acordo"):
        with st.spinner("Gerando apresentação..."):
            ppt_bytes = gerar_ppt_cobranca(dados, periodo)
        st.download_button(
            "⬇ Baixar Apresentação",
            data=ppt_bytes,
            file_name=f"LLE_Cobranca_Acordo_{periodo.replace('/', '-')}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
