"""
Tela Cadastros · Upload da planilha do Sankhya.
"""
from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from src.banco import repo_cadastros
from src.utils.formatadores import nome_mes
from src.utils.marca import AZUL_ESCURO


COLUNAS_NECESSARIAS = [
    "Canal de Origem",
    "Data cadastramento",
    "Cód. Parceiro",
    "Nome Parceiro",
]


def renderizar_cad_upload(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📥 Cadastros · Upload</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Faça upload da planilha **Cadastro_ativos_por_origem.xlsx** exportada do Sankhya. "
        "O sistema lê só as colunas necessárias (Canal de Origem, Data, Cód./Nome Parceiro)."
    )

    msg = st.session_state.pop("cad_upload_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    arquivo = st.file_uploader(
        "Selecione a planilha (.xlsx)",
        type=["xlsx", "xls"],
        key="cad_arquivo",
    )

    if not arquivo:
        return

    # Hash pra anti-reprocessamento
    bytes_arq = arquivo.getvalue()
    hash_arq = hashlib.md5(bytes_arq).hexdigest()

    if st.session_state.get("cad_hash_processado") == hash_arq:
        st.warning(
            "ℹ️ Essa planilha já foi processada nessa sessão. "
            "Pra reprocessar (caso tenha excluído registros), clique abaixo:"
        )
        if st.button("🔄 Reprocessar mesmo assim", key="cad_btn_reproc"):
            st.session_state.pop("cad_hash_processado", None)
            st.rerun()
        return

    # ─── Lê planilha ─────────────────────────
    try:
        df = pd.read_excel(BytesIO(bytes_arq))
    except Exception as e:
        st.error(f"❌ Erro ao ler a planilha: {e}")
        return

    st.success(f"📄 Planilha carregada: **{len(df)}** linha(s) brutas")

    # Confere colunas necessárias
    faltando = [c for c in COLUNAS_NECESSARIAS if c not in df.columns]
    if faltando:
        st.error(
            f"❌ Faltam colunas obrigatórias: **{', '.join(faltando)}**. "
            f"Re-exporte do Sankhya incluindo essas colunas."
        )
        return

    # Mantém só colunas necessárias
    df = df[COLUNAS_NECESSARIAS].copy()

    # Limpa
    df["Cód. Parceiro"] = pd.to_numeric(df["Cód. Parceiro"], errors="coerce")
    df["Data cadastramento"] = pd.to_datetime(df["Data cadastramento"], errors="coerce")
    df = df.dropna(subset=["Cód. Parceiro", "Data cadastramento"])

    if df.empty:
        st.warning("⚠️ Nenhuma linha válida encontrada após limpeza.")
        return

    # Diagnóstico por canal
    st.markdown("### 📊 Diagnóstico da planilha")
    contagem = df["Canal de Origem"].fillna("(sem canal)").value_counts()

    cols_diag = st.columns(min(len(contagem), 5))
    for i, (canal, qtd) in enumerate(contagem.items()):
        with cols_diag[i % len(cols_diag)]:
            cor = repo_cadastros.cor_canal(canal if canal != "(sem canal)" else None)
            emoji = repo_cadastros.emoji_canal(canal if canal != "(sem canal)" else None)
            st.markdown(
                f"""<div style='background:{cor}; color:white; padding:14px;
                border-radius:8px; text-align:center;'>
                <div style='font-size:24px;'>{emoji}</div>
                <div style='font-size:12px; font-weight:600;'>{canal}</div>
                <div style='font-size:22px; font-weight:700;'>{qtd}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.caption(f"Período: **{df['Data cadastramento'].min().date()}** "
               f"a **{df['Data cadastramento'].max().date()}**")

    # Prévia
    with st.expander("👀 Ver primeiras 10 linhas", expanded=False):
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

    # ─── Botão de gravar ─────────────────────
    st.markdown("---")
    st.markdown("### 💾 Gravar no banco")

    st.info(
        "Cada cadastro é único pelo **Cód. Parceiro**. "
        "Se já existir, será atualizado (sem duplicar)."
    )

    if st.button("✅ Gravar todos os cadastros", type="primary",
                 use_container_width=True, key="cad_btn_gravar"):
        try:
            registros = []
            for _, row in df.iterrows():
                registros.append({
                    "cod_parceiro": int(row["Cód. Parceiro"]),
                    "nome_parceiro": str(row["Nome Parceiro"] or "").strip(),
                    "canal_origem": (str(row["Canal de Origem"]).strip()
                                     if pd.notna(row["Canal de Origem"])
                                     else None),
                    "data_cadastramento": row["Data cadastramento"].date(),
                })

            res = repo_cadastros.upsert_cadastros_em_lote(
                registros,
                nome_arquivo_origem=arquivo.name,
                criado_por_id=usuario.id,
            )

            st.session_state["cad_hash_processado"] = hash_arq
            st.session_state["cad_upload_msg"] = {
                "tipo": "sucesso",
                "texto": (
                    f"✅ **{res['total']}** registros processados:\n"
                    f"- 🆕 Criados: **{res['criados']}**\n"
                    f"- 🔄 Atualizados: **{res['atualizados']}**\n"
                    f"- ⏭️ Ignorados (sem dados): {res['ignorados']}"
                ),
            }
            st.toast("✅ Cadastros gravados!", icon="✅")
            st.rerun()
        except Exception as e:
            st.session_state["cad_upload_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao gravar: {type(e).__name__}: {e}",
            }
            st.rerun()
