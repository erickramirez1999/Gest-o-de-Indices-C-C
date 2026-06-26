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

    ocorrencias = repo_dados.buscar_ocorrencias(mes_sel)
    df = pd.DataFrame(acordos)
    df_oc = pd.DataFrame(ocorrencias) if ocorrencias else pd.DataFrame()
    _dashboard_acordos(df, df_oc, nome_mes(mes_sel), usuario)


def _dashboard_acordos(df: pd.DataFrame, df_oc: pd.DataFrame, periodo: str, usuario):
    import plotly.graph_objects as go
    import plotly.express as px

    # KPIs gerais
    total = len(df)
    valor_total = df["valor_total"].sum() if "valor_total" in df.columns else 0
    valor_recebido = df["valor_pago"].sum() if "valor_pago" in df.columns else 0
    ticket_medio = valor_total / total if total else 0
    parcelas_media = df["qtd_parcelas"].mean() if "qtd_parcelas" in df.columns else 0

    # Quebras (origem: ocorrências)
    qtd_quebras = 0
    qtd_acordos_ocor = 0
    if df_oc is not None and not df_oc.empty:
        if "eh_quebra" in df_oc.columns:
            qtd_quebras = int(df_oc["eh_quebra"].fillna(False).sum())
        if "eh_acordo" in df_oc.columns:
            qtd_acordos_ocor = int(df_oc["eh_acordo"].fillna(False).sum())
    base_quebra = qtd_acordos_ocor if qtd_acordos_ocor else total
    pct_quebra = (qtd_quebras / base_quebra * 100) if base_quebra else 0

    st.markdown(f"**{periodo}** · {total} acordos registrados")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, "Total Acordos", str(total), "no período", COR_AZUL),
        (c2, "Valor Total", formatar_brl(valor_total), "soma dos acordos", COR_VERDE),
        (c3, "Recebido", formatar_brl(valor_recebido), "valor pago (parcelas)", COR_VERDE),
        (c4, "Ticket Médio", formatar_brl(ticket_medio), "por acordo", COR_AZUL),
        (c5, "Quebras", str(qtd_quebras), f"{pct_quebra:.1f}% s/ acordos", COR_VERMELHO),
        (c6, "Parcelas Média", f"{parcelas_media:.1f}x", "por acordo", COR_AZUL),
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
                df
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
            por_forma = df.groupby("forma_pagto").size().reset_index(name="qtd")
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
                "Valor Total": formatar_brl(g["valor_total"].sum()),
                "Recebido": formatar_brl(g["valor_pago"].sum()) if "valor_pago" in g.columns else "-",
                "% Recebido": f"{(g['valor_pago'].sum() / g['valor_total'].sum() * 100) if g['valor_total'].sum() else 0:.1f}%" if "valor_pago" in g.columns else "-",
                "Ticket Médio": formatar_brl(g["valor_total"].sum() / max(len(g), 1)),
                "Parcelas Média": f"{g['qtd_parcelas'].mean():.1f}x" if "qtd_parcelas" in g.columns else "-",
            }))
            .reset_index()
            .rename(columns={"negociador": "Cobrador"})
        )
        st.dataframe(resumo, use_container_width=True, hide_index=True)

    # Quebras de acordo (origem: ocorrências)
    if df_oc is not None and not df_oc.empty and "eh_quebra" in df_oc.columns:
        st.markdown("---")
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Quebras de Acordo</h3>", unsafe_allow_html=True)
        quebras = df_oc[df_oc["eh_quebra"].fillna(False)].copy()
        if quebras.empty:
            st.info("Nenhuma quebra de acordo registrada neste mês.")
        else:
            col_q1, col_q2 = st.columns([1, 1])
            with col_q1:
                por_neg_q = (
                    quebras.groupby("negociador").size()
                    .reset_index(name="Quebras")
                    .sort_values("Quebras", ascending=False)
                )
                import plotly.graph_objects as _go
                figq = _go.Figure(_go.Bar(
                    x=por_neg_q["negociador"], y=por_neg_q["Quebras"],
                    marker_color=COR_VERMELHO,
                    text=por_neg_q["Quebras"], textposition="outside",
                ))
                figq.update_layout(
                    height=280, margin=dict(l=0, r=0, t=10, b=10),
                    showlegend=False, plot_bgcolor="white",
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="#EEE"),
                )
                st.plotly_chart(figq, use_container_width=True, config={"displayModeBar": False})
            with col_q2:
                cols_q = [c for c in ["negociador", "processo", "devedor", "cidade", "uf", "data_ocorrencia"] if c in quebras.columns]
                tab_q = quebras[cols_q].sort_values("data_ocorrencia").rename(columns={
                    "negociador": "Cobrador", "processo": "Processo", "devedor": "Devedor",
                    "cidade": "Cidade", "uf": "UF", "data_ocorrencia": "Data",
                })
                st.dataframe(tab_q, use_container_width=True, hide_index=True)

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
    _botao_exportar_ppt_acordo(df, df_oc, periodo)


def _botao_exportar_ppt_acordo(df: pd.DataFrame, df_oc: pd.DataFrame, periodo: str):
    from src.servicos.gerador_ppt import gerar_ppt_cobranca

    total = len(df)
    valor_total = float(df["valor_total"].sum()) if "valor_total" in df.columns else 0
    valor_recebido = float(df["valor_pago"].sum()) if "valor_pago" in df.columns else 0
    top_cob = ""
    if "negociador" in df.columns:
        top = df.groupby("negociador")["valor_total"].sum()
        if not top.empty:
            top_cob = top.idxmax()

    qtd_quebras = 0
    base_quebra = total
    if df_oc is not None and not df_oc.empty and "eh_quebra" in df_oc.columns:
        qtd_quebras = int(df_oc["eh_quebra"].fillna(False).sum())
        if "eh_acordo" in df_oc.columns:
            n_ac = int(df_oc["eh_acordo"].fillna(False).sum())
            base_quebra = n_ac or total
    pct_quebra = (qtd_quebras / base_quebra * 100) if base_quebra else 0

    dados = {
        "acordos": {
            "total_acordos": total,
            "valor_total": valor_total,
            "valor_recebido": valor_recebido,
            "ticket_medio": valor_total / total if total else 0,
            "pct_cancelamento": pct_quebra,  # rótulo no PPT é "Taxa de Quebra"
            "qtd_quebras": qtd_quebras,
            "parcelas_media": float(df["qtd_parcelas"].mean()) if "qtd_parcelas" in df.columns else 0,
            "top_cobrador": top_cob,
        },
        "baixas": {"total_recebido": valor_recebido},
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
