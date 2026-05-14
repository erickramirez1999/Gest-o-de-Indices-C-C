"""Repositório de usuários — LLE Índices."""
from __future__ import annotations
import secrets
import bcrypt
import streamlit as st
from dataclasses import dataclass
from typing import Optional
from src.banco.conexao import obter_conexao


@dataclass
class Usuario:
    id: int
    nome: str
    email: str
    perfil: str
    ativo: bool
    aprovado: bool
    deve_trocar_senha: bool
    chave_aprovacao: Optional[str]


def _hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _verificar(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except Exception:
        return False


def _row(d: dict) -> Usuario:
    return Usuario(
        id=d["id"],
        nome=d["nome"],
        email=d["email"],
        perfil=d["perfil"],
        ativo=d["ativo"],
        aprovado=d["aprovado"],
        deve_trocar_senha=d.get("deve_trocar_senha", False),
        chave_aprovacao=d.get("chave_aprovacao"),
    )


def existe_algum_usuario() -> bool:
    sb = obter_conexao()
    r = sb.table("usuario").select("id", count="exact").limit(1).execute()
    return (r.count or 0) > 0


def criar_usuario(nome: str, email: str, senha: str, perfil: str) -> Usuario:
    sb = obter_conexao()
    email = email.strip().lower()
    # Verifica duplicidade
    ex = sb.table("usuario").select("id").eq("email", email).execute()
    if ex.data:
        raise ValueError("E-mail já cadastrado.")
    chave = secrets.token_hex(8).upper()
    # Primeiro usuário vira ADMIN automaticamente
    if not existe_algum_usuario():
        perfil = "ADMIN"
        aprovado = True
    else:
        aprovado = False
    r = sb.table("usuario").insert({
        "nome": nome.strip(),
        "email": email,
        "senha_hash": _hash(senha),
        "perfil": perfil,
        "aprovado": aprovado,
        "chave_aprovacao": chave,
    }).execute()
    return _row(r.data[0])


def autenticar(email: str, senha: str) -> Optional[Usuario]:
    sb = obter_conexao()
    r = sb.table("usuario").select("*").eq("email", email.strip().lower()).execute()
    if not r.data:
        return None
    d = r.data[0]
    if not _verificar(senha, d["senha_hash"]):
        return None
    # Atualiza ultimo_login
    sb.table("usuario").update({"ultimo_login": "NOW()"}).eq("id", d["id"]).execute()
    return _row(d)


def buscar_por_id(uid: int) -> Optional[Usuario]:
    sb = obter_conexao()
    r = sb.table("usuario").select("*").eq("id", uid).execute()
    return _row(r.data[0]) if r.data else None


def listar_todos() -> list[Usuario]:
    sb = obter_conexao()
    r = sb.table("usuario").select("*").order("nome").execute()
    return [_row(d) for d in r.data]


def alterar_perfil(uid: int, novo_perfil: str) -> None:
    obter_conexao().table("usuario").update({"perfil": novo_perfil}).eq("id", uid).execute()


def aprovar(uid: int) -> None:
    obter_conexao().table("usuario").update({"aprovado": True}).eq("id", uid).execute()


def reprovar(uid: int) -> None:
    obter_conexao().table("usuario").update({"ativo": False}).eq("id", uid).execute()


def alterar_senha(uid: int, nova: str, deve_trocar: bool = False) -> None:
    if len(nova) < 8:
        raise ValueError("Senha deve ter pelo menos 8 caracteres.")
    obter_conexao().table("usuario").update({
        "senha_hash": _hash(nova),
        "deve_trocar_senha": deve_trocar,
    }).eq("id", uid).execute()


def sincronizar_aprovacoes_com_secrets() -> None:
    """Aprova usuários cujas chaves estejam nos Streamlit Secrets."""
    try:
        chaves = st.secrets.get("usuarios_aprovados", {}).get("chaves", [])
        if not chaves:
            return
        sb = obter_conexao()
        for chave in chaves:
            sb.table("usuario").update({"aprovado": True}).eq(
                "chave_aprovacao", chave
            ).execute()
    except Exception:
        pass
