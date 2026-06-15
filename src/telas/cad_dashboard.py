"""
Tela Cadastros · Dashboard.

Indicadores profundos:
  - KPIs (total, ano atual, mês atual, % comparativo)
  - Distribuição por canal (cards + pizza + barras)
  - Tabela cruzada: canal x mês
  - Evolução mensal por canal (linhas)
  - Comparativo ano a ano
  - Drill-down: lista de cadastros por canal/período
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from src.banco import repo_cadastros
from src.utils.formatadores import nome_mes
from src.utils.marca import AZUL_ESCURO


def renderizar_cad_dashboard(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📊 Cadastros · Dashboard</h1>",
        unsafe_allow_html=True,
    )

    # Conta no banco PRIMEIRO (mais rápido que listar tudo)
    total_no_banco = repo_cadastros.contar_cadastros()

    if total_no_banco == 0:
        st.info("📭 Nenhum cadastro registrado. Vá em **📥 Upload** pra carregar a planilha.")
        return

    dados = repo_cadastros.listar_cadastros()

    if not dados:
        st.error(
            f"⚠️ O banco tem **{total_no_banco}** cadastros, mas a query não retornou nada. "
            f"Pode ser problema de permissão (RLS) ou erro de conexão. Recarregue a página."
        )
        return

    if len(dados) < total_no_banco:
        st.warning(
            f"⚠️ Lendo apenas **{len(dados):,}** de **{total_no_banco:,}** cadastros do banco. "
            "Recarregue a página se faltar algo."
        )

    df = pd.DataFrame(dados)
    df["data_cadastramento"] = pd.to_datetime(df["data_cadastramento"])
    df["ano"] = df["data_cadastramento"].dt.year
    df["mes"] = df["data_cadastramento"].dt.month
    df["mes_ano"] = df["data_cadastramento"].dt.strftime("%Y-%m")
    df["canal"] = df["canal_origem"].fillna("(sem canal)")

    # ─── Filtros de período no topo ──────────
    col_f1, col_f2, col_f3 = st.columns(3)
    anos_disponiveis = sorted(df["ano"].unique(), reverse=True)

    with col_f1:
        ano_foco = st.selectbox(
            "📅 Ano",
            ["Todos"] + anos_disponiveis,
            index=1 if len(anos_disponiveis) > 0 else 0,
            key="cad_ano_foco",
        )

    with col_f2:
        canais_disponiveis = sorted(df["canal"].unique())
        canais_sel = st.multiselect(
            "🎯 Filtrar Canais",
            canais_disponiveis,
            default=canais_disponiveis,
            key="cad_canais_sel",
        )

    with col_f3:
        # Comparar com outro ano
        if len(anos_disponiveis) > 1:
            ano_compara = st.selectbox(
                "🔄 Comparar com",
                ["(nenhum)"] + [a for a in anos_disponiveis if a != ano_foco],
                key="cad_ano_compara",
            )
        else:
            ano_compara = "(nenhum)"

    # Aplica filtros
    df_filt = df[df["canal"].isin(canais_sel)].copy()
    if ano_foco != "Todos":
        df_filt = df_filt[df_filt["ano"] == ano_foco]

    if df_filt.empty:
        st.warning("Nenhum cadastro com esses filtros.")
        return

    # ═══════════════════════════════════════════════════
    # KPIs gerais
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📌 Indicadores")

    total = len(df_filt)
    hoje = date.today()
    mes_atual_str = f"{hoje.year:04d}-{hoje.month:02d}"
    cadastros_mes_atual = (df_filt["mes_ano"] == mes_atual_str).sum()

    # Mês anterior pra comparar
    mes_ant = hoje.month - 1 if hoje.month > 1 else 12
    ano_ant = hoje.year if hoje.month > 1 else hoje.year - 1
    mes_ant_str = f"{ano_ant:04d}-{mes_ant:02d}"
    cadastros_mes_ant = (df_filt["mes_ano"] == mes_ant_str).sum()

    if cadastros_mes_ant > 0:
        var_pct = (cadastros_mes_atual - cadastros_mes_ant) / cadastros_mes_ant * 100
        var_str = f"{var_pct:+.1f}% vs mês anterior"
    else:
        var_str = "—"

    media_mes = df_filt.groupby("mes_ano").size().mean()

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    with col_k1:
        st.metric("Total no período", f"{total:,}".replace(",", "."))
    with col_k2:
        st.metric(f"Mês atual ({nome_mes(mes_atual_str)})", cadastros_mes_atual, var_str)
    with col_k3:
        st.metric("Média mensal", f"{media_mes:.0f}")
    with col_k4:
        st.metric("Canais ativos", df_filt["canal"].nunique())

    # ═══════════════════════════════════════════════════
    # Distribuição por Canal (cards + pizza + barras)
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🎯 Distribuição por Canal de Origem")

    por_canal = df_filt.groupby("canal").size().sort_values(ascending=False)
    cols_cards = st.columns(min(len(por_canal), 5))
    for i, (canal, qtd) in enumerate(por_canal.items()):
        with cols_cards[i % len(cols_cards)]:
            cor = repo_cadastros.cor_canal(canal if canal != "(sem canal)" else None)
            emoji = repo_cadastros.emoji_canal(canal if canal != "(sem canal)" else None)
            pct = qtd / total * 100 if total else 0
            st.markdown(
                f"""<div style='background:{cor}; color:white; padding:14px;
                border-radius:8px; margin-bottom:10px; text-align:center;'>
                <div style='font-size:28px;'>{emoji}</div>
                <div style='font-size:13px; font-weight:600; margin:4px 0;'>{canal}</div>
                <div style='font-size:22px; font-weight:700;'>{qtd}</div>
                <div style='font-size:12px; opacity:0.9;'>{pct:.1f}% do total</div>
                </div>""",
                unsafe_allow_html=True,
            )

    col_p, col_b = st.columns(2)
    cores_map = {c: repo_cadastros.cor_canal(c if c != "(sem canal)" else None) for c in por_canal.index}

    with col_p:
        st.markdown("##### 🥧 Proporção")
        fig_pie = px.pie(
            names=por_canal.index, values=por_canal.values,
            color=por_canal.index, color_discrete_map=cores_map, hole=0.4,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(height=350, margin=dict(t=10, b=10), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.markdown("##### 📊 Total por Canal")
        df_bar = por_canal.reset_index()
        df_bar.columns = ["Canal", "Qtd"]
        fig_bar = px.bar(
            df_bar, x="Qtd", y="Canal", orientation="h",
            color="Canal", color_discrete_map=cores_map, text_auto=True,
        )
        fig_bar.update_layout(
            height=350, margin=dict(t=10, b=10), showlegend=False,
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ═══════════════════════════════════════════════════
    # Tabela cruzada: Canal × Mês
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📅 Cadastros mês a mês — por Canal")
    st.caption(
        "Linhas = canal. Colunas = meses. Pra ver quantos cadastros cada canal trouxe por mês."
    )

    meses_lista = sorted(df_filt["mes_ano"].unique())
    pivot = (df_filt.groupby(["canal", "mes_ano"]).size()
             .unstack(fill_value=0)
             .reindex(columns=meses_lista, fill_value=0))

    # Constrói tabela
    rows = []
    for canal in pivot.index:
        row = {"Canal": canal}
        total_canal = 0
        for m in meses_lista:
            v = int(pivot.at[canal, m])
            row[f"{nome_mes(m)[:3]}/{m[2:4]}"] = v
            total_canal += v
        row["Total"] = total_canal
        rows.append(row)

    # Linha de totais
    totais_row = {"Canal": "TOTAL DO MÊS"}
    soma_total = 0
    for m in meses_lista:
        t = int(pivot[m].sum())
        totais_row[f"{nome_mes(m)[:3]}/{m[2:4]}"] = t
        soma_total += t
    totais_row["Total"] = soma_total
    rows.append(totais_row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════
    # Evolução mensal por canal (linhas)
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📈 Evolução mensal por Canal")

    df_evol = (df_filt.groupby(["mes_ano", "canal"]).size()
               .reset_index(name="qtd"))
    df_evol["mes_label"] = df_evol["mes_ano"].apply(lambda m: f"{nome_mes(m)[:3]}/{m[2:4]}")
    df_evol = df_evol.sort_values("mes_ano")

    fig_evol = px.line(
        df_evol, x="mes_label", y="qtd", color="canal",
        color_discrete_map=cores_map, markers=True,
        labels={"qtd": "Cadastros", "mes_label": "Mês", "canal": "Canal"},
    )
    fig_evol.update_layout(height=400, margin=dict(t=10, b=10))
    st.plotly_chart(fig_evol, use_container_width=True)

    # ═══════════════════════════════════════════════════
    # Comparativo ano a ano (se houver outro ano selecionado)
    # ═══════════════════════════════════════════════════
    if ano_compara != "(nenhum)" and ano_compara in anos_disponiveis:
        st.markdown("---")
        st.markdown(f"### 🔄 Comparativo {ano_foco} vs {ano_compara}")

        df_compara = df[df["canal"].isin(canais_sel) & df["ano"].isin([ano_foco, ano_compara])].copy()

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown(f"##### Por mês")
            comp_mes = (df_compara.groupby(["ano", "mes"]).size()
                        .reset_index(name="qtd"))
            comp_mes["mes_nome"] = comp_mes["mes"].apply(
                lambda m: nome_mes(f"2026-{m:02d}")[:3]
            )
            fig_comp = px.bar(
                comp_mes, x="mes_nome", y="qtd", color="ano", barmode="group",
                labels={"qtd": "Cadastros", "mes_nome": "Mês", "ano": "Ano"},
                color_discrete_sequence=[AZUL_ESCURO, "#FAC318"],
            )
            fig_comp.update_layout(height=350, margin=dict(t=10, b=10))
            st.plotly_chart(fig_comp, use_container_width=True)

        with col_c2:
            st.markdown(f"##### Por canal")
            comp_canal = (df_compara.groupby(["ano", "canal"]).size()
                          .reset_index(name="qtd"))
            fig_cc = px.bar(
                comp_canal, x="canal", y="qtd", color="ano", barmode="group",
                labels={"qtd": "Cadastros", "canal": "Canal", "ano": "Ano"},
                color_discrete_sequence=[AZUL_ESCURO, "#FAC318"],
            )
            fig_cc.update_layout(height=350, margin=dict(t=10, b=10))
            st.plotly_chart(fig_cc, use_container_width=True)

        # Resumo numérico
        totais_compara = df_compara.groupby("ano").size().to_dict()
        col_kc1, col_kc2, col_kc3 = st.columns(3)
        v_foco = totais_compara.get(ano_foco, 0)
        v_comp = totais_compara.get(ano_compara, 0)
        with col_kc1:
            st.metric(f"Total {ano_foco}", v_foco)
        with col_kc2:
            st.metric(f"Total {ano_compara}", v_comp)
        with col_kc3:
            if v_comp > 0:
                dif = (v_foco - v_comp) / v_comp * 100
                st.metric("Variação", f"{dif:+.1f}%")
            else:
                st.metric("Variação", "—")

    # ═══════════════════════════════════════════════════
    # Drill-down: lista de cadastros
    # ═══════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 🔍 Detalhar — lista de cadastros")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        canal_drill = st.selectbox(
            "Canal pra ver detalhes",
            ["Todos"] + sorted(df_filt["canal"].unique()),
            key="cad_drill_canal",
        )
    with col_d2:
        mes_drill = st.selectbox(
            "Mês",
            ["Todos"] + meses_lista,
            format_func=lambda m: m if m == "Todos" else f"{nome_mes(m)}/{m[:4]}",
            key="cad_drill_mes",
        )

    df_drill = df_filt.copy()
    if canal_drill != "Todos":
        df_drill = df_drill[df_drill["canal"] == canal_drill]
    if mes_drill != "Todos":
        df_drill = df_drill[df_drill["mes_ano"] == mes_drill]

    df_drill = df_drill.sort_values("data_cadastramento", ascending=False)

    rows_drill = []
    for _, row in df_drill.iterrows():
        rows_drill.append({
            "Data": row["data_cadastramento"].strftime("%d/%m/%Y"),
            "Cód. Parceiro": int(row["cod_parceiro"]),
            "Nome Parceiro": row["nome_parceiro"],
            "Canal": row["canal"],
        })

    st.caption(f"📋 {len(rows_drill)} cadastro(s) listados")
    st.dataframe(pd.DataFrame(rows_drill), use_container_width=True, hide_index=True)
