"""Conexão com Supabase — LLE Índices."""
from __future__ import annotations
import os
import streamlit as st

_conn = None


def obter_conexao():
    global _conn
    if _conn is not None:
        return _conn
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        raise RuntimeError("Supabase não configurado. Verifique os secrets.")

    from supabase import create_client
    _conn = create_client(url, key)
    return _conn
