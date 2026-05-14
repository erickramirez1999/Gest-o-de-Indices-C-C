"""Tela Meu Perfil — LLE Índices."""
from __future__ import annotations
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO
from src.banco import repo_usuario

PERFIS = {
    "ADMIN": "Administrador",
    "GESTOR_COBRANCA": "Gestor de Cobrança",
    "GESTOR_CREDITO": "Gestor de Crédito",
    "DIRETORIA": "Diretoria",
}


def renderizar_meu_perfil(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>👤 Meu Perfil</h1>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div style='background:#F8F9FA; padding:20px; border-radius:8px; "
        f"border-left:5px solid {AZUL_ESCURO}; margin-bottom:24px;'>"
        f"<div style='font-size:18px; font-weight:700; color:{AZUL_ESCURO};'>{usuario.nome}</div>"
        f"<div style='color:#666; margin-top:4px;'>{usuario.email}</div>"
        f"<div style='margin-top:8px;'>"
        f"<span style='background:{AZUL_ESCURO}; color:white; padding:3px 10px; "
        f"border-radius:10px; font-size:12px;'>{PERFIS.get(usuario.perfil, usuario.perfil)}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>🔑 Alterar Senha</h3>", unsafe_allow_html=True)

    with st.form("form_senha"):
        atual = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha (mín. 8 caracteres)", type="password")
        confirma = st.text_input("Confirmar nova senha", type="password")
        salvar = st.form_submit_button("✓ Salvar senha", type="primary", use_container_width=True)

        if salvar:
            if not atual or not nova or not confirma:
                st.error("❌ Preencha todos os campos.")
                return
            if nova != confirma:
                st.error("❌ As senhas não conferem.")
                return
            u_valid = repo_usuario.autenticar(usuario.email, atual)
            if u_valid is None:
                st.error("❌ Senha atual incorreta.")
                return
            try:
                repo_usuario.alterar_senha(usuario.id, nova)
                st.success("✓ Senha alterada com sucesso!")
            except ValueError as e:
                st.error(f"❌ {e}")
