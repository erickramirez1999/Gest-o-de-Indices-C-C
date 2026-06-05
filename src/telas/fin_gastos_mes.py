"""
Tela Financeiro · Gastos do Mês

Mostra todos os lançamentos de um mês escolhido, com:
  - Totais por categoria, por fornecedor e por empresa LLE
  - Tabela detalhada
  - Opção de excluir lançamento (com confirmação)
"""
from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from src.banco import repo_financeiro
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE


def renderizar_fin_gastos_mes(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📊 Financeiro · Gastos do Mês</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Visualize os gastos lançados em cada mês de competência.")

    # Mensagem persistente
    msg = st.session_state.pop("fin_gastos_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    # ─── Seletor de mês ─────────────────────────
    meses_existentes = repo_financeiro.meses_com_gasto()
    hoje = datetime.date.today()
    mes_atual_str = f"{hoje.year:04d}-{hoje.month:02d}"

    if not meses_existentes:
        st.info(
            "📭 Nenhum gasto cadastrado ainda. Vá em **💼 Upload de NFs** "
            "pra subir suas primeiras notas."
        )
        return

    # Garante o mês atual na lista
    if mes_atual_str not in meses_existentes:
        meses_existentes = [mes_atual_str] + meses_existentes

    mes_ano = st.selectbox(
        "🗓️ Mês de competência",
        meses_existentes,
        format_func=lambda x: f"{nome_mes(x)}/{x[:4]}",
        key="fin_gastos_mes_sel",
    )

    gastos = repo_financeiro.listar_gastos_do_mes(mes_ano)

    if not gastos:
        st.info(f"📭 Nenhum gasto lançado em **{nome_mes(mes_ano)}/{mes_ano[:4]}**.")
        return

    # ─── KPIs ─────────────────────────
    total = sum(float(g.get("valor", 0)) for g in gastos)
    qtd = len(gastos)
    fornecedores_distintos = len({g["fornecedor_id"] for g in gastos})

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total do mês", formatar_brl(total))
    c2.metric("📄 Lançamentos", qtd)
    c3.metric("🏢 Fornecedores", fornecedores_distintos)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Quebras (por categoria, fornecedor, empresa LLE) ────────────
    df = pd.DataFrame(gastos)
    df["valor"] = df["valor"].astype(float)

    col_cat, col_emp = st.columns(2)
    with col_cat:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Por Categoria</h4>", unsafe_allow_html=True)
        por_cat = df.groupby("categoria", dropna=False)["valor"].sum().sort_values(ascending=False)
        por_cat_df = pd.DataFrame({
            "Categoria": [c or "—" for c in por_cat.index],
            "Total": [formatar_brl(v) for v in por_cat.values],
            "%": [f"{v / total * 100:.1f}%" if total else "0%" for v in por_cat.values],
        })
        st.dataframe(por_cat_df, use_container_width=True, hide_index=True)

    with col_emp:
        st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Por Empresa LLE</h4>", unsafe_allow_html=True)
        por_emp = df.groupby("empresa_lle", dropna=False)["valor"].sum().sort_values(ascending=False)
        por_emp_df = pd.DataFrame({
            "Empresa": [e or "—" for e in por_emp.index],
            "Total": [formatar_brl(v) for v in por_emp.values],
            "%": [f"{v / total * 100:.1f}%" if total else "0%" for v in por_emp.values],
        })
        st.dataframe(por_emp_df, use_container_width=True, hide_index=True)

    # ─── Tabela detalhada ─────────────────────────
    st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Lançamentos detalhados</h4>", unsafe_allow_html=True)

    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        categorias = sorted({(g.get("categoria") or "—") for g in gastos})
        filtro_cat = st.multiselect(
            "Filtrar categorias",
            categorias,
            default=categorias,
            key="fin_filtro_cat",
        )
    with col_f2:
        empresas = sorted({(g.get("empresa_lle") or "—") for g in gastos})
        filtro_emp = st.multiselect(
            "Filtrar empresas LLE",
            empresas,
            default=empresas,
            key="fin_filtro_emp",
        )

    gastos_filtrados = [
        g for g in gastos
        if (g.get("categoria") or "—") in filtro_cat
        and (g.get("empresa_lle") or "—") in filtro_emp
    ]

    if not gastos_filtrados:
        st.info("Nenhum lançamento corresponde aos filtros.")
        return

    # Monta a tabela
    rows = []
    for g in gastos_filtrados:
        rows.append({
            "ID": g["id"],
            "Data": g.get("data_emissao") or "—",
            "Fornecedor": g.get("nome_fornecedor") or "—",
            "CNPJ": g.get("cnpj_fornecedor") or "—",
            "Categoria": g.get("categoria") or "—",
            "Empresa": g.get("empresa_lle") or "—",
            "NF nº": g.get("numero_nf") or "—",
            "Valor": formatar_brl(g.get("valor", 0)),
            "Descrição": (g.get("descricao_servico") or "")[:50],
        })

    df_show = pd.DataFrame(rows)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Total filtrado
    total_filt = sum(float(g.get("valor", 0)) for g in gastos_filtrados)
    st.caption(f"📊 Filtrado: **{len(gastos_filtrados)}** lançamentos · **{formatar_brl(total_filt)}**")

    # ─── Excluir lançamento (com confirmação) ─────────────────────────
    st.markdown("---")
    with st.expander("🗑️ Excluir um lançamento"):
        st.caption(
            "Use com cuidado. Excluir um lançamento NÃO apaga o cadastro do "
            "fornecedor, apenas o lançamento de gasto."
        )

        ids_validos = [g["id"] for g in gastos]
        id_excluir = st.number_input(
            "ID do lançamento (vê na coluna 'ID' da tabela acima)",
            min_value=0,
            step=1,
            key="fin_excluir_id",
        )

        if id_excluir and id_excluir in ids_validos:
            gasto_alvo = next(g for g in gastos if g["id"] == id_excluir)
            st.warning(
                f"**Vai excluir:**\n"
                f"- Fornecedor: {gasto_alvo.get('nome_fornecedor')}\n"
                f"- Valor: {formatar_brl(gasto_alvo.get('valor', 0))}\n"
                f"- NF: {gasto_alvo.get('numero_nf') or '—'}\n"
                f"- Data: {gasto_alvo.get('data_emissao') or '—'}"
            )
            if st.button("⚠️ Confirmar exclusão", type="primary", key="btn_conf_excluir_fin"):
                try:
                    repo_financeiro.excluir_gasto(id_excluir)
                    st.session_state["fin_gastos_msg"] = {
                        "tipo": "sucesso",
                        "texto": f"✅ Lançamento ID {id_excluir} excluído.",
                    }
                    st.rerun()
                except Exception as e:
                    st.session_state["fin_gastos_msg"] = {
                        "tipo": "erro",
                        "texto": f"❌ Erro ao excluir: {e}",
                    }
                    st.rerun()
        elif id_excluir:
            st.error(f"ID {id_excluir} não existe nessa lista.")
