"""Tela Cobrança — Geral (histórico mês a mês)."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"


def renderizar_geral_cobranca(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📊 Visão Geral — Cobrança</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Consolidado histórico de todos os meses disponíveis.")

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("COBRANCA")

    if not meses:
        st.info("Nenhum dado disponível. Faça o upload do primeiro mês.")
        return

    # Carrega todos os dados históricos
    acordos_hist = pd.DataFrame(repo_dados.historico_cobranca_acordos())
    baixas_hist = pd.DataFrame(repo_dados.historico_cobranca_baixas())

    if acordos_hist.empty and baixas_hist.empty:
        st.warning("Sem dados consolidados.")
        return

    import plotly.graph_objects as go

    # --- EVOLUÇÃO DE ACORDOS ---
    if not acordos_hist.empty:
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>📈 Evolução de Acordos</h3>", unsafe_allow_html=True)

        evo = (
            acordos_hist.groupby("mes_ano").apply(lambda g: pd.Series({
                "Total": len(g),
                "Ativos": int((~g["cancelado"]).sum()) if "cancelado" in g.columns else len(g),
                "Valor": g.loc[~g["cancelado"], "valor_total"].sum() if "cancelado" in g.columns else g["valor_total"].sum(),
            }))
            .reset_index()
            .sort_values("mes_ano")
        )
        evo["Mes"] = evo["mes_ano"].apply(nome_mes)

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=evo["Mes"], y=evo["Total"],
                name="Total Acordos",
                marker_color=AZUL_VIVO,
                text=evo["Total"], textposition="outside",
            ))
            fig.add_trace(go.Bar(
                x=evo["Mes"], y=evo["Ativos"],
                name="Ativos",
                marker_color=VERDE,
            ))
            fig.update_layout(
                title="Quantidade de Acordos por Mês",
                height=300, barmode="group",
                margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                legend=dict(orientation="h", y=-0.2),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_g2:
            fig2 = go.Figure(go.Scatter(
                x=evo["Mes"], y=evo["Valor"],
                mode="lines+markers+text",
                line=dict(color=COR_VERDE, width=2.5),
                marker=dict(size=8, color=COR_VERDE),
                fill="tozeroy",
                fillcolor="rgba(15,140,59,0.1)",
                text=[formatar_brl(v) for v in evo["Valor"]],
                textposition="top center",
                textfont=dict(size=10),
            ))
            fig2.update_layout(
                title="Valor Total Acordado por Mês",
                height=300,
                margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # --- EVOLUÇÃO DE BAIXAS ---
    if not baixas_hist.empty:
        st.markdown("---")
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>💰 Evolução de Recebimentos</h3>", unsafe_allow_html=True)

        rec = (
            baixas_hist.groupby("mes_ano").apply(lambda g: pd.Series({
                "Total": len(g),
                "Recebido": g["vlr_liquido"].sum() if "vlr_liquido" in g.columns else 0,
                "Dias Medio": g["dias_atraso"].mean() if "dias_atraso" in g.columns else 0,
            }))
            .reset_index()
            .sort_values("mes_ano")
        )
        rec["Mes"] = rec["mes_ano"].apply(nome_mes)

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            fig3 = go.Figure(go.Bar(
                x=rec["Mes"], y=rec["Recebido"],
                marker_color=COR_VERDE,
                text=[formatar_brl(v) for v in rec["Recebido"]],
                textposition="outside",
            ))
            fig3.update_layout(
                title="Total Recebido por Mês",
                height=280, margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        with col_r2:
            fig4 = go.Figure(go.Scatter(
                x=rec["Mes"], y=rec["Dias Medio"],
                mode="lines+markers",
                line=dict(color=COR_VERMELHO, width=2),
                marker=dict(size=7),
                fill="tozeroy",
                fillcolor="rgba(220,53,69,0.1)",
            ))
            fig4.update_layout(
                title="Dias Médios de Atraso por Mês",
                height=280, margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#EEE", ticksuffix=" dias"),
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    # Tabela consolidada
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Consolidado por Mês</h3>", unsafe_allow_html=True)

    rows = []
    for m in sorted(set(
        list(acordos_hist["mes_ano"].unique() if not acordos_hist.empty else []) +
        list(baixas_hist["mes_ano"].unique() if not baixas_hist.empty else [])
    )):
        row = {"Mês": nome_mes(m)}
        if not acordos_hist.empty and m in acordos_hist["mes_ano"].values:
            g = acordos_hist[acordos_hist["mes_ano"] == m]
            ativos = g[~g["cancelado"]] if "cancelado" in g.columns else g
            row["Acordos"] = len(g)
            row["Valor Acordado"] = formatar_brl(ativos["valor_total"].sum())
        else:
            row["Acordos"] = "-"
            row["Valor Acordado"] = "-"
        if not baixas_hist.empty and m in baixas_hist["mes_ano"].values:
            g2 = baixas_hist[baixas_hist["mes_ano"] == m]
            row["Baixas"] = len(g2)
            row["Total Recebido"] = formatar_brl(g2["vlr_liquido"].sum())
        else:
            row["Baixas"] = "-"
            row["Total Recebido"] = "-"
        rows.append(row)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Exportar PPT Geral
    st.markdown("---")
    _botao_ppt_geral_cobranca(meses)


def _botao_ppt_geral_cobranca(meses: list):
    from src.servicos.gerador_ppt import gerar_ppt_geral
    from src.banco import repo_dados

    if st.button("📊 Exportar PPT Geral — Cobrança", key="ppt_geral_cob"):
        with st.spinner("Gerando apresentação consolidada..."):
            dados_cob = []
            for m in meses:
                mes_ano = m["mes_ano"]
                acordos = repo_dados.buscar_acordos(mes_ano)
                baixas = repo_dados.buscar_baixas(mes_ano)
                perf = repo_dados.buscar_performance(mes_ano)
                import pandas as pd
                df_ac = pd.DataFrame(acordos) if acordos else pd.DataFrame()
                df_bx = pd.DataFrame(baixas) if baixas else pd.DataFrame()
                df_pf = pd.DataFrame(perf) if perf else pd.DataFrame()

                cancelados = int(df_ac["cancelado"].sum()) if not df_ac.empty and "cancelado" in df_ac.columns else 0
                ativos = len(df_ac) - cancelados
                valor_total = float(df_ac["valor_total"].sum()) if not df_ac.empty and "valor_total" in df_ac.columns else 0
                total_recebido = float(df_bx["vlr_liquido"].sum()) if not df_bx.empty and "vlr_liquido" in df_bx.columns else 0
                dias_atraso = float(df_bx["dias_atraso"].mean()) if not df_bx.empty and "dias_atraso" in df_bx.columns else 0
                ader = float(df_pf["pct_aderencia"].mean()) if not df_pf.empty and "pct_aderencia" in df_pf.columns else 0
                top_cob = ""
                if not df_pf.empty and "cobrador" in df_pf.columns and "total_acordos_valor" in df_pf.columns:
                    top_cob = df_pf.loc[df_pf["total_acordos_valor"].idxmax(), "cobrador"] if len(df_pf) else ""

                dados_cob.append({
                    "mes_label": nome_mes(mes_ano),
                    "acordos": {
                        "total_acordos": len(df_ac),
                        "valor_total": valor_total,
                        "ticket_medio": valor_total / ativos if ativos else 0,
                        "pct_cancelamento": cancelados / len(df_ac) * 100 if len(df_ac) else 0,
                    },
                    "baixas": {
                        "total_recebido": total_recebido,
                        "total_baixas": len(df_bx),
                        "dias_medio_atraso": dias_atraso,
                    },
                    "performance": {
                        "aderencia_media": ader,
                        "top_cobrador": top_cob,
                    },
                    "df_acordos": df_ac,
                    "df_baixas": df_bx,
                    "df_performance": df_pf,
                })

            ppt_bytes = gerar_ppt_geral(dados_cob, [])

        st.download_button(
            "⬇ Baixar PPT Geral Cobrança",
            data=ppt_bytes,
            file_name="LLE_Geral_Cobranca.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
