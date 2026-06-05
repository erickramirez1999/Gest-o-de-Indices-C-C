"""
Tela Financeiro · Comparativos e Dashboard

Mostra:
  - Evolução mês a mês (12 meses do ano)
  - Comparativo ano vs ano (esse ano vs anterior)
  - Quebra por categoria (evolução ao longo do tempo)
  - Quebra por fornecedor (top 10)
  - Quebra por empresa LLE (PISA/KING/TRIO)
  - KPIs gerais
"""
from __future__ import annotations

import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE


def _carregar_todos_gastos() -> pd.DataFrame:
    """Busca todos os lançamentos como DataFrame."""
    sb = obter_conexao()
    res = sb.table("dados_financeiro_gasto").select("*").execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df["valor"] = df["valor"].astype(float)
    df["ano"] = df["mes_ano"].str[:4].astype(int)
    df["mes"] = df["mes_ano"].str[5:7].astype(int)
    return df


def renderizar_fin_comparativos(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📈 Financeiro · Comparativos e Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Veja a evolução mês a mês e compare anos pra orçar o próximo período."
    )

    df = _carregar_todos_gastos()
    if df.empty:
        st.info(
            "📭 Nenhum gasto cadastrado ainda. Vá em **💼 Upload de NFs** "
            "ou **✍️ Cadastro Manual** pra começar."
        )
        return

    anos_disponiveis = sorted(df["ano"].unique(), reverse=True)
    ano_atual = datetime.date.today().year

    # ─── Seletor de ano ─────────────────────────
    col_ano, col_comp = st.columns([1, 1])
    with col_ano:
        ano_foco = st.selectbox(
            "🗓️ Ano em análise",
            anos_disponiveis,
            index=anos_disponiveis.index(ano_atual) if ano_atual in anos_disponiveis else 0,
            key="fin_comp_ano",
        )
    with col_comp:
        anos_para_comp = [a for a in anos_disponiveis if a != ano_foco]
        if anos_para_comp:
            ano_compara = st.selectbox(
                "📊 Comparar com",
                anos_para_comp,
                index=0,
                key="fin_comp_outro",
            )
        else:
            ano_compara = None
            st.caption("Sem outro ano disponível pra comparação ainda.")

    df_ano = df[df["ano"] == ano_foco]
    df_compara = df[df["ano"] == ano_compara] if ano_compara else pd.DataFrame()

    # ─── KPIs principais ─────────────────────────
    st.markdown("### 📊 Visão geral")

    total_ano = df_ano["valor"].sum()
    total_compara = df_compara["valor"].sum() if not df_compara.empty else 0
    qtd_lanc = len(df_ano)
    fornecedores_ativos = df_ano["fornecedor_id"].nunique()

    delta_pct = None
    if total_compara > 0:
        delta_pct = (total_ano - total_compara) / total_compara * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        f"💰 Total {ano_foco}",
        formatar_brl(total_ano),
        delta=f"{delta_pct:+.1f}% vs {ano_compara}" if delta_pct is not None else None,
        delta_color="inverse",  # gasto maior = vermelho
    )
    c2.metric(
        "📊 Média/mês",
        formatar_brl(total_ano / max(df_ano["mes"].nunique(), 1)),
    )
    c3.metric("📄 Lançamentos", qtd_lanc)
    c4.metric("🏢 Fornecedores", fornecedores_ativos)

    st.markdown("---")

    # ─── Evolução mês a mês (ano em foco) ─────────────────────────
    st.markdown(f"### 📈 Evolução mensal — {ano_foco}")

    # Monta DF com 12 meses (preenche zero onde não tem dado)
    meses_completos = pd.DataFrame({"mes": range(1, 13)})
    por_mes_foco = (df_ano.groupby("mes")["valor"].sum().reindex(range(1, 13), fill_value=0)).reset_index()
    por_mes_foco["ano"] = ano_foco

    if not df_compara.empty:
        por_mes_compara = (
            df_compara.groupby("mes")["valor"].sum().reindex(range(1, 13), fill_value=0)
        ).reset_index()
        por_mes_compara["ano"] = ano_compara
        plot_data = pd.concat([por_mes_foco, por_mes_compara], ignore_index=True)
    else:
        plot_data = por_mes_foco

    plot_data["mes_nome"] = plot_data["mes"].apply(
        lambda m: nome_mes(f"2026-{m:02d}")[:3]
    )

    fig = px.bar(
        plot_data,
        x="mes_nome",
        y="valor",
        color="ano",
        barmode="group",
        text_auto=".2s",
        labels={"valor": "Total (R$)", "mes_nome": "Mês", "ano": "Ano"},
        color_discrete_map={
            ano_foco: AZUL_ESCURO,
            ano_compara: AMARELO if ano_compara else AZUL_ESCURO,
        },
    )
    fig.update_layout(
        height=380,
        showlegend=bool(ano_compara),
        margin=dict(t=10, b=10),
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Tabela de variação mensal
    if not df_compara.empty:
        st.markdown("#### Variação mês a mês")
        var_rows = []
        for m in range(1, 13):
            v_foco = por_mes_foco[por_mes_foco["mes"] == m]["valor"].iloc[0] if not por_mes_foco.empty else 0
            v_comp = por_mes_compara[por_mes_compara["mes"] == m]["valor"].iloc[0] if not por_mes_compara.empty else 0
            if v_foco == 0 and v_comp == 0:
                continue
            var = ((v_foco - v_comp) / v_comp * 100) if v_comp > 0 else None
            var_rows.append({
                "Mês": nome_mes(f"2026-{m:02d}"),
                f"{ano_compara}": formatar_brl(v_comp),
                f"{ano_foco}": formatar_brl(v_foco),
                "Diferença": formatar_brl(v_foco - v_comp),
                "Variação": f"{var:+.1f}%" if var is not None else "—",
            })
        if var_rows:
            st.dataframe(pd.DataFrame(var_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ─── Por Categoria ─────────────────────────
    st.markdown(f"### 🏷️ Por Categoria — {ano_foco}")

    col_cat1, col_cat2 = st.columns([2, 3])

    por_cat = df_ano.groupby("categoria", dropna=False)["valor"].sum().sort_values(ascending=False)

    with col_cat1:
        st.markdown("**Total por categoria**")
        rows = []
        for cat, val in por_cat.items():
            rows.append({
                "Categoria": cat or "—",
                "Total": formatar_brl(val),
                "%": f"{val / total_ano * 100:.1f}%" if total_ano else "0%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with col_cat2:
        # Pizza
        if not por_cat.empty:
            fig_pizza = px.pie(
                values=por_cat.values,
                names=[c or "—" for c in por_cat.index],
                hole=0.45,
            )
            fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
            fig_pizza.update_layout(height=350, margin=dict(t=10, b=10), showlegend=False)
            st.plotly_chart(fig_pizza, use_container_width=True)

    # Evolução das TOP 5 categorias no ano
    top5_cats = por_cat.head(5).index.tolist()
    if top5_cats:
        st.markdown("#### Evolução mensal das principais categorias")
        ev_data = (df_ano[df_ano["categoria"].isin(top5_cats)]
                   .groupby(["mes", "categoria"])["valor"].sum().reset_index())
        ev_data["mes_nome"] = ev_data["mes"].apply(lambda m: nome_mes(f"2026-{m:02d}")[:3])

        fig_ev = px.line(
            ev_data,
            x="mes_nome",
            y="valor",
            color="categoria",
            markers=True,
            labels={"valor": "Total (R$)", "mes_nome": "Mês", "categoria": "Categoria"},
        )
        fig_ev.update_layout(height=350, margin=dict(t=10, b=10))
        st.plotly_chart(fig_ev, use_container_width=True)

    st.markdown("---")

    # ─── Por Fornecedor (Top 10) ─────────────────────────
    st.markdown(f"### 🏢 Top Fornecedores — {ano_foco}")

    por_forn = (df_ano.groupby(["nome_fornecedor", "cnpj_fornecedor"])["valor"]
                .sum().sort_values(ascending=False).head(15))

    rows = []
    for (nome, cnpj), val in por_forn.items():
        rows.append({
            "Fornecedor": nome,
            "CNPJ": cnpj,
            "Total": formatar_brl(val),
            "%": f"{val / total_ano * 100:.1f}%" if total_ano else "0%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ─── Por Empresa LLE ─────────────────────────
    st.markdown(f"### 🏛️ Por Empresa LLE — {ano_foco}")

    por_emp = df_ano.groupby("empresa_lle", dropna=False)["valor"].sum().sort_values(ascending=False)
    if not por_emp.empty:
        col_e1, col_e2 = st.columns([2, 3])
        with col_e1:
            rows = []
            for emp, val in por_emp.items():
                rows.append({
                    "Empresa": emp or "—",
                    "Total": formatar_brl(val),
                    "%": f"{val / total_ano * 100:.1f}%" if total_ano else "0%",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with col_e2:
            # Cores oficiais LLE
            cores_emp = {
                "PISA": "#041747",
                "KING": "#FAC318",
                "TRIO": "#0F8C3B",
                None: "#888888",
                "OUTRO": "#888888",
            }
            fig_emp = px.bar(
                x=[e or "—" for e in por_emp.index],
                y=por_emp.values,
                color=[e or "—" for e in por_emp.index],
                color_discrete_map={(e or "—"): cores_emp.get(e, "#888") for e in por_emp.index},
                text_auto=".2s",
                labels={"x": "Empresa", "y": "Total (R$)"},
            )
            fig_emp.update_layout(height=300, showlegend=False, margin=dict(t=10, b=10))
            fig_emp.update_traces(textposition="outside")
            st.plotly_chart(fig_emp, use_container_width=True)

    st.markdown("---")

    # ─── Projeção pro ano (orçamento próximo) ─────────────────────────
    st.markdown(f"### 🔮 Projeção e referência pra orçamento")

    meses_com_dado = df_ano[df_ano["valor"] > 0]["mes"].nunique()
    if meses_com_dado > 0:
        media_mensal = total_ano / meses_com_dado
        projecao_ano = media_mensal * 12

        col_p1, col_p2, col_p3 = st.columns(3)
        col_p1.metric("Meses com dados", meses_com_dado)
        col_p2.metric("Média mensal real", formatar_brl(media_mensal))
        col_p3.metric(
            f"Projeção fim de {ano_foco}",
            formatar_brl(projecao_ano),
            help="Média mensal × 12. Use como referência pra orçar o ano seguinte.",
        )

        st.info(
            f"💡 Pra orçar **{ano_foco + 1}**, considere a projeção de "
            f"**{formatar_brl(projecao_ano)}** como base. Inflação e novos "
            f"contratos devem ser adicionados separadamente."
        )

    # ─── Botão de export ─────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Exportar relatório")

    if st.button("📊 Baixar Excel completo do ano", type="primary", key="btn_export_fin"):
        try:
            from io import BytesIO
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment

            wb = openpyxl.Workbook()
            # Aba 1: Lançamentos detalhados
            ws1 = wb.active
            ws1.title = "Lancamentos"
            headers = ["Mês", "Data", "Fornecedor", "CNPJ", "Categoria",
                       "Empresa", "NF nº", "Valor", "Descrição"]
            for c, h in enumerate(headers, 1):
                cell = ws1.cell(row=1, column=c, value=h)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="041747", end_color="041747", fill_type="solid")

            for r, row in enumerate(df_ano.sort_values(["mes", "data_emissao"]).itertuples(), 2):
                ws1.cell(row=r, column=1, value=row.mes_ano)
                ws1.cell(row=r, column=2, value=str(row.data_emissao or ""))
                ws1.cell(row=r, column=3, value=row.nome_fornecedor)
                ws1.cell(row=r, column=4, value=row.cnpj_fornecedor)
                ws1.cell(row=r, column=5, value=row.categoria or "")
                ws1.cell(row=r, column=6, value=row.empresa_lle or "")
                ws1.cell(row=r, column=7, value=row.numero_nf or "")
                ws1.cell(row=r, column=8, value=float(row.valor))
                ws1.cell(row=r, column=9, value=row.descricao_servico or "")

            for col in ws1.columns:
                ws1.column_dimensions[col[0].column_letter].width = 22

            # Aba 2: Resumo mensal
            ws2 = wb.create_sheet("Resumo mensal")
            ws2.append(["Mês", "Total"])
            ws2["A1"].font = Font(bold=True)
            ws2["B1"].font = Font(bold=True)
            for m in range(1, 13):
                v = por_mes_foco[por_mes_foco["mes"] == m]["valor"].iloc[0] if not por_mes_foco.empty else 0
                ws2.append([nome_mes(f"2026-{m:02d}"), float(v)])

            # Aba 3: Por categoria
            ws3 = wb.create_sheet("Por categoria")
            ws3.append(["Categoria", "Total", "%"])
            for cat, val in por_cat.items():
                pct = (val / total_ano * 100) if total_ano else 0
                ws3.append([cat or "—", float(val), f"{pct:.1f}%"])

            # Aba 4: Top fornecedores
            ws4 = wb.create_sheet("Top fornecedores")
            ws4.append(["Fornecedor", "CNPJ", "Total", "%"])
            for (nome, cnpj), val in por_forn.items():
                pct = (val / total_ano * 100) if total_ano else 0
                ws4.append([nome, cnpj, float(val), f"{pct:.1f}%"])

            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            st.download_button(
                label=f"⬇️ Baixar relatorio_financeiro_{ano_foco}.xlsx",
                data=buffer.getvalue(),
                file_name=f"relatorio_financeiro_{ano_foco}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")
