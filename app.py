"""
LLE Índices — App principal Streamlit.
Gestão de Índices Financeiros: Cobrança e Crédito.

Perfis:
  ADMIN            → acesso total
  GESTOR_COBRANCA  → só seção Cobrança + upload
  GESTOR_CREDITO   → só seção Crédito + upload
  DIRETORIA        → visualização de tudo, sem upload
"""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.estilo import aplicar_css_lle
from src.utils.marca import AZUL_ESCURO, AMARELO

st.set_page_config(
    page_title="LLE Índices",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

aplicar_css_lle()

# ============================================================
# NAVEGAÇÃO (session_state)
# ============================================================
PAGINAS_COBRANCA = {
    "cob_acordo": "📋 Indices de Acordo",
    "cob_cobranca": "💰 Indices de Cobranca",
    "cob_performance": "⚡ Performance",
    "cob_geral": "📊 Geral",
}

PAGINAS_CREDITO = {
    "cred_indicadores": "💳 Indicadores de Analise",
    "cred_reanalises": "🔄 Reanalises de Limite",
    "cred_geral": "📊 Geral",
}


def pagina_atual():
    return st.session_state.get("pagina", "inicio")


def ir_para(pagina: str):
    st.session_state["pagina"] = pagina


def usuario_logado():
    return st.session_state.get("usuario_atual")


def logar(usuario):
    st.session_state["usuario_atual"] = usuario
    st.session_state["pagina"] = "inicio"


def deslogar():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


# ============================================================
# CSS LOGIN / SIDEBAR
# ============================================================

def _esconder_sidebar():
    st.markdown("""
    <style>
        section[data-testid="stSidebar"] { display: none !important; }
        button[data-testid="collapsedControl"] { display: none !important; }
        .block-container { padding-top: 3rem !important; max-width: 600px !important; }
    </style>
    """, unsafe_allow_html=True)


def _sidebar_fixa():
    st.markdown("""
    <style>
        section[data-testid="stSidebar"] {
            display: block !important;
            min-width: 260px !important; max-width: 260px !important;
            transform: translateX(0px) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        button[data-testid="collapsedControl"],
        button[data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }
        [data-testid="stSidebarNav"] { display: none !important; }
        header[data-testid="stHeader"] { display: none !important; }
        .main .block-container { padding-left: 2rem !important; padding-right: 2rem !important; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# TELA DE LOGIN
# ============================================================

def tela_login():
    LOGO = Path(__file__).parent / "assets" / "logo_lle.png"

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        if LOGO.exists():
            st.image(str(LOGO), use_container_width=True)

        st.markdown(
            f"""<div style="text-align:center; margin-top:-10px; margin-bottom:24px;">
            <h2 style="color:{AZUL_ESCURO}; margin-bottom:4px;">LLE Índices</h2>
            <p style="color:#666;">Gestão de Índices Financeiros · Grupo LLE</p>
            </div>""",
            unsafe_allow_html=True,
        )

        if st.session_state.get("chave_recem_gerada"):
            _tela_chave_gerada()
            return

        tab_login, tab_cad = st.tabs(["🔑 Entrar", "📝 Cadastrar"])

        with tab_login:
            _form_login()

        with tab_cad:
            _form_cadastro()


def _form_login():
    from src.banco import repo_usuario
    with st.form("login"):
        email = st.text_input("E-mail", placeholder="seu@email.com")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if entrar:
            u = repo_usuario.autenticar(email.strip(), senha)
            if u is None:
                st.error("❌ E-mail ou senha inválidos.")
                return
            if not u.ativo:
                st.error("❌ Usuário inativado.")
                return
            if not u.aprovado:
                st.warning("⏳ Seu acesso ainda está pendente de aprovação pelo administrador.")
                return
            if u.deve_trocar_senha:
                st.session_state["usuario_trocando_senha"] = u
                st.rerun()
                return
            logar(u)
            from src.banco.repo_auditoria import registrar as _audit
            _audit(u.id, u.nome, "LOGIN")
            st.rerun()


def _form_cadastro():
    from src.banco import repo_usuario

    PERFIS_CAD = {
        "GESTOR_COBRANCA": "Gestor de Cobrança",
        "GESTOR_CREDITO": "Gestor de Crédito",
        "DIRETORIA": "Diretoria",
    }

    st.caption("Após o cadastro, aguarde aprovação do administrador.")

    with st.form("cadastro"):
        nome = st.text_input("Nome completo *")
        email = st.text_input("E-mail *")
        perfil = st.selectbox("Perfil *", list(PERFIS_CAD.keys()),
                               format_func=lambda x: PERFIS_CAD[x])
        senha = st.text_input("Senha (mín. 8 caracteres) *", type="password")
        senha_conf = st.text_input("Confirmar senha *", type="password")
        sub = st.form_submit_button("Criar conta", type="primary", use_container_width=True)

        if sub:
            if not nome or not email or not senha:
                st.error("❌ Preencha todos os campos.")
                return
            if "@" in nome:
                st.error("❌ Use o campo 'Nome completo' para seu nome, não e-mail.")
                return
            if senha != senha_conf:
                st.error("❌ As senhas não conferem.")
                return
            try:
                novo = repo_usuario.criar_usuario(nome.strip(), email.strip(), senha, perfil)
                st.session_state["chave_recem_gerada"] = novo.chave_aprovacao
                st.session_state["nome_recem_cadastrado"] = novo.nome
                st.session_state["aprovado_auto"] = novo.aprovado
                st.rerun()
            except ValueError as e:
                st.error(f"❌ {e}")


def _tela_chave_gerada():
    chave = st.session_state.get("chave_recem_gerada")
    nome = st.session_state.get("nome_recem_cadastrado", "")
    aprovado_auto = st.session_state.get("aprovado_auto", False)

    st.success(f"✅ Cadastro realizado, {nome.split()[0] if nome else ''}!")

    if aprovado_auto:
        st.info("🎉 Você é o primeiro usuário — virou Administrador automaticamente. Faça login abaixo.")
    else:
        st.markdown(
            f"""<div style="background:#FFF3CD; border-left:4px solid {AMARELO};
            padding:16px; border-radius:6px; margin:16px 0;">
            <b>⏳ Acesso pendente de aprovação.</b><br>
            Avise o administrador que se cadastrou.<br>
            Sua chave de identificação: <code>{chave}</code>
            </div>""",
            unsafe_allow_html=True,
        )

    if st.button("← Voltar ao login", type="primary", use_container_width=True):
        for k in ["chave_recem_gerada", "nome_recem_cadastrado", "aprovado_auto"]:
            st.session_state.pop(k, None)
        st.rerun()


# ============================================================
# TROCA DE SENHA FORÇADA
# ============================================================

def tela_troca_senha_forcada():
    from src.banco import repo_usuario
    u = st.session_state.get("usuario_trocando_senha")
    if not u:
        return

    st.markdown(
        f"""<div style="background:#FFF3CD; border-left:4px solid {AMARELO};
        padding:16px; border-radius:6px; margin:24px auto; max-width:500px;">
        <b>🔐 Defina sua nova senha</b><br>
        O administrador redefiniu seu acesso. Crie sua senha pessoal para continuar.
        </div>""",
        unsafe_allow_html=True,
    )

    with st.form("trocar_senha"):
        nova = st.text_input("Nova senha (mín. 8 caracteres)", type="password")
        confirma = st.text_input("Confirmar senha", type="password")
        salvar = st.form_submit_button("✓ Salvar e entrar", type="primary", use_container_width=True)
        if salvar:
            if nova != confirma:
                st.error("❌ As senhas não conferem.")
                return
            try:
                repo_usuario.alterar_senha(u.id, nova, deve_trocar=False)
                u_atualizado = repo_usuario.buscar_por_id(u.id)
                del st.session_state["usuario_trocando_senha"]
                logar(u_atualizado)
                st.rerun()
            except ValueError as e:
                st.error(f"❌ {e}")


# ============================================================
# SIDEBAR LOGADO
# ============================================================

def sidebar_logado(usuario):
    from src.utils.traducoes import PERFIS_LABEL
    LOGO_BRANCO = Path(__file__).parent / "assets" / "logo_lle_branco.png"
    LOGO = Path(__file__).parent / "assets" / "logo_lle.png"
    logo = LOGO_BRANCO if LOGO_BRANCO.exists() else LOGO

    with st.sidebar:
        if logo.exists():
            st.image(str(logo), use_container_width=True)

        st.markdown("---")
        st.markdown(f"👤 **{usuario.nome}**")
        st.caption(f"Perfil: {PERFIS_LABEL.get(usuario.perfil, usuario.perfil)}")

        if st.button("🏠 Inicio", use_container_width=True, key="nav_inicio"):
            ir_para("inicio")
            st.rerun()

        if st.button("Meu Perfil", use_container_width=True, key="nav_perfil"):
            ir_para("meu_perfil")
            st.rerun()

        st.markdown("---")

        pode_cobranca = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA", "DIRETORIA")
        pode_credito = usuario.perfil in ("ADMIN", "GESTOR_CREDITO", "DIRETORIA")
        pode_upload = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA", "GESTOR_CREDITO")
        eh_admin = usuario.perfil == "ADMIN"

        if pode_cobranca:
            st.markdown("**📊 Cobrança**")
            for chave, label in PAGINAS_COBRANCA.items():
                if st.button(label, key=f"nav_{chave}", use_container_width=True):
                    ir_para(chave)
                    st.rerun()
            st.markdown("")

        if pode_credito:
            st.markdown("**💳 Crédito**")
            for chave, label in PAGINAS_CREDITO.items():
                if st.button(label, key=f"nav_{chave}", use_container_width=True):
                    ir_para(chave)
                    st.rerun()
            st.markdown("")

        if pode_upload:
            st.markdown("---")
            if st.button("📤 Upload Mensal", use_container_width=True, key="nav_upload"):
                ir_para("upload")
                st.rerun()

        if eh_admin:
            st.markdown("---")
            st.markdown("**⚙ Administração**")
            if st.button("👥 Usuarios", use_container_width=True, key="nav_users"):
                ir_para("admin_usuarios")
                st.rerun()
        elif usuario.perfil in ("GESTOR_COBRANCA", "GESTOR_CREDITO"):
            st.markdown("---")
            if st.button("⚙ Administracao", use_container_width=True, key="nav_admin"):
                ir_para("admin_usuarios")
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            deslogar()
            st.rerun()


# ============================================================
# ROTEAMENTO
# ============================================================

def renderizar_pagina(usuario, pagina: str):
    from src.modelos.tipos import pode_acessar
    if not pode_acessar(usuario.perfil, pagina):
        st.error("❌ Você não tem permissão para acessar esta página.")
        return

    if pagina == "inicio":
        _tela_inicio(usuario)
    elif pagina == "meu_perfil":
        from src.telas.meu_perfil import renderizar_meu_perfil
        renderizar_meu_perfil(usuario)
    elif pagina == "upload":
        from src.telas.upload import renderizar_upload
        renderizar_upload(usuario)
    elif pagina == "cob_acordo":
        from src.telas.cob_acordo import renderizar_indices_acordo
        renderizar_indices_acordo(usuario)
    elif pagina == "cob_cobranca":
        from src.telas.cob_cobranca import renderizar_indices_cobranca
        renderizar_indices_cobranca(usuario)
    elif pagina == "cob_performance":
        from src.telas.cob_performance import renderizar_performance
        renderizar_performance(usuario)
    elif pagina == "cob_geral":
        from src.telas.cob_geral import renderizar_geral_cobranca
        renderizar_geral_cobranca(usuario)
    elif pagina == "cred_indicadores":
        from src.telas.cred_indicadores import renderizar_indicadores_credito
        renderizar_indicadores_credito(usuario)
    elif pagina == "cred_reanalises":
        from src.telas.cred_reanalises import renderizar_reanalises
        renderizar_reanalises(usuario)
    elif pagina == "cred_geral":
        from src.telas.cred_geral import renderizar_geral_credito
        renderizar_geral_credito(usuario)
    elif pagina == "admin_usuarios":
        from src.telas.admin_usuarios import renderizar_usuarios
        renderizar_usuarios(usuario)
    else:
        _tela_inicio(usuario)


def _tela_inicio(usuario):
    from src.utils.marca import AMARELO, VERDE
    LOGO = Path(__file__).parent / "assets" / "logo_lle.png"

    primeiro = usuario.nome.split()[0]
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>Olá, {primeiro}! 👋</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Bem-vindo ao LLE Índices — Gestão de Indicadores Financeiros do Grupo LLE.")

    st.markdown("<br>", unsafe_allow_html=True)

    pode_cobranca = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA", "DIRETORIA")
    pode_credito = usuario.perfil in ("ADMIN", "GESTOR_CREDITO", "DIRETORIA")
    pode_upload = usuario.perfil in ("ADMIN", "GESTOR_COBRANCA", "GESTOR_CREDITO")

    col1, col2 = st.columns(2)

    if pode_cobranca:
        with col1:
            st.markdown(
                f"""<div style="background:{AZUL_ESCURO}; padding:24px; border-radius:10px;
                border-left:5px solid {AMARELO}; margin-bottom:12px; cursor:pointer;">
                <div style="color:{AMARELO}; font-size:13px; font-weight:700; letter-spacing:1px;">
                COBRANÇA</div>
                <div style="color:white; font-size:20px; font-weight:700; margin-top:6px;">
                Índices de Acordo, Cobrança e Performance</div>
                <div style="color:#AAA; font-size:12px; margin-top:8px;">
                Acordos realizados · Baixas · Produtividade por cobrador</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("📊 Acessar Cobrança", use_container_width=True, type="primary"):
                ir_para("cob_acordo")
                st.rerun()

    if pode_credito:
        with col2:
            st.markdown(
                f"""<div style="background:{AZUL_ESCURO}; padding:24px; border-radius:10px;
                border-left:5px solid {VERDE}; margin-bottom:12px;">
                <div style="color:{VERDE}; font-size:13px; font-weight:700; letter-spacing:1px;">
                CRÉDITO</div>
                <div style="color:white; font-size:20px; font-weight:700; margin-top:6px;">
                Indicadores de Análise e Reanálises</div>
                <div style="color:#AAA; font-size:12px; margin-top:8px;">
                Pedidos aprovados · Negados · Direto · Limites</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if st.button("💳 Acessar Crédito", use_container_width=True, type="primary"):
                ir_para("cred_indicadores")
                st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():
    from src.banco import repo_usuario

    try:
        repo_usuario.sincronizar_aprovacoes_com_secrets()
    except Exception:
        pass

    usuario = usuario_logado()

    if usuario is None:
        # Troca de senha forçada
        if st.session_state.get("usuario_trocando_senha"):
            _esconder_sidebar()
            tela_troca_senha_forcada()
        else:
            _esconder_sidebar()
            tela_login()
    else:
        _sidebar_fixa()
        sidebar_logado(usuario)
        renderizar_pagina(usuario, pagina_atual())


main()
