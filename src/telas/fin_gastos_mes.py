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

    # ─── AÇÕES SOBRE OS LANÇAMENTOS ─────────────────────────
    st.markdown("---")
    st.markdown(f"### 🛠️ Ações sobre os lançamentos de {nome_mes(mes_ano)}/{mes_ano[:4]}")

    aba_mover, aba_excluir1, aba_excluir_tudo = st.tabs([
        "📅 Mover lançamento de mês",
        "🗑️ Excluir um lançamento",
        "⚠️ Excluir TODOS do mês",
    ])

    # ───── Tab 1: Mover de mês ─────
    with aba_mover:
        st.caption(
            "Lançou no mês errado? Selecione o lançamento e mude pro mês correto. "
            "Os dados (fornecedor, valor, NF) ficam preservados — só muda a competência."
        )

        opcoes_mover = {
            f"ID {g['id']} · {g.get('nome_fornecedor', '?')} · "
            f"{formatar_brl(g.get('valor', 0))} · NF {g.get('numero_nf') or '—'} "
            f"· {g.get('data_emissao') or '—'}": g
            for g in gastos
        }

        sel = st.selectbox(
            "Selecione o lançamento",
            list(opcoes_mover.keys()),
            key="fin_mover_sel",
        )
        gasto_mover = opcoes_mover[sel]

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            novo_mes = st.selectbox(
                "Mover para o MÊS",
                list(range(1, 13)),
                index=int(mes_ano[5:7]) - 1,
                format_func=lambda m: nome_mes(f"2026-{m:02d}"),
                key="fin_mover_mes",
            )
        with col_m2:
            from datetime import date as _date
            ano_atual = _date.today().year
            novo_ano = st.selectbox(
                "Para o ANO",
                list(range(ano_atual - 3, ano_atual + 2)),
                index=3,  # ano atual
                key="fin_mover_ano",
            )

        novo_mes_ano = f"{novo_ano:04d}-{novo_mes:02d}"
        mes_atual_lanc = gasto_mover.get("mes_ano")

        if novo_mes_ano == mes_atual_lanc:
            st.info(f"ℹ️ O lançamento já está em {nome_mes(novo_mes_ano)}/{novo_ano}. Escolha outro mês.")
        else:
            st.warning(
                f"**Vai mover:**\n"
                f"- Fornecedor: {gasto_mover.get('nome_fornecedor')}\n"
                f"- Valor: {formatar_brl(gasto_mover.get('valor', 0))}\n"
                f"- NF: {gasto_mover.get('numero_nf') or '—'}\n"
                f"- De: **{nome_mes(mes_atual_lanc)}/{mes_atual_lanc[:4]}**\n"
                f"- Para: **{nome_mes(novo_mes_ano)}/{novo_ano}**"
            )
            if st.button("📅 Confirmar movimentação", type="primary", key="btn_mover_lanc"):
                try:
                    repo_financeiro.atualizar_gasto(
                        gasto_mover["id"],
                        {"mes_ano": novo_mes_ano},
                    )
                    st.session_state["fin_gastos_msg"] = {
                        "tipo": "sucesso",
                        "texto": (
                            f"✅ Lançamento ID {gasto_mover['id']} movido pra "
                            f"**{nome_mes(novo_mes_ano)}/{novo_ano}**."
                        ),
                    }
                    st.rerun()
                except Exception as e:
                    st.session_state["fin_gastos_msg"] = {
                        "tipo": "erro",
                        "texto": f"❌ Erro ao mover: {e}",
                    }
                    st.rerun()

    # ───── Tab 2: Excluir um lançamento ─────
    with aba_excluir1:
        st.caption(
            "Excluir lançamento individual. NÃO apaga o cadastro do fornecedor."
        )

        opcoes_excl = {
            f"ID {g['id']} · {g.get('nome_fornecedor', '?')} · "
            f"{formatar_brl(g.get('valor', 0))} · NF {g.get('numero_nf') or '—'} "
            f"· {g.get('data_emissao') or '—'}": g
            for g in gastos
        }

        sel_excl = st.selectbox(
            "Selecione o lançamento",
            list(opcoes_excl.keys()),
            key="fin_excluir_sel",
        )
        gasto_excl = opcoes_excl[sel_excl]

        st.warning(
            f"**Vai excluir:**\n"
            f"- Fornecedor: {gasto_excl.get('nome_fornecedor')}\n"
            f"- Valor: {formatar_brl(gasto_excl.get('valor', 0))}\n"
            f"- NF: {gasto_excl.get('numero_nf') or '—'}\n"
            f"- Data: {gasto_excl.get('data_emissao') or '—'}\n"
            f"- Competência: {nome_mes(gasto_excl.get('mes_ano', ''))}/{gasto_excl.get('mes_ano', '')[:4]}"
        )

        if st.button("🗑️ Confirmar exclusão", type="primary", key="btn_conf_excluir_fin"):
            try:
                repo_financeiro.excluir_gasto(gasto_excl["id"])
                st.session_state["fin_gastos_msg"] = {
                    "tipo": "sucesso",
                    "texto": f"✅ Lançamento ID {gasto_excl['id']} excluído.",
                }
                st.rerun()
            except Exception as e:
                st.session_state["fin_gastos_msg"] = {
                    "tipo": "erro",
                    "texto": f"❌ Erro ao excluir: {e}",
                }
                st.rerun()

    # ───── Tab 3: Excluir TODOS do mês ─────
    with aba_excluir_tudo:
        st.caption(
            "**⚠️ Ação destrutiva.** Apaga TODOS os lançamentos do mês selecionado. "
            "Use só se subiu tudo errado e quer começar do zero. Os cadastros de "
            "fornecedores NÃO são apagados."
        )

        st.error(
            f"**Você está prestes a apagar TODOS os {len(gastos)} lançamento(s) "
            f"de {nome_mes(mes_ano)}/{mes_ano[:4]}** "
            f"(total {formatar_brl(total)})."
        )

        confirmacao = st.text_input(
            f"Pra confirmar, digite **APAGAR {nome_mes(mes_ano).upper()}** no campo abaixo:",
            key="fin_apagar_mes_conf",
            placeholder=f"APAGAR {nome_mes(mes_ano).upper()}",
        )

        confirma_ok = confirmacao.strip().upper() == f"APAGAR {nome_mes(mes_ano).upper()}"

        if st.button(
            f"⚠️ Excluir TODOS os {len(gastos)} lançamento(s) de {nome_mes(mes_ano)}",
            type="primary",
            disabled=not confirma_ok,
            key="btn_apagar_mes_inteiro",
        ):
            try:
                qtd_excluidos = 0
                for g in gastos:
                    repo_financeiro.excluir_gasto(g["id"])
                    qtd_excluidos += 1
                st.session_state["fin_gastos_msg"] = {
                    "tipo": "sucesso",
                    "texto": (
                        f"✅ **{qtd_excluidos}** lançamento(s) excluído(s) de "
                        f"**{nome_mes(mes_ano)}/{mes_ano[:4]}**."
                    ),
                }
                st.rerun()
            except Exception as e:
                st.session_state["fin_gastos_msg"] = {
                    "tipo": "erro",
                    "texto": f"❌ Erro ao excluir lançamentos do mês: {e}",
                }
                st.rerun()
