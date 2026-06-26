"""
Tela Crédito — Comparativos Salvos.

Lista os comparativos salvos e permite abrir/visualizar/exportar/excluir.
Quando o usuário clica em "Abrir", o comparativo é renderizado completo
(igual à tela de criação, mas sem precisar subir arquivos de novo).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.banco import repo_comparativos
from src.utils.marca import AZUL_ESCURO


def renderizar_cred_comparativos_salvos(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📋 Comparativos Salvos — Crédito</h1>",
        unsafe_allow_html=True,
    )

    # Se tem ID na sessão, abre direto esse
    comp_aberto_id = st.session_state.get("cmp_aberto_id")
    if comp_aberto_id:
        _visualizar_comparativo(comp_aberto_id, usuario)
        return

    # Caso contrário, lista todos
    st.caption("Lista de todos os comparativos salvos. Clique em **Abrir** pra visualizar.")

    try:
        comparativos = repo_comparativos.listar_comparativos()
    except Exception as e:
        st.error(f"❌ Erro ao carregar lista: {type(e).__name__}: {e}")
        return

    if not comparativos:
        st.info(
            "📭 Nenhum comparativo salvo ainda. "
            "Vá em **📊 Comparativo Semanal** pra criar e salvar o primeiro."
        )
        return

    st.markdown(f"##### 📊 {len(comparativos)} comparativo(s) salvos")

    for comp in comparativos:
        with st.container():
            criado_em = comp.get("criado_em", "")
            if criado_em:
                try:
                    criado_em = datetime.fromisoformat(criado_em.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass

            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f"""
                    <div style='background:white; padding:12px; border-radius:8px;
                    border-left:4px solid {AZUL_ESCURO}; margin-bottom:8px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.08);'>
                        <div style='font-size:16px; color:{AZUL_ESCURO}; font-weight:600;'>
                            {comp['titulo']}
                        </div>
                        <div style='font-size:13px; color:#555; margin-top:4px;'>
                            📅 <b>{comp['rotulo_a']}</b> vs <b>{comp['rotulo_b']}</b>
                        </div>
                        <div style='font-size:12px; color:#888; margin-top:4px;'>
                            🕐 Salvo em {criado_em} · 👤 {comp.get('criado_por_nome') or '—'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                if st.button("👁️ Abrir", key=f"abrir_{comp['id']}", use_container_width=True):
                    st.session_state["cmp_aberto_id"] = comp["id"]
                    st.rerun()
                if st.button("🗑️ Excluir", key=f"excluir_{comp['id']}", use_container_width=True):
                    st.session_state[f"_confirma_excl_{comp['id']}"] = True
                    st.rerun()

            # Confirmação de exclusão
            if st.session_state.get(f"_confirma_excl_{comp['id']}"):
                st.warning(f"⚠️ Tem certeza que quer excluir **{comp['titulo']}**?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✓ Confirmar exclusão", key=f"sim_excl_{comp['id']}", type="primary"):
                        with st.spinner("Excluindo..."):
                            try:
                                repo_comparativos.excluir_comparativo(comp["id"])
                                st.session_state.pop(f"_confirma_excl_{comp['id']}", None)
                                st.toast("Excluído!", icon="🗑️")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erro ao excluir: {e}")
                with c2:
                    if st.button("Cancelar", key=f"nao_excl_{comp['id']}"):
                        st.session_state.pop(f"_confirma_excl_{comp['id']}", None)
                        st.rerun()


def _visualizar_comparativo(comp_id: int, usuario):
    """Carrega e renderiza um comparativo salvo, reaproveitando os blocos da tela de criação."""
    try:
        comp = repo_comparativos.carregar_comparativo(comp_id)
    except Exception as e:
        st.error(f"❌ Erro ao carregar comparativo: {e}")
        if st.button("← Voltar"):
            st.session_state.pop("cmp_aberto_id", None)
            st.rerun()
        return

    if not comp:
        st.warning("⚠️ Comparativo não encontrado.")
        if st.button("← Voltar"):
            st.session_state.pop("cmp_aberto_id", None)
            st.rerun()
        return

    # Cabeçalho + voltar
    col_titulo, col_voltar = st.columns([5, 1])
    with col_titulo:
        st.markdown(
            f"<h1 style='color:{AZUL_ESCURO}'>📊 {comp['titulo']}</h1>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"📅 **{comp['rotulo_a']}** vs **{comp['rotulo_b']}** · "
            f"Salvo por {comp.get('criado_por_nome') or '—'}"
        )
    with col_voltar:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Voltar à lista", use_container_width=True):
            st.session_state.pop("cmp_aberto_id", None)
            st.rerun()

    # Mostra arquivos originais
    if comp.get("arquivos_a") or comp.get("arquivos_b"):
        with st.expander("📋 Arquivos originais (snapshot do dia do salvamento)", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**{comp['rotulo_a']}**")
                st.code(comp.get("arquivos_a") or "—", language=None)
            with col_b:
                st.markdown(f"**{comp['rotulo_b']}**")
                st.code(comp.get("arquivos_b") or "—", language=None)

    st.markdown("---")

    # Reaproveita os blocos da tela de criação
    from src.telas.cred_comparativo import (
        _renderizar_kpis_liberacoes,
        _renderizar_graficos_liberacoes,
        _renderizar_aumento_limite,
        _renderizar_tempo_tela,
        _exportar_comparativo_excel,
    )

    rot_a = comp["rotulo_a"]
    rot_b = comp["rotulo_b"]
    dados_a = comp["dados_a"]
    dados_b = comp["dados_b"]

    _renderizar_kpis_liberacoes(dados_a, dados_b, rot_a, rot_b)
    _renderizar_graficos_liberacoes(dados_a, dados_b, rot_a, rot_b)
    _renderizar_aumento_limite(dados_a, dados_b, rot_a, rot_b)
    _renderizar_tempo_tela(dados_a, dados_b, rot_a, rot_b)

    # Exportar Excel + PPT (igual à tela de criação)
    st.markdown("---")
    st.markdown("### 📥 Exportar")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        excel_bytes = _exportar_comparativo_excel(dados_a, dados_b, rot_a, rot_b)
        st.download_button(
            "💾 Baixar Excel",
            data=excel_bytes,
            file_name=f"comparativo_credito_{rot_a.replace(' ', '_')}_vs_{rot_b.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_exp2:
        if st.button("📊 Gerar Apresentação PPT", use_container_width=True, type="primary", key="cmp_salvo_ppt"):
            with st.spinner("📊 Montando apresentação..."):
                try:
                    from src.servicos.gerador_ppt import gerar_ppt_comparativo_credito
                    ppt_bytes = gerar_ppt_comparativo_credito(dados_a, dados_b, rot_a, rot_b)
                    st.session_state["cmp_salvo_ppt_bytes"] = ppt_bytes
                    st.session_state["cmp_salvo_ppt_nome"] = (
                        f"comparativo_credito_{rot_a.replace(' ', '_')}_vs_{rot_b.replace(' ', '_')}.pptx"
                    )
                    st.toast("✅ PPT gerado!", icon="🎯")
                except Exception as e:
                    st.error(f"❌ Erro: {type(e).__name__}: {e}")

        if st.session_state.get("cmp_salvo_ppt_bytes"):
            st.download_button(
                "⬇️ Baixar PPT",
                data=st.session_state["cmp_salvo_ppt_bytes"],
                file_name=st.session_state.get("cmp_salvo_ppt_nome", "comparativo.pptx"),
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
