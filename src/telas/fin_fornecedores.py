"""
Tela Financeiro · Cadastro de Fornecedores

CRUD de fornecedores + detecção de duplicados por CNPJ + unificação manual.
"""
from __future__ import annotations

import re
import pandas as pd
import streamlit as st

from src.banco import repo_financeiro
from src.banco.conexao import obter_conexao
from src.utils.formatadores import formatar_brl
from src.utils.marca import AZUL_ESCURO


CATEGORIAS_PADRAO = [
    "PROTESTO", "SOFTWARE", "HOSPEDAGEM", "CONTABIL", "JURÍDICO",
    "MARKETING", "CONSULTORIA", "TRANSPORTE", "TELECOM", "ALUGUEL",
    "ENERGIA", "ÁGUA", "LIMPEZA", "MATERIAL", "BANCO",
    "SALÁRIOS", "IMPOSTOS", "OUTROS",
]


def _atualizar_fornecedor_completo(forn_id, nome, categoria, municipio, uf, ativo):
    sb = obter_conexao()
    sb.table("fornecedor_financeiro").update({
        "nome": nome, "categoria": categoria,
        "municipio": municipio or None, "uf": uf or None, "ativo": ativo,
    }).eq("id", forn_id).execute()


def _propagar_nome_para_gastos(forn_id, novo_nome):
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"nome_fornecedor": novo_nome})
           .eq("fornecedor_id", forn_id).execute())
    return len(res.data) if res.data else 0


def _propagar_categoria_para_gastos(forn_id, nova_cat):
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"categoria": nova_cat})
           .eq("fornecedor_id", forn_id).execute())
    return len(res.data) if res.data else 0


def _unificar_fornecedores(id_origem, id_destino):
    """Move lançamentos do origem pro destino, desativa o origem."""
    sb = obter_conexao()
    destino_res = sb.table("fornecedor_financeiro").select("*").eq("id", id_destino).limit(1).execute()
    if not destino_res.data:
        raise ValueError(f"Destino (ID {id_destino}) não encontrado.")
    destino = destino_res.data[0]
    upd = (sb.table("dados_financeiro_gasto")
           .update({
               "fornecedor_id": id_destino,
               "cnpj_fornecedor": destino["cnpj"],
               "nome_fornecedor": destino["nome"],
               "categoria": destino.get("categoria"),
           })
           .eq("fornecedor_id", id_origem).execute())
    movidos = len(upd.data) if upd.data else 0
    sb.table("fornecedor_financeiro").update({"ativo": False}).eq("id", id_origem).execute()
    return {"movidos": movidos}


def renderizar_fin_fornecedores(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🏢 Financeiro · Fornecedores</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Edite cadastros e detecte duplicações. "
        "Se algo der errado, use a tela **🔧 Reparo** pra recuperar."
    )

    msg = st.session_state.pop("fin_forn_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    fornecedores = repo_financeiro.listar_fornecedores(apenas_ativos=False)
    if not fornecedores:
        st.info("📭 Nenhum fornecedor cadastrado ainda.")
        return

    sb = obter_conexao()
    gastos = sb.table("dados_financeiro_gasto").select("fornecedor_id, valor").execute().data or []
    contagem = {}
    valores = {}
    for g in gastos:
        fid = g["fornecedor_id"]
        contagem[fid] = contagem.get(fid, 0) + 1
        valores[fid] = valores.get(fid, 0) + float(g.get("valor", 0))

    # ─── Tabela ─────────────────────────
    st.markdown("### 📋 Fornecedores cadastrados")
    filtro = st.radio("Filtrar", ["Todos", "Só ativos", "Só inativos"], horizontal=True, key="fin_forn_filt")
    if filtro == "Só ativos":
        forn_filt = [f for f in fornecedores if f.get("ativo", True)]
    elif filtro == "Só inativos":
        forn_filt = [f for f in fornecedores if not f.get("ativo", True)]
    else:
        forn_filt = fornecedores

    rows = []
    for f in forn_filt:
        rows.append({
            "ID": f["id"], "Nome": f["nome"], "CNPJ": f["cnpj"],
            "Categoria": f.get("categoria") or "—",
            "Local": f"{f.get('municipio') or ''}/{f.get('uf') or ''}".strip("/"),
            "NFs": contagem.get(f["id"], 0),
            "Total": formatar_brl(valores.get(f["id"], 0)),
            "Ativo": "✅" if f.get("ativo", True) else "❌",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"Total: **{len(forn_filt)}** fornecedor(es)")

    # ─── DETECÇÃO DE DUPLICADOS ─────────────────────────
    fornecedores_ativos = [f for f in fornecedores if f.get("ativo", True)]

    st.markdown("---")
    st.markdown("### 🔍 Detectar duplicados por CNPJ")
    st.caption("Lista cadastros que têm o **mesmo CNPJ**. Você confirma cada unificação manualmente.")

    def _so_digitos(s):
        return re.sub(r"\D", "", s or "")

    por_cnpj = {}
    for f in fornecedores_ativos:
        cnpj_norm = _so_digitos(f.get("cnpj", ""))
        if cnpj_norm:
            por_cnpj.setdefault(cnpj_norm, []).append(f)

    duplicados = {k: v for k, v in por_cnpj.items() if len(v) >= 2}
    st.caption(
        f"🔎 **{len(fornecedores_ativos)}** ativo(s) · "
        f"**{len(por_cnpj)}** CNPJ(s) único(s) · "
        f"**{len(duplicados)}** com duplicação"
    )

    if not duplicados:
        st.success("✅ Nenhum CNPJ duplicado entre os ativos.")
    else:
        st.warning(f"⚠️ Encontrei **{len(duplicados)}** CNPJ(s) duplicado(s):")
        for cnpj, grupo in duplicados.items():
            grupo_ord = sorted(
                grupo,
                key=lambda f: (contagem.get(f["id"], 0), valores.get(f["id"], 0)),
                reverse=True,
            )
            destino_sug = grupo_ord[0]
            cnpj_fmt = grupo_ord[0].get("cnpj", cnpj)

            with st.expander(f"🔁 CNPJ **{cnpj_fmt}** ({len(grupo)} cadastros)", expanded=True):
                for f in grupo_ord:
                    marca = "🟢 MANTER (sugerido)" if f["id"] == destino_sug["id"] else "🔴 ABSORVER"
                    st.markdown(
                        f"- **ID {f['id']}**: `{f['nome']}` — "
                        f"{contagem.get(f['id'], 0)} NF · "
                        f"{formatar_brl(valores.get(f['id'], 0))} — {marca}"
                    )

                opcoes = {
                    f"ID {f['id']} — {f['nome']} ({contagem.get(f['id'], 0)} NF, "
                    f"{formatar_brl(valores.get(f['id'], 0))})": f
                    for f in grupo_ord
                }

                col_d, col_o = st.columns(2)
                with col_d:
                    st.markdown("**🟢 MANTER:**")
                    keys = list(opcoes.keys())
                    idx_sug = next((i for i, k in enumerate(keys) if opcoes[k]["id"] == destino_sug["id"]), 0)
                    sel_d = st.selectbox(
                        "Destino", keys, index=idx_sug,
                        key=f"dup_dest_{cnpj}",
                        label_visibility="collapsed",
                    )
                    forn_destino = opcoes[sel_d]

                with col_o:
                    st.markdown("**🔴 ABSORVER:**")
                    keys_orig = [k for k in opcoes if opcoes[k]["id"] != forn_destino["id"]]
                    sel_origens = st.multiselect(
                        "Origens", keys_orig, default=keys_orig,
                        key=f"dup_orig_{cnpj}",
                        label_visibility="collapsed",
                    )
                    forn_origens = [opcoes[k] for k in sel_origens]

                if not forn_origens:
                    st.info("Selecione pelo menos 1 origem.")
                    continue

                # Confirmação por texto (anti-duplo-clique)
                confirma = st.text_input(
                    f"Pra confirmar a unificação desse CNPJ, digite **UNIFICAR**:",
                    key=f"dup_conf_{cnpj}",
                    placeholder="UNIFICAR",
                )
                pode_unif = confirma.strip().upper() == "UNIFICAR"

                if st.button(
                    f"🔗 Unificar {len(forn_origens)} → {forn_destino['nome'][:40]}",
                    type="primary",
                    disabled=not pode_unif,
                    use_container_width=True,
                    key=f"dup_btn_{cnpj}",
                ):
                    try:
                        total_mov = 0
                        for forn_origem in forn_origens:
                            res = _unificar_fornecedores(forn_origem["id"], forn_destino["id"])
                            total_mov += res["movidos"]
                        st.session_state["fin_forn_msg"] = {
                            "tipo": "sucesso",
                            "texto": (
                                f"✅ CNPJ **{cnpj_fmt}** unificado!\n"
                                f"- {total_mov} lançamento(s) movido(s)\n"
                                f"- {len(forn_origens)} cadastro(s) desativado(s)\n"
                                f"- Mantido: **{forn_destino['nome']}**"
                            ),
                        }
                        st.toast("✅ Unificado!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.session_state["fin_forn_msg"] = {
                            "tipo": "erro",
                            "texto": f"❌ Erro: {type(e).__name__}: {e}",
                        }
                        st.rerun()

    # ─── EDITAR FORNECEDOR ─────────────────────────
    st.markdown("---")
    st.markdown("### ✏️ Editar fornecedor")

    opcoes = {f"{f['nome']} — {f['cnpj']} (ID {f['id']})": f for f in forn_filt}
    if not opcoes:
        st.info("Sem fornecedores pra editar.")
        return

    escolha = st.selectbox("Selecione", list(opcoes.keys()), key="fin_forn_sel_edit")
    forn = opcoes[escolha]
    qtd_lanc = contagem.get(forn["id"], 0)
    if qtd_lanc > 0:
        st.info(f"ℹ️ {qtd_lanc} lançamento(s) gravados. Mudanças podem ser propagadas.")

    col_n, col_c = st.columns([2, 1])
    with col_n:
        novo_nome = st.text_input("Nome *", value=forn["nome"], key=f"e_n_{forn['id']}").upper().strip()
    with col_c:
        st.text_input("CNPJ", value=forn["cnpj"], disabled=True, key=f"e_c_{forn['id']}")

    col_cat, col_mun, col_uf = st.columns([2, 2, 1])
    with col_cat:
        cat_at = forn.get("categoria") or "OUTROS"
        idx = CATEGORIAS_PADRAO.index(cat_at) if cat_at in CATEGORIAS_PADRAO else CATEGORIAS_PADRAO.index("OUTROS")
        nova_cat = st.selectbox("Categoria *", CATEGORIAS_PADRAO, index=idx, key=f"e_cat_{forn['id']}")
    with col_mun:
        novo_mun = st.text_input("Município", value=forn.get("municipio") or "", key=f"e_m_{forn['id']}")
    with col_uf:
        novo_uf = st.text_input("UF", value=forn.get("uf") or "", max_chars=2, key=f"e_u_{forn['id']}").upper()

    novo_ativo = st.checkbox("Ativo", value=forn.get("ativo", True), key=f"e_a_{forn['id']}")

    mudou_n = novo_nome != forn["nome"]
    mudou_c = nova_cat != (forn.get("categoria") or "OUTROS")
    prop_n = prop_c = False
    if qtd_lanc > 0 and (mudou_n or mudou_c):
        st.markdown("##### Propagar mudanças?")
        c1, c2 = st.columns(2)
        if mudou_n:
            with c1:
                prop_n = st.checkbox(f"📝 Atualizar nome em {qtd_lanc} lançamento(s)", value=True, key=f"p_n_{forn['id']}")
        if mudou_c:
            with c2:
                prop_c = st.checkbox(f"🏷️ Atualizar categoria em {qtd_lanc} lançamento(s)", value=True, key=f"p_c_{forn['id']}")

    if not novo_nome or len(novo_nome) < 3:
        st.warning("Nome obrigatório (mín. 3 caracteres)")
        return

    if st.button("💾 Salvar alterações", type="primary", use_container_width=True, key=f"e_btn_{forn['id']}"):
        try:
            _atualizar_fornecedor_completo(forn["id"], novo_nome, nova_cat, novo_mun, novo_uf, novo_ativo)
            partes = ["✅ Cadastro atualizado!"]
            if prop_n:
                n = _propagar_nome_para_gastos(forn["id"], novo_nome)
                partes.append(f"- Nome atualizado em {n} lançamento(s)")
            if prop_c:
                n = _propagar_categoria_para_gastos(forn["id"], nova_cat)
                partes.append(f"- Categoria atualizada em {n} lançamento(s)")
            st.session_state["fin_forn_msg"] = {"tipo": "sucesso", "texto": "\n".join(partes)}
            st.toast("✅ Salvo!", icon="✅")
            st.rerun()
        except Exception as e:
            st.session_state["fin_forn_msg"] = {"tipo": "erro", "texto": f"❌ {type(e).__name__}: {e}"}
            st.rerun()
