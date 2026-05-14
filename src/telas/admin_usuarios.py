"""Tela de administração — LLE Índices.
Usuários · Relatórios (com senha) · Auditoria
"""
from __future__ import annotations
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE
from src.banco import repo_usuario
from src.banco.repo_auditoria import registrar as _audit

PERFIS = {
    "ADMIN": "Administrador",
    "GESTOR_COBRANCA": "Gestor de Cobrança",
    "GESTOR_CREDITO": "Gestor de Crédito",
    "DIRETORIA": "Diretoria",
}


def renderizar_usuarios(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>⚙ Administração</h1>",
        unsafe_allow_html=True,
    )

    # Abas visíveis dependem do perfil
    eh_admin = usuario.perfil == "ADMIN"
    pode_excluir_cob = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA")
    pode_excluir_cred = usuario.perfil in ("ADMIN", "GESTOR_CREDITO")

    if eh_admin:
        tab_usuarios, tab_relatorios, tab_auditoria = st.tabs([
            "👥 Usuários", "🗑 Relatórios", "📋 Auditoria"
        ])
        with tab_usuarios:
            _tela_usuarios(usuario)
        with tab_relatorios:
            _tela_relatorios(usuario)
        with tab_auditoria:
            _tela_auditoria(usuario)
    elif pode_excluir_cob or pode_excluir_cred:
        tab_relatorios, tab_auditoria = st.tabs(["🗑 Relatórios", "📋 Auditoria"])
        with tab_relatorios:
            _tela_relatorios(usuario)
        with tab_auditoria:
            _tela_auditoria(usuario)
    else:
        st.info("Você não tem permissão para acessar esta área.")


# ============================================================
# USUÁRIOS (só Admin)
# ============================================================

def _tela_usuarios(usuario):
    usuarios = repo_usuario.listar_todos()
    pendentes = [u for u in usuarios if not u.aprovado and u.ativo]
    ativos = [u for u in usuarios if u.aprovado and u.ativo]
    inativos = [u for u in usuarios if not u.ativo]

    # Aprovações pendentes
    if pendentes:
        st.markdown(
            f"<div style='background:#FFF3CD; border-left:4px solid {AMARELO}; "
            f"padding:12px; border-radius:6px; margin-bottom:16px;'>"
            f"<b>⏳ {len(pendentes)} usuário(s) aguardando aprovação</b></div>",
            unsafe_allow_html=True,
        )
        for u in pendentes:
            col_info, col_perfil_sel, col_ap, col_rep = st.columns([3, 2, 1, 1])
            with col_info:
                st.markdown(f"**{u.nome}**")
                st.caption(u.email)
            with col_perfil_sel:
                perfil_novo = st.selectbox(
                    "Perfil",
                    list(PERFIS.keys()),
                    index=list(PERFIS.keys()).index(u.perfil) if u.perfil in PERFIS else 0,
                    format_func=lambda x: PERFIS[x],
                    key=f"perfil_pend_{u.id}",
                    label_visibility="collapsed",
                )
            with col_ap:
                if st.button("✅ Aprovar", key=f"ap_{u.id}", type="primary", use_container_width=True):
                    if perfil_novo != u.perfil:
                        repo_usuario.alterar_perfil(u.id, perfil_novo)
                    repo_usuario.aprovar(u.id)
                    _audit(usuario.id, usuario.nome, "APROVAR_USUARIO",
                           detalhe=f"{u.nome} · {PERFIS.get(perfil_novo, perfil_novo)}")
                    st.rerun()
            with col_rep:
                if st.button("❌ Recusar", key=f"rep_{u.id}", use_container_width=True):
                    repo_usuario.reprovar(u.id)
                    _audit(usuario.id, usuario.nome, "RECUSAR_USUARIO", detalhe=u.nome)
                    st.rerun()
            st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

    # Usuários ativos
    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Usuários Ativos ({len(ativos)})</h3>", unsafe_allow_html=True)

    for u in ativos:
        col_info, col_perfil, col_acoes = st.columns([3, 2, 2])
        with col_info:
            st.markdown(f"**{u.nome}**")
            st.caption(u.email)
        with col_perfil:
            if u.id != usuario.id:
                perfil_atual_idx = list(PERFIS.keys()).index(u.perfil) if u.perfil in PERFIS else 0
                novo_perfil = st.selectbox(
                    "Cargo",
                    list(PERFIS.keys()),
                    index=perfil_atual_idx,
                    format_func=lambda x: PERFIS[x],
                    key=f"perfil_ativo_{u.id}",
                    label_visibility="collapsed",
                )
                if novo_perfil != u.perfil:
                    if st.button("💾 Salvar cargo", key=f"salvar_perfil_{u.id}", use_container_width=True):
                        repo_usuario.alterar_perfil(u.id, novo_perfil)
                        _audit(usuario.id, usuario.nome, "ALTERAR_CARGO",
                               detalhe=f"{u.nome}: {PERFIS.get(u.perfil)} → {PERFIS.get(novo_perfil)}")
                        st.success(f"✓ Cargo de {u.nome} atualizado.")
                        st.rerun()
            else:
                st.caption(f"Você · {PERFIS.get(u.perfil, u.perfil)}")
        with col_acoes:
            if u.id != usuario.id:
                col_rs, col_in = st.columns(2)
                with col_rs:
                    if st.button("🔑 Reset Senha", key=f"rs_{u.id}", use_container_width=True):
                        nova = f"LLE@{u.nome.split()[0].lower()}123"
                        repo_usuario.alterar_senha(u.id, nova, deve_trocar=True)
                        _audit(usuario.id, usuario.nome, "RESET_SENHA", detalhe=u.nome)
                        st.success(f"Senha temporária: `{nova}`")
                with col_in:
                    if st.button("🚫 Inativar", key=f"in_{u.id}", use_container_width=True):
                        repo_usuario.reprovar(u.id)
                        _audit(usuario.id, usuario.nome, "INATIVAR_USUARIO", detalhe=u.nome)
                        st.rerun()
        st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

    # Inativos
    if inativos:
        with st.expander(f"Usuários inativos ({len(inativos)})"):
            for u in inativos:
                col_i, col_reativar = st.columns([4, 1])
                with col_i:
                    st.caption(f"{u.nome} · {u.email}")
                with col_reativar:
                    if st.button("Reativar", key=f"reat_{u.id}", use_container_width=True):
                        repo_usuario.aprovar(u.id)
                        _audit(usuario.id, usuario.nome, "REATIVAR_USUARIO", detalhe=u.nome)
                        st.rerun()


# ============================================================
# RELATÓRIOS — exclusão com confirmação de senha
# ============================================================

def _tela_relatorios(usuario):
    from src.banco import repo_dados
    from src.utils.formatadores import nome_mes

    pode_cob = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA")
    pode_cred = usuario.perfil in ("ADMIN", "GESTOR_CREDITO")

    st.markdown(
        f"<div style='background:#FFF0F0; border-left:4px solid #DC3545; "
        f"padding:12px; border-radius:6px; margin-bottom:16px;'>"
        f"<b>⚠ Atenção:</b> Excluir um relatório remove todos os dados daquele mês. "
        f"A exclusão exige confirmação com sua senha.</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    if pode_cob:
        with col1:
            st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>📊 Cobrança</h4>", unsafe_allow_html=True)
            meses = repo_dados.listar_meses_disponiveis("COBRANCA")
            if not meses:
                st.caption("Nenhum upload encontrado.")
            else:
                for m in meses:
                    _item_relatorio(m, "COBRANCA", usuario)

    if pode_cred:
        with col2:
            st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>💳 Crédito</h4>", unsafe_allow_html=True)
            meses = repo_dados.listar_meses_disponiveis("CREDITO")
            if not meses:
                st.caption("Nenhum upload encontrado.")
            else:
                for m in meses:
                    _item_relatorio(m, "CREDITO", usuario)


def _item_relatorio(m: dict, area: str, usuario):
    from src.utils.formatadores import nome_mes

    chave_del = f"del_{area}_{m['mes_ano']}"
    label_mes = nome_mes(m["mes_ano"])

    col_mes, col_arq, col_btn = st.columns([1.5, 3, 1])
    with col_mes:
        st.markdown(f"**{label_mes}**")
    with col_arq:
        st.caption(m.get("nome_arquivo", "-"))
    with col_btn:
        if st.button("🗑 Excluir", key=f"btn_{chave_del}", use_container_width=True):
            st.session_state[chave_del] = True
            st.rerun()

    # Modal de confirmação com senha
    if st.session_state.get(chave_del):
        st.markdown(
            f"<div style='background:#FFF0F0; border:1px solid #DC3545; "
            f"padding:14px; border-radius:8px; margin:8px 0;'>"
            f"<b>Confirmar exclusão de {label_mes} ({area})?</b><br>"
            f"<small>Digite sua senha para confirmar.</small></div>",
            unsafe_allow_html=True,
        )
        with st.form(key=f"form_{chave_del}"):
            senha = st.text_input("Sua senha", type="password", key=f"senha_{chave_del}")
            col_ok, col_cancel = st.columns(2)
            with col_ok:
                confirmar = st.form_submit_button("Sim, excluir", type="primary", use_container_width=True)
            with col_cancel:
                cancelar = st.form_submit_button("Cancelar", use_container_width=True)

            if confirmar:
                u_valid = repo_usuario.autenticar(usuario.email, senha)
                if u_valid is None:
                    st.error("❌ Senha incorreta.")
                else:
                    _excluir_upload(area, m["mes_ano"])
                    _audit(usuario.id, usuario.nome, "EXCLUIR_RELATORIO", area,
                           f"Mês: {label_mes} · Arquivo: {m.get('nome_arquivo', '-')}")
                    del st.session_state[chave_del]
                    st.success(f"✓ Dados de {label_mes} excluídos.")
                    st.rerun()
            if cancelar:
                del st.session_state[chave_del]
                st.rerun()

    st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)


def _excluir_upload(area: str, mes_ano: str):
    sb = __import__("src.banco.conexao", fromlist=["obter_conexao"]).obter_conexao()
    r = sb.table("upload_mes").select("id").eq("area", area).eq("mes_ano", mes_ano).execute()
    if r.data:
        upload_id = r.data[0]["id"]
        tabelas = {
            "COBRANCA": ["dados_cobranca_acordo", "dados_cobranca_baixa", "dados_cobranca_performance"],
            "CREDITO": ["dados_credito_liberacao", "dados_credito_limite"],
        }
        for tabela in tabelas.get(area, []):
            sb.table(tabela).delete().eq("upload_id", upload_id).execute()
        sb.table("upload_mes").delete().eq("id", upload_id).execute()


# ============================================================
# AUDITORIA
# ============================================================

def _tela_auditoria(usuario):
    from src.banco import repo_auditoria
    from src.utils.formatadores import nome_mes
    import pandas as pd

    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>📋 Log de Auditoria</h3>", unsafe_allow_html=True)
    st.caption("Registro de todas as ações realizadas no sistema.")

    # Filtros
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filtro_area = st.selectbox(
            "Área", ["Todas", "COBRANCA", "CREDITO"],
            format_func=lambda x: "Todas as áreas" if x == "Todas" else x.title(),
        )
    with col_f2:
        filtro_acao = st.selectbox(
            "Ação", ["Todas"] + repo_auditoria.listar_acoes_disponiveis(),
            format_func=lambda x: "Todas as ações" if x == "Todas" else x.replace("_", " ").title(),
        )
    with col_f3:
        limite = st.selectbox("Exibir", [50, 100, 200], index=0)

    registros = repo_auditoria.listar(
        limite=limite,
        area=None if filtro_area == "Todas" else filtro_area,
    )

    if filtro_acao != "Todas":
        registros = [r for r in registros if r.get("acao") == filtro_acao]

    if not registros:
        st.info("Nenhum registro encontrado.")
        return

    st.markdown(f"**{len(registros)} registro(s)**")
    st.markdown("<br>", unsafe_allow_html=True)

    for r in registros:
        ts = r.get("timestamp", "")
        if ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts[:19])
                ts_fmt = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                ts_fmt = ts[:16]
        else:
            ts_fmt = "-"

        acao = r.get("acao", "").replace("_", " ").title()
        area = r.get("area") or ""
        detalhe = r.get("detalhe") or ""
        nome = r.get("usuario_nome", "?")

        cor_acao = {
            "LOGIN": "#0071FE",
            "UPLOAD_COBRANCA": "#0F8C3B",
            "UPLOAD_CREDITO": "#0F8C3B",
            "EXCLUIR_RELATORIO": "#DC3545",
            "APROVAR_USUARIO": "#0F8C3B",
            "RECUSAR_USUARIO": "#DC3545",
            "INATIVAR_USUARIO": "#DC3545",
            "ALTERAR_CARGO": "#FAC318",
            "RESET_SENHA": "#FAC318",
        }.get(r.get("acao", ""), "#6C757D")

        st.markdown(
            f"<div style='display:flex; align-items:center; gap:12px; "
            f"padding:8px 12px; border-left:4px solid {cor_acao}; "
            f"background:#F8F9FA; border-radius:0 6px 6px 0; margin-bottom:6px;'>"
            f"<div style='font-size:11px; color:#999; min-width:110px;'>{ts_fmt}</div>"
            f"<div style='font-size:12px; font-weight:700; color:{cor_acao}; min-width:160px;'>{acao}</div>"
            f"<div style='font-size:12px; font-weight:600; color:{AZUL_ESCURO}; min-width:140px;'>{nome}</div>"
            f"<div style='font-size:12px; color:#555;'>{area}{' · ' if area and detalhe else ''}{detalhe}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
