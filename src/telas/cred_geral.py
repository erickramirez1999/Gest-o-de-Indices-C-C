"""Tela Crédito — Geral (histórico mês a mês)."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_AMARELO = "#FAC318"


def renderizar_geral_credito(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📊 Visão Geral — Crédito</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Consolidado histórico de todos os meses disponíveis.")

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("CREDITO")

    if not meses:
        st.info("Nenhum dado disponível. Faça o upload do primeiro mês.")
        return

    lib_hist = pd.DataFrame(repo_dados.historico_credito_liberacoes())
    lim_hist = pd.DataFrame(repo_dados.historico_credito_limites())

    import plotly.graph_objects as go

    # Evolução do fluxo de pedidos
    if not lib_hist.empty:
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>📈 Evolução do Fluxo de Pedidos</h3>", unsafe_allow_html=True)

        evo = (
            lib_hist.groupby(["mes_ano", "tipo"]).size()
            .unstack(fill_value=0)
            .reset_index()
            .sort_values("mes_ano")
        )
        evo["Mes"] = evo["mes_ano"].apply(nome_mes)

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            fig = go.Figure()
            for tipo, cor in [("DIRETO", COR_VERDE), ("LIBERADO", COR_AZUL), ("NEGADO", COR_VERMELHO)]:
                if tipo in evo.columns:
                    fig.add_trace(go.Bar(x=evo["Mes"], y=evo[tipo], name=tipo.title(), marker_color=cor))
            fig.update_layout(
                title="Pedidos por Tipo e Mês",
                barmode="stack", height=300,
                margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        with col_g2:
            # % Negados ao longo do tempo
            evo2 = (
                lib_hist.groupby("mes_ano").apply(lambda g: pd.Series({
                    "pct_negados": len(g[g["tipo"] == "NEGADO"]) / len(g) * 100,
                    "pct_direto": len(g[g["tipo"] == "DIRETO"]) / len(g) * 100,
                    "total": len(g),
                }))
                .reset_index()
                .sort_values("mes_ano")
            )
            evo2["Mes"] = evo2["mes_ano"].apply(nome_mes)

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=evo2["Mes"], y=evo2["pct_direto"],
                name="% Direto", mode="lines+markers",
                line=dict(color=COR_VERDE, width=2),
            ))
            fig2.add_trace(go.Scatter(
                x=evo2["Mes"], y=evo2["pct_negados"],
                name="% Negados", mode="lines+markers",
                line=dict(color=COR_VERMELHO, width=2, dash="dot"),
            ))
            fig2.update_layout(
                title="Tendência: % Direto vs % Negados",
                height=300, margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                yaxis=dict(ticksuffix="%"),
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Evolução de limites
    if not lim_hist.empty:
        st.markdown("---")
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>💳 Evolução de Reanálises de Limite</h3>", unsafe_allow_html=True)

        evo_lim = (
            lim_hist.groupby("mes_ano").apply(lambda g: pd.Series({
                "qtd": len(g),
                "variacao": g["variacao"].sum() if "variacao" in g.columns else 0,
                "novo_limite": g["novo_limite"].sum() if "novo_limite" in g.columns else 0,
            }))
            .reset_index()
            .sort_values("mes_ano")
        )
        evo_lim["Mes"] = evo_lim["mes_ano"].apply(nome_mes)

        col_l1, col_l2 = st.columns(2)
        with col_l1:
            fig3 = go.Figure(go.Bar(
                x=evo_lim["Mes"], y=evo_lim["qtd"],
                marker_color=COR_AZUL,
                text=evo_lim["qtd"], textposition="outside",
            ))
            fig3.update_layout(
                title="Qtd Reanálises por Mês",
                height=280, margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        with col_l2:
            fig4 = go.Figure(go.Scatter(
                x=evo_lim["Mes"], y=evo_lim["variacao"],
                mode="lines+markers+text",
                line=dict(color=COR_VERDE, width=2.5),
                fill="tozeroy", fillcolor="rgba(15,140,59,0.1)",
                text=[formatar_brl(v) for v in evo_lim["variacao"]],
                textposition="top center", textfont=dict(size=9),
            ))
            fig4.update_layout(
                title="Variação Total de Limite por Mês",
                height=280, margin=dict(l=0, r=0, t=30, b=10),
                plot_bgcolor="white",
                yaxis=dict(tickprefix="R$ ", tickformat=",.0f"),
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

    # Tabela consolidada
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Consolidado por Mês</h3>", unsafe_allow_html=True)

    todos_meses = sorted(set(
        list(lib_hist["mes_ano"].unique() if not lib_hist.empty else []) +
        list(lim_hist["mes_ano"].unique() if not lim_hist.empty else [])
    ))

    rows = []
    for m in todos_meses:
        row = {"Mês": nome_mes(m)}
        if not lib_hist.empty and m in lib_hist["mes_ano"].values:
            g = lib_hist[lib_hist["mes_ano"] == m]
            total = len(g)
            neg = len(g[g["tipo"] == "NEGADO"])
            direto = len(g[g["tipo"] == "DIRETO"])
            row["Total Pedidos"] = total
            row["% Direto"] = f"{direto/total*100:.1f}%"
            row["% Negados"] = f"{neg/total*100:.1f}%"
            row["Valor Aprovado"] = formatar_brl(g[g["tipo"].isin(["DIRETO","LIBERADO"])]["vlr_pedido"].sum())
        else:
            row["Total Pedidos"] = "-"
            row["% Direto"] = "-"
            row["% Negados"] = "-"
            row["Valor Aprovado"] = "-"

        if not lim_hist.empty and m in lim_hist["mes_ano"].values:
            g2 = lim_hist[lim_hist["mes_ano"] == m]
            row["Reanálises"] = len(g2)
            row["Variação Limite"] = formatar_brl(g2["variacao"].sum())
        else:
            row["Reanálises"] = "-"
            row["Variação Limite"] = "-"

        rows.append(row)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Exportar PPT Geral
    st.markdown("---")
    _botao_ppt_geral_credito(meses)


def _botao_ppt_geral_credito(meses: list):
    from src.servicos.gerador_ppt import gerar_ppt_geral
    from src.banco import repo_dados
    import pandas as pd

    if st.button("📊 Exportar PPT Geral — Análise Completa de Crédito", key="ppt_geral_cred"):
        with st.spinner("Gerando apresentação consolidada..."):
            dados_cred = []
            for m in meses:
                mes_ano = m["mes_ano"]
                liberacoes = repo_dados.buscar_liberacoes(mes_ano)
                limites = repo_dados.buscar_limites(mes_ano)
                df_lib = pd.DataFrame(liberacoes) if liberacoes else pd.DataFrame()
                df_lim = pd.DataFrame(limites) if limites else pd.DataFrame()

                total = len(df_lib)
                qtd_d = len(df_lib[df_lib["tipo"] == "DIRETO"]) if not df_lib.empty and "tipo" in df_lib.columns else 0
                qtd_l = len(df_lib[df_lib["tipo"] == "LIBERADO"]) if not df_lib.empty and "tipo" in df_lib.columns else 0
                qtd_n = len(df_lib[df_lib["tipo"] == "NEGADO"]) if not df_lib.empty and "tipo" in df_lib.columns else 0
                vlr_ap = float(df_lib[df_lib["tipo"].isin(["DIRETO", "LIBERADO"])]["vlr_pedido"].sum()) if not df_lib.empty and "vlr_pedido" in df_lib.columns else 0
                vlr_neg = float(df_lib[df_lib["tipo"] == "NEGADO"]["vlr_pedido"].sum()) if not df_lib.empty and "vlr_pedido" in df_lib.columns else 0
                var_lim = float(df_lim["variacao"].sum()) if not df_lim.empty and "variacao" in df_lim.columns else 0

                dados_cred.append({
                    "mes_label": nome_mes(mes_ano),
                    "liberacoes": {
                        "total": total,
                        "qtd_direto": qtd_d, "qtd_liberados": qtd_l, "qtd_negados": qtd_n,
                        "pct_direto": qtd_d / total * 100 if total else 0,
                        "pct_liberados": qtd_l / total * 100 if total else 0,
                        "pct_negados": qtd_n / total * 100 if total else 0,
                        "vlr_aprovado": vlr_ap, "vlr_negado": vlr_neg,
                    },
                    "limites": {
                        "total": len(df_lim),
                        "total_variacao": var_lim,
                    },
                    "df_liberacoes": df_lib,
                    "df_limites": df_lim,
                })

            ppt_bytes = gerar_ppt_geral([], dados_cred)

        st.download_button(
            "⬇ Baixar PPT Geral — Crédito",
            data=ppt_bytes,
            file_name="LLE_Analise_Geral_Credito.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
