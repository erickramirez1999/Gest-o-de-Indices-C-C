"""Tela Cobrança — Índices de Performance."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_AMARELO = "#FAC318"
META_HORAS = 2.0


def renderizar_performance(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>⚡ Índices de Performance</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Tempo de tela, ligações, ocorrências e acordos por cobrador.")

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("COBRANCA")

    if not meses:
        st.info("Nenhum dado disponível. Faça o upload do primeiro mês.")
        return

    opcoes = {m["mes_ano"]: nome_mes(m["mes_ano"]) for m in meses}
    mes_sel = st.selectbox("📅 Selecionar mês", list(opcoes.keys()), format_func=lambda x: opcoes[x])

    perf = repo_dados.buscar_performance(mes_sel)
    if not perf:
        st.warning("Nenhum dado de performance encontrado para este mês.")
        return

    df = pd.DataFrame(perf)
    _dashboard_performance(df, nome_mes(mes_sel))


def _dashboard_performance(df: pd.DataFrame, periodo: str):
    import plotly.graph_objects as go

    # Filtra linha de equipe se existir
    df_ind = df[~df["cobrador"].str.upper().str.contains("EQUIPE|TOTAL", na=False)].copy()

    # KPIs da equipe
    tempo_medio_eq = df_ind["tempo_medio_diario_h"].mean() if "tempo_medio_diario_h" in df_ind.columns else 0
    ader_media = df_ind["pct_aderencia"].mean() if "pct_aderencia" in df_ind.columns else 0
    ader_pct = ader_media * 100 if ader_media <= 1 else ader_media
    acordos_total = df_ind["total_acordos_valor"].sum() if "total_acordos_valor" in df_ind.columns else 0
    ocorr_media = df_ind["ocorrencias_media_dia"].mean() if "ocorrencias_media_dia" in df_ind.columns else 0

    st.markdown(f"**{periodo}** · {len(df_ind)} cobradores")
    st.markdown("<br>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (c1, "Tempo Médio Equipe", f"{tempo_medio_eq:.2f}h", f"meta: {META_HORAS}h/dia", COR_AZUL),
        (c2, "Aderência Média", f"{ader_pct:.1f}%", "à meta diária", COR_VERDE if ader_pct >= 80 else COR_VERMELHO),
        (c3, "Total Acordos", formatar_brl(acordos_total), "valor realizado", COR_VERDE),
        (c4, "Ocorrências/dia", f"{ocorr_media:.0f}", "média da equipe", COR_AZUL),
    ]
    for col, titulo, valor, sub, cor in kpis:
        with col:
            st.markdown(card_kpi(titulo, valor, sub, cor), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráfico de barras — tempo médio x meta
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Tempo Médio Diário vs Meta (2h)</h4>", unsafe_allow_html=True)
        if "tempo_medio_diario_h" in df_ind.columns:
            cores = [COR_VERDE if v >= META_HORAS else COR_VERMELHO
                     for v in df_ind["tempo_medio_diario_h"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_ind["cobrador"], y=df_ind["tempo_medio_diario_h"],
                marker_color=cores,
                text=[f"{v:.2f}h" for v in df_ind["tempo_medio_diario_h"]],
                textposition="outside",
                name="Tempo Médio",
            ))
            fig.add_hline(y=META_HORAS, line_dash="dash", line_color=COR_AMARELO,
                          annotation_text="Meta 2h", annotation_position="top right")
            fig.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=10),
                plot_bgcolor="white", showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", ticksuffix="h"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_g2:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Valor Total de Acordos</h4>", unsafe_allow_html=True)
        if "total_acordos_valor" in df_ind.columns:
            df_sort = df_ind.sort_values("total_acordos_valor", ascending=True)
            fig2 = go.Figure(go.Bar(
                x=df_sort["total_acordos_valor"], y=df_sort["cobrador"],
                orientation="h",
                marker_color=AZUL_VIVO,
                text=[formatar_brl(v) for v in df_sort["total_acordos_valor"]],
                textposition="outside",
            ))
            fig2.update_layout(
                height=280, margin=dict(l=0, r=80, t=10, b=10),
                plot_bgcolor="white", showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Tabela detalhada
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Detalhamento por Cobrador</h3>", unsafe_allow_html=True)

    colunas_map = {
        "cobrador": "Cobrador",
        "tempo_medio_diario_h": "Tempo Médio (h)",
        "meta_diaria_h": "Meta (h)",
        "pct_aderencia": "% Aderência",
        "ocorrencias_media_dia": "Ocorr./dia",
        "acordos_media_dia": "Acordos/dia",
        "valor_medio_diario": "Valor Médio/dia",
        "total_acordos_valor": "Total Acordos",
    }
    cols_ex = [c for c in colunas_map.keys() if c in df_ind.columns]
    df_show = df_ind[cols_ex].copy()

    if "pct_aderencia" in df_show.columns:
        df_show["pct_aderencia"] = df_show["pct_aderencia"].apply(
            lambda v: f"{v*100:.1f}%" if v <= 1 else f"{v:.1f}%"
        )
    if "tempo_medio_diario_h" in df_show.columns:
        df_show["tempo_medio_diario_h"] = df_show["tempo_medio_diario_h"].apply(lambda v: f"{v:.2f}h")
    if "total_acordos_valor" in df_show.columns:
        df_show["total_acordos_valor"] = df_show["total_acordos_valor"].apply(formatar_brl)
    if "valor_medio_diario" in df_show.columns:
        df_show["valor_medio_diario"] = df_show["valor_medio_diario"].apply(formatar_brl)

    df_show.rename(columns=colunas_map, inplace=True)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Aderência visual
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Aderência à Meta</h3>", unsafe_allow_html=True)
    for _, row in df_ind.iterrows():
        ader = row.get("pct_aderencia", 0)
        ader_pct_val = ader * 100 if ader <= 1 else ader
        cor = COR_VERDE if ader_pct_val >= 100 else (COR_AMARELO if ader_pct_val >= 80 else COR_VERMELHO)
        st.markdown(
            f"<div style='margin-bottom:10px;'>"
            f"<div style='display:flex; justify-content:space-between; margin-bottom:4px;'>"
            f"<b>{row['cobrador']}</b>"
            f"<span style='color:{cor}; font-weight:700;'>{ader_pct_val:.1f}%</span></div>"
            f"<div style='background:#EEE; height:10px; border-radius:5px; overflow:hidden;'>"
            f"<div style='background:{cor}; width:{min(ader_pct_val, 100):.0f}%; height:100%; border-radius:5px;'></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )
