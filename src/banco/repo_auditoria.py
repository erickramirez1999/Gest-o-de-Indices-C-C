"""Repositório de auditoria — LLE Índices."""
from __future__ import annotations
from typing import Optional
from src.banco.conexao import obter_conexao


def registrar(
    usuario_id: int,
    usuario_nome: str,
    acao: str,
    area: Optional[str] = None,
    detalhe: Optional[str] = None,
) -> None:
    """Registra uma ação no log de auditoria."""
    try:
        obter_conexao().table("auditoria").insert({
            "usuario_id": usuario_id,
            "usuario_nome": usuario_nome,
            "acao": acao,
            "area": area,
            "detalhe": detalhe,
        }).execute()
    except Exception:
        pass  # Auditoria nunca trava o fluxo principal


def listar(
    limite: int = 200,
    area: Optional[str] = None,
    usuario_id: Optional[int] = None,
) -> list[dict]:
    sb = obter_conexao()
    q = sb.table("auditoria").select("*").order("timestamp", desc=True).limit(limite)
    if area:
        q = q.eq("area", area)
    if usuario_id:
        q = q.eq("usuario_id", usuario_id)
    r = q.execute()
    return r.data


def listar_acoes_disponiveis() -> list[str]:
    return [
        "LOGIN",
        "UPLOAD_COBRANCA",
        "UPLOAD_CREDITO",
        "EXCLUIR_RELATORIO",
        "APROVAR_USUARIO",
        "RECUSAR_USUARIO",
        "ALTERAR_CARGO",
        "RESET_SENHA",
        "INATIVAR_USUARIO",
        "REATIVAR_USUARIO",
        "ALTERAR_SENHA_PROPRIA",
    ]
