"""Tela Crédito — Indicadores de Análise (Liberações por Pedido)."""
from __future__ import annotations
import pandas as pd
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi, badge_variacao

COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_AMARELO = "#FAC318"


def renderizar_indicadores_credito(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>💳 Indicadores de Análise de Crédito</h1>",
        unsafe_allow_html=True,
    )

    from src.banco import repo_dados
    meses = repo_dados.listar_meses_disponiveis("CREDITO")

    if not meses:
        st.info("Nenhum dado de Crédito disponível. Faça o upload do primeiro mês.")
        return

    opcoes = {m["mes_ano"]: nome_mes(m["mes_ano"]) for m in meses}

    col_sel, col_comp = st.columns([2, 2])
    with col_sel:
        mes_sel = st.selectbox("📅 Mês atual", list(opcoes.keys()), format_func=lambda x: opcoes[x])
    with col_comp:
        meses_comp = ["—"] + [m for m in list(opcoes.keys()) if m != mes_sel]
        mes_ant = st.selectbox("🔄 Comparar com", meses_comp,
                               format_func=lambda x: "Sem comparativo" if x == "—" else opcoes.get(x, x))

    liberacoes = repo_dados.buscar_liberacoes(mes_sel)
    if not liberacoes:
        st.warning("Nenhum dado de liberações encontrado.")
        return

    df = pd.DataFrame(liberacoes)

    lib_ant = None
    if mes_ant != "—":
        dados_ant = repo_dados.buscar_liberacoes(mes_ant)
        if dados_ant:
            lib_ant = pd.DataFrame(dados_ant)

    _dashboard_liberacoes(df, lib_ant, nome_mes(mes_sel),
                          nome_mes(mes_ant) if mes_ant != "—" else None)


def _dashboard_liberacoes(df: pd.DataFrame, df_ant: pd.DataFrame | None, periodo: str, periodo_ant: str | None):
    import plotly.graph_objects as go

    # Cálculos
    def _calc(d):
        total = len(d)
        qtd_dir = len(d[d["tipo"] == "DIRETO"])
        qtd_lib = len(d[d["tipo"] == "LIBERADO"])
        qtd_neg = len(d[d["tipo"] == "NEGADO"])
        vlr_dir = d[d["tipo"] == "DIRETO"]["vlr_pedido"].sum()
        vlr_lib = d[d["tipo"] == "LIBERADO"]["vlr_pedido"].sum()
        vlr_neg = d[d["tipo"] == "NEGADO"]["vlr_pedido"].sum()
        return {
            "total": total,
            "qtd_direto": qtd_dir, "pct_direto": qtd_dir / total * 100 if total else 0,
            "qtd_liberados": qtd_lib, "pct_liberados": qtd_lib / total * 100 if total else 0,
            "qtd_negados": qtd_neg, "pct_negados": qtd_neg / total * 100 if total else 0,
            "vlr_aprovado": vlr_dir + vlr_lib, "vlr_negado": vlr_neg,
        }

    atual = _calc(df)
    ant = _calc(df_ant) if df_ant is not None else None

    st.markdown(f"**{periodo}** · {atual['total']:,} pedidos processados")
    if periodo_ant:
        st.caption(f"Comparando com: {periodo_ant}")
    st.markdown("<br>", unsafe_allow_html=True)

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (c1, "Total Pedidos", f"{atual['total']:,}", "no período", COR_AZUL),
        (c2, "Passaram Direto", f"{atual['pct_direto']:.1f}%", f"{atual['qtd_direto']:,} pedidos", COR_VERDE),
        (c3, "Liberados", f"{atual['pct_liberados']:.1f}%", f"{atual['qtd_liberados']:,} pedidos", COR_AZUL),
        (c4, "Negados", f"{atual['pct_negados']:.1f}%", f"{atual['qtd_negados']:,} pedidos", COR_VERMELHO),
    ]
    for col, titulo, valor, sub, cor in kpis:
        with col:
            st.markdown(card_kpi(titulo, valor, sub, cor), unsafe_allow_html=True)

    # Comparativo
    if ant:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Variação vs {periodo_ant}</h4>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            var_dir = atual["pct_direto"] - ant["pct_direto"]
            st.markdown(
                f"<div style='text-align:center; padding:12px; background:#F8F9FA; border-radius:8px;'>"
                f"<div style='font-size:12px; color:#666;'>Passaram Direto</div>"
                f"<div style='font-size:18px; font-weight:700;'>{badge_variacao(var_dir, True)}</div>"
                f"<div style='font-size:11px; color:#999;'>{ant['pct_direto']:.1f}% → {atual['pct_direto']:.1f}%</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with c2:
            var_lib = atual["pct_liberados"] - ant["pct_liberados"]
            st.markdown(
                f"<div style='text-align:center; padding:12px; background:#F8F9FA; border-radius:8px;'>"
                f"<div style='font-size:12px; color:#666;'>Liberados</div>"
                f"<div style='font-size:18px; font-weight:700;'>{badge_variacao(var_lib, False)}</div>"
                f"<div style='font-size:11px; color:#999;'>{ant['pct_liberados']:.1f}% → {atual['pct_liberados']:.1f}%</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with c3:
            var_neg = atual["pct_negados"] - ant["pct_negados"]
            st.markdown(
                f"<div style='text-align:center; padding:12px; background:#F8F9FA; border-radius:8px;'>"
                f"<div style='font-size:12px; color:#666;'>Negados</div>"
                f"<div style='font-size:18px; font-weight:700;'>{badge_variacao(var_neg, False)}</div>"
                f"<div style='font-size:11px; color:#999;'>{ant['pct_negados']:.1f}% → {atual['pct_negados']:.1f}%</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Gráficos
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Distribuição de Pedidos</h4>", unsafe_allow_html=True)
        labels = ["Passaram Direto", "Liberados", "Negados"]
        values = [atual["qtd_direto"], atual["qtd_liberados"], atual["qtd_negados"]]
        cores = [COR_VERDE, COR_AZUL, COR_VERMELHO]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.45,
            marker_colors=cores,
            textinfo="label+percent",
        ))
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_g2:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Valor dos Pedidos</h4>", unsafe_allow_html=True)
        fig2 = go.Figure(go.Bar(
            x=["Aprovado Direto", "Liberado Analista", "Negado"],
            y=[atual["vlr_aprovado"] - atual.get("vlr_direto", atual["vlr_aprovado"]),
               0, atual["vlr_negado"]],
            marker_color=[COR_VERDE, COR_AZUL, COR_VERMELHO],
        ))
        # Simplificado: 3 barras com valores reais
        vlr_dir = float(df[df["tipo"] == "DIRETO"]["vlr_pedido"].sum())
        vlr_lib = float(df[df["tipo"] == "LIBERADO"]["vlr_pedido"].sum())
        vlr_neg = float(df[df["tipo"] == "NEGADO"]["vlr_pedido"].sum())
        fig2 = go.Figure(go.Bar(
            x=["Direto", "Liberado", "Negado"],
            y=[vlr_dir, vlr_lib, vlr_neg],
            marker_color=[COR_VERDE, COR_AZUL, COR_VERMELHO],
            text=[formatar_brl(v) for v in [vlr_dir, vlr_lib, vlr_neg]],
            textposition="outside",
        ))
        fig2.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=10),
            plot_bgcolor="white", showlegend=False,
            yaxis=dict(showgrid=True, gridcolor="#EEE", tickprefix="R$ ", tickformat=",.0f"),
        )
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # Ranking analistas
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Ranking de Analistas</h3>", unsafe_allow_html=True)

    df_lib = df[df["tipo"] == "LIBERADO"].copy()
    if "analista" in df_lib.columns and not df_lib["analista"].isna().all():
        ranking = (
            df_lib.dropna(subset=["analista"])
            .groupby("analista")
            .agg(qtd=("vlr_pedido", "count"), valor=("vlr_pedido", "sum"))
            .sort_values("qtd", ascending=False)
            .reset_index()
        )
        ranking["valor_fmt"] = ranking["valor"].apply(formatar_brl)
        ranking.rename(columns={"analista": "Analista", "qtd": "Liberações", "valor_fmt": "Valor Liberado"}, inplace=True)
        st.dataframe(ranking[["Analista", "Liberações", "Valor Liberado"]], use_container_width=True, hide_index=True)

    # Exportar PPT
    st.markdown("---")
    _botao_ppt_credito(atual, df, periodo)


def _botao_ppt_credito(atual: dict, df: pd.DataFrame, periodo: str):
    from src.servicos.gerador_ppt import gerar_ppt_credito

    df_lib = df[df["tipo"] == "LIBERADO"] if "tipo" in df.columns else df
    ranking = []
    if "analista" in df_lib.columns:
        r = (
            df_lib.dropna(subset=["analista"])
            .groupby("analista")
            .agg(qtd=("vlr_pedido", "count"), valor=("vlr_pedido", "sum"))
            .sort_values("qtd", ascending=False)
            .reset_index()
        )
        ranking = r.to_dict("records")

    dados = {
        "liberacoes": {**atual, "ranking_analistas": ranking},
        "df_liberacoes": df,
        "limites": {},
        "df_limites": pd.DataFrame(),
    }
    if st.button("📊 Exportar PPT", key="ppt_cred"):
        with st.spinner("Gerando apresentação..."):
            ppt_bytes = gerar_ppt_credito(dados, periodo)
        st.download_button(
            "⬇ Baixar Apresentação",
            data=ppt_bytes,
            file_name=f"LLE_Credito_{periodo.replace('/', '-')}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
