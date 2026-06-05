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

    # ─── Recorrências (Fornecedor + Serviço mês a mês) ────────────
    st.markdown(f"### 🔁 Recorrências — comparativo de TODOS os fornecedores mês a mês")
    st.caption(
        "Agrupa por **fornecedor + descrição do serviço**. Cada combinação é um "
        "'serviço recorrente'. Mostra todos lado a lado pra você comparar valores "
        "e detectar variações."
    )

    # Pega histórico do ano + ano de comparação
    anos_para_recorrencia = [ano_foco]
    if ano_compara:
        anos_para_recorrencia.append(ano_compara)
    df_rec = df[df["ano"].isin(anos_para_recorrencia)].copy()

    if df_rec.empty:
        st.info("Sem dados pra mostrar recorrências.")
    else:
        # Normaliza descrição (remove pontuação, maiúsculas)
        import re as _re
        def _normalizar(s):
            if not s:
                return "(sem descrição)"
            s = str(s).upper().strip()
            s = _re.sub(r"[^\w\s]", " ", s)
            s = _re.sub(r"\s+", " ", s)
            return s.strip() or "(sem descrição)"

        df_rec["descricao_norm"] = df_rec["descricao_servico"].apply(_normalizar)
        df_rec["servico_chave"] = (
            df_rec["nome_fornecedor"].fillna("") + " — " +
            df_rec["descricao_norm"].str.slice(0, 60)
        )

        # Filtro: incluir não-recorrentes (apareceram 1 vez só)?
        col_filt1, col_filt2 = st.columns([1, 1])
        with col_filt1:
            min_meses = st.selectbox(
                "Mostrar serviços que apareceram em pelo menos",
                [1, 2, 3, 6],
                index=1,  # default: 2 meses
                format_func=lambda n: f"{n} mês(es)",
                key="fin_rec_min_meses",
            )
        with col_filt2:
            ordenar_por = st.selectbox(
                "Ordenar por",
                ["Maior gasto total", "Nome do fornecedor", "Mais meses ativos"],
                key="fin_rec_ordem",
            )

        # Agrupa por (fornecedor + descrição)
        grupos = df_rec.groupby(
            ["nome_fornecedor", "cnpj_fornecedor", "descricao_norm", "servico_chave"]
        ).agg(
            meses_distintos=("mes_ano", "nunique"),
            total_geral=("valor", "sum"),
            primeira_descricao=("descricao_servico", "first"),
        ).reset_index()

        recorrentes = grupos[grupos["meses_distintos"] >= min_meses].copy()

        if recorrentes.empty:
            st.info(f"🔎 Nenhum serviço com pelo menos {min_meses} mês(es) ainda.")
        else:
            # Ordenação
            if ordenar_por == "Maior gasto total":
                recorrentes = recorrentes.sort_values("total_geral", ascending=False)
            elif ordenar_por == "Nome do fornecedor":
                recorrentes = recorrentes.sort_values(["nome_fornecedor", "descricao_norm"])
            else:
                recorrentes = recorrentes.sort_values(
                    ["meses_distintos", "total_geral"], ascending=[False, False]
                )

            st.caption(
                f"📊 **{len(recorrentes)}** serviço(s) detectado(s)."
            )

            # ═══ TABELA CRUZADA: serviço × mês ═══════════════════════════
            st.markdown(f"#### 📋 Tabela comparativa mês a mês")

            # Lista de meses presentes (ordenados)
            meses_lista = sorted(df_rec["mes_ano"].unique())

            # Pra cada serviço, soma os valores por mês
            linhas_tabela = []
            for _, grupo in recorrentes.iterrows():
                lancs = df_rec[
                    (df_rec["nome_fornecedor"] == grupo["nome_fornecedor"])
                    & (df_rec["cnpj_fornecedor"] == grupo["cnpj_fornecedor"])
                    & (df_rec["descricao_norm"] == grupo["descricao_norm"])
                ]

                por_mes = lancs.groupby("mes_ano")["valor"].sum().to_dict()

                row = {
                    "Fornecedor": grupo["nome_fornecedor"],
                    "Serviço": (grupo["primeira_descricao"] or "(sem descrição)")[:55],
                }
                for m in meses_lista:
                    valor_m = por_mes.get(m, 0)
                    row[f"{nome_mes(m)[:3]}/{m[2:4]}"] = (
                        formatar_brl(valor_m) if valor_m > 0 else "—"
                    )
                row["Total"] = formatar_brl(grupo["total_geral"])
                row["Meses"] = int(grupo["meses_distintos"])
                linhas_tabela.append(row)

            df_cruzada = pd.DataFrame(linhas_tabela)
            st.dataframe(df_cruzada, use_container_width=True, hide_index=True)

            # Total geral por mês (rodapé)
            totais_mes = {}
            for m in meses_lista:
                totais_mes[m] = df_rec[df_rec["mes_ano"] == m]["valor"].sum()

            rodape = {"Fornecedor": "**TOTAL GERAL**", "Serviço": ""}
            for m in meses_lista:
                rodape[f"{nome_mes(m)[:3]}/{m[2:4]}"] = formatar_brl(totais_mes[m])
            rodape["Total"] = formatar_brl(sum(totais_mes.values()))
            rodape["Meses"] = ""

            st.caption("**Soma por mês (todos os serviços):**")
            st.dataframe(pd.DataFrame([rodape]), use_container_width=True, hide_index=True)

            # ═══ GRÁFICO DE LINHAS: todos os serviços juntos ═══════════════
            st.markdown(f"#### 📈 Gráfico — evolução de todos os fornecedores")

            # Monta dataset longo (pra plotly)
            dados_long = []
            for _, grupo in recorrentes.iterrows():
                lancs = df_rec[
                    (df_rec["nome_fornecedor"] == grupo["nome_fornecedor"])
                    & (df_rec["cnpj_fornecedor"] == grupo["cnpj_fornecedor"])
                    & (df_rec["descricao_norm"] == grupo["descricao_norm"])
                ]
                por_mes = lancs.groupby("mes_ano")["valor"].sum()
                rotulo = f"{grupo['nome_fornecedor']} — {(grupo['primeira_descricao'] or '(s/desc)')[:35]}"
                for m in meses_lista:
                    dados_long.append({
                        "Mês": f"{nome_mes(m)[:3]}/{m[2:4]}",
                        "Serviço": rotulo,
                        "Valor": float(por_mes.get(m, 0)),
                    })

            df_plot = pd.DataFrame(dados_long)

            fig_rec = px.line(
                df_plot,
                x="Mês",
                y="Valor",
                color="Serviço",
                markers=True,
                labels={"Valor": "Total (R$)"},
            )
            fig_rec.update_layout(
                height=450,
                margin=dict(t=10, b=10),
                legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(fig_rec, use_container_width=True)

            # ═══ DETALHE EXPANSÍVEL DE CADA SERVIÇO ═══════════════
            st.markdown(f"#### 🔍 Detalhar serviço individual")

            opcoes_servico = {
                f"{g['nome_fornecedor']} — {(g['primeira_descricao'] or '(s/desc)')[:60]} "
                f"({g['meses_distintos']} mês, {formatar_brl(g['total_geral'])})": g
                for _, g in recorrentes.iterrows()
            }

            servico_escolhido = st.selectbox(
                "Escolha um serviço pra ver detalhes",
                list(opcoes_servico.keys()),
                key="fin_rec_serv_detalhe",
            )

            g = opcoes_servico[servico_escolhido]
            lancs = df_rec[
                (df_rec["nome_fornecedor"] == g["nome_fornecedor"])
                & (df_rec["cnpj_fornecedor"] == g["cnpj_fornecedor"])
                & (df_rec["descricao_norm"] == g["descricao_norm"])
            ].sort_values("mes_ano")

            por_mes_serv = lancs.groupby("mes_ano")["valor"].sum().reset_index().sort_values("mes_ano")

            rows = []
            valor_anterior = None
            for _, lin in por_mes_serv.iterrows():
                mes_str = lin["mes_ano"]
                valor_mes = float(lin["valor"])
                if valor_anterior is not None and valor_anterior > 0:
                    var = (valor_mes - valor_anterior) / valor_anterior * 100
                    var_str = f"{var:+.1f}%"
                    if abs(var) > 20:
                        var_str = f"⚠️ {var_str}"
                else:
                    var_str = "—"
                rows.append({
                    "Mês": f"{nome_mes(mes_str)}/{mes_str[:4]}",
                    "Valor": formatar_brl(valor_mes),
                    "Variação vs mês anterior": var_str,
                })
                valor_anterior = valor_mes

            col_d1, col_d2 = st.columns([2, 3])
            with col_d1:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                valor_medio = lancs["valor"].mean()
                valor_min = lancs["valor"].min()
                valor_max = lancs["valor"].max()
                st.caption(
                    f"📊 Média: **{formatar_brl(valor_medio)}** · "
                    f"Mín: {formatar_brl(valor_min)} · Máx: {formatar_brl(valor_max)}"
                )

            with col_d2:
                por_mes_serv["mes_label"] = por_mes_serv["mes_ano"].apply(
                    lambda m: f"{nome_mes(m)[:3]}/{m[2:4]}"
                )
                fig_serv = px.bar(
                    por_mes_serv,
                    x="mes_label",
                    y="valor",
                    text_auto=".2s",
                    labels={"valor": "R$", "mes_label": "Mês"},
                    color_discrete_sequence=[AZUL_ESCURO],
                )
                fig_serv.update_layout(height=300, margin=dict(t=10, b=10))
                fig_serv.update_traces(textposition="outside")
                st.plotly_chart(fig_serv, use_container_width=True)

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
