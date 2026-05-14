"""Controle de permissões por perfil — LLE Índices."""

PERMISSOES = {
    "ADMIN": "*",  # acesso total
    "GESTOR_COBRANCA": [
        "inicio", "meu_perfil", "upload",
        "cob_acordo", "cob_cobranca", "cob_performance", "cob_geral",
        "admin_usuarios",  # só vê aba Relatórios (Cobrança) + Auditoria
    ],
    "GESTOR_CREDITO": [
        "inicio", "meu_perfil", "upload",
        "cred_indicadores", "cred_reanalises", "cred_geral",
        "admin_usuarios",  # só vê aba Relatórios (Crédito) + Auditoria
    ],
    "DIRETORIA": [
        "inicio", "meu_perfil",
        "cob_acordo", "cob_cobranca", "cob_performance", "cob_geral",
        "cred_indicadores", "cred_reanalises", "cred_geral",
    ],
}


def pode_acessar(perfil: str, pagina: str) -> bool:
    perms = PERMISSOES.get(perfil, [])
    if perms == "*":
        return True
    return pagina in perms
