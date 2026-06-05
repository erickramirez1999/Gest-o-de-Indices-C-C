"""Tela Financeiro · Fornecedores — CRUD + Detectar duplicados por CNPJ."""
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


def _propagar_nome(forn_id, novo_nome):
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"nome_fornecedor": novo_nome})
           .eq("fornecedor_id", forn_id).execute())
    return len(res.data) if res.data else 0


def _propagar_categoria(forn_id, nova_cat):
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"categoria": nova_cat})
           .eq("fornecedor_id", forn_id).execute())
    return len(res.data) if res.data else 0


def _unificar(id_origem, id_destino):
    sb = obter_conexao()
    dest = sb.table("fornecedor_financeiro").select("*").eq("id", id_destino).limit(1).execute()
    if not dest.data:
        raise ValueError(f"Destino {id_destino} não encontrado")
    d = dest.data[0]
    upd = (sb.table("dados_financeiro_gasto")
           .update({
               "fornecedor_id": id_destino,
               "cnpj_fornecedor": d["cnpj"],
               "nome_fornecedor": d["nome"],
               "categoria": d.get("categoria"),
           })
           .eq("fornecedor_id", id_origem).execute())
    movidos = len(upd.data) if upd.data else 0
    sb.table("fornecedor_financeiro").update({"ativo": False}).eq("id", id_origem).execute()
    return movidos


def renderizar_fin_fornecedores(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🏢 Financeiro · Fornecedores</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Edite cadastros e detecte duplicados por CNPJ. "
        "Pra recuperar dados, use 🔧 Reparo."
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
    contagem, valores = {}, {}
    for g in gastos:
        fid = g["fornecedor_id"]
        contagem[fid] = contagem.get(fid, 0) + 1
        valores[fid] = valores.get(fid, 0) + float(g.get("valor", 0))

    # ─── Tabela
    st.markdown("### 📋 Fornecedores cadastrados")
    filtro = st.radio("Filtrar", ["Todos", "Só ativos", "Só inativos"], horizontal=True, key="fin_f_filt")
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

    # ─── Detector de duplicados
    st.markdown("---")
    st.markdown("### 🔍 Detectar duplicados por CNPJ")

    fornecedores_ativos = [f for f in fornecedores if f.get("ativo", True)]

    def _so_digs(s):
        return re.sub(r"\D", "", s or "")

    por_cnpj = {}
    for f in fornecedores_ativos:
        c = _so_digs(f.get("cnpj", ""))
        if c:
            por_cnpj.setdefault(c, []).append(f)

    duplicados = {k: v for k, v in por_cnpj.items() if len(v) >= 2}

    st.caption(
        f"🔎 **{len(fornecedores_ativos)}** ativo(s) · "
        f"**{len(por_cnpj)}** CNPJ(s) único(s) · "
        f"**{len(duplicados)}** duplicado(s)"
    )

    if not duplicados:
        st.success("✅ Nenhum CNPJ duplicado.")
    else:
        st.warning(f"⚠️ Encontrei {len(duplicados)} CNPJ(s) com mais de um cadastro:")
        for cnpj, grupo in duplicados.items():
            grupo_ord = sorted(grupo, key=lambda f: (
                contagem.get(f["id"], 0), valores.get(f["id"], 0)
            ), reverse=True)
            dest_sug = grupo_ord[0]
            cnpj_fmt = grupo_ord[0].get("cnpj", cnpj)

            with st.expander(f"🔁 CNPJ **{cnpj_fmt}** ({len(grupo)} cadastros)", expanded=True):
                for f in grupo_ord:
                    marca = "🟢 MANTER" if f["id"] == dest_sug["id"] else "🔴 ABSORVER"
                    st.markdown(
                        f"- **ID {f['id']}**: `{f['nome']}` — "
                        f"{contagem.get(f['id'], 0)} NF · "
                        f"{formatar_brl(valores.get(f['id'], 0))} — {marca}"
                    )

                opcoes = {
                    f"ID {f['id']} — {f['nome']}": f for f in grupo_ord
                }

                col_d, col_o = st.columns(2)
                with col_d:
                    st.markdown("**🟢 MANTER:**")
                    keys = list(opcoes.keys())
                    idx_sug = next(
                        (i for i, k in enumerate(keys) if opcoes[k]["id"] == dest_sug["id"]),
                        0,
                    )
                    sel_d = st.selectbox(
                        "Destino", keys, index=idx_sug,
                        key=f"fd_d_{cnpj}", label_visibility="collapsed",
                    )
                    forn_d = opcoes[sel_d]

                with col_o:
                    st.markdown("**🔴 ABSORVER:**")
                    keys_o = [k for k in opcoes if opcoes[k]["id"] != forn_d["id"]]
                    sel_o = st.multiselect(
                        "Origens", keys_o, default=keys_o,
                        key=f"fd_o_{cnpj}", label_visibility="collapsed",
                    )
                    forn_origens = [opcoes[k] for k in sel_o]

                if not forn_origens:
                    st.info("Selecione pelo menos 1 origem.")
                    continue

                confirma = st.text_input(
                    "Digite **UNIFICAR** pra liberar o botão:",
                    key=f"fd_c_{cnpj}", placeholder="UNIFICAR",
                )
                pode = confirma.strip().upper() == "UNIFICAR"

                if st.button(
                    f"🔗 Unificar {len(forn_origens)} → {forn_d['nome'][:40]}",
                    type="primary", disabled=not pode,
                    use_container_width=True,
                    key=f"fd_b_{cnpj}",
                ):
                    try:
                        total = 0
                        for fo in forn_origens:
                            total += _unificar(fo["id"], forn_d["id"])
                        st.session_state["fin_forn_msg"] = {
                            "tipo": "sucesso",
                            "texto": f"✅ CNPJ {cnpj_fmt}: {total} lançamento(s) movidos pra {forn_d['nome']}",
                        }
                        st.rerun()
                    except Exception as e:
                        st.session_state["fin_forn_msg"] = {
                            "tipo": "erro", "texto": f"❌ {type(e).__name__}: {e}",
                        }
                        st.rerun()

    # ─── Editar
    st.markdown("---")
    st.markdown("### ✏️ Editar fornecedor")
    opcoes = {f"{f['nome']} — {f['cnpj']} (ID {f['id']})": f for f in forn_filt}
    if not opcoes:
        st.info("Sem fornecedores pra editar.")
        return

    escolha = st.selectbox("Selecione", list(opcoes.keys()), key="fin_f_sel")
    forn = opcoes[escolha]
    qtd = contagem.get(forn["id"], 0)
    if qtd > 0:
        st.info(f"ℹ️ {qtd} lançamento(s). Mudanças podem ser propagadas.")

    col_n, col_c = st.columns([2, 1])
    with col_n:
        novo_nome = st.text_input("Nome *", value=forn["nome"], key=f"en_{forn['id']}").upper().strip()
    with col_c:
        st.text_input("CNPJ", value=forn["cnpj"], disabled=True, key=f"ec_{forn['id']}")

    col_cat, col_mun, col_uf = st.columns([2, 2, 1])
    with col_cat:
        cat_at = forn.get("categoria") or "OUTROS"
        idx = CATEGORIAS_PADRAO.index(cat_at) if cat_at in CATEGORIAS_PADRAO else CATEGORIAS_PADRAO.index("OUTROS")
        nova_cat = st.selectbox("Categoria *", CATEGORIAS_PADRAO, index=idx, key=f"ecat_{forn['id']}")
    with col_mun:
        novo_mun = st.text_input("Município", value=forn.get("municipio") or "", key=f"em_{forn['id']}")
    with col_uf:
        novo_uf = st.text_input("UF", value=forn.get("uf") or "", max_chars=2, key=f"eu_{forn['id']}").upper()

    novo_ativo = st.checkbox("Ativo", value=forn.get("ativo", True), key=f"ea_{forn['id']}")

    mudou_n = novo_nome != forn["nome"]
    mudou_c = nova_cat != (forn.get("categoria") or "OUTROS")
    prop_n = prop_c = False
    if qtd > 0 and (mudou_n or mudou_c):
        st.markdown("##### Propagar mudanças?")
        c1, c2 = st.columns(2)
        if mudou_n:
            with c1:
                prop_n = st.checkbox(f"📝 Atualizar nome em {qtd} lanç.", value=True, key=f"pn_{forn['id']}")
        if mudou_c:
            with c2:
                prop_c = st.checkbox(f"🏷️ Atualizar categoria em {qtd} lanç.", value=True, key=f"pc_{forn['id']}")

    if not novo_nome or len(novo_nome) < 3:
        st.warning("Nome obrigatório (mín. 3)")
        return

    if st.button("💾 Salvar", type="primary", use_container_width=True, key=f"eb_{forn['id']}"):
        try:
            _atualizar_fornecedor_completo(forn["id"], novo_nome, nova_cat, novo_mun, novo_uf, novo_ativo)
            partes = ["✅ Atualizado!"]
            if prop_n:
                n = _propagar_nome(forn["id"], novo_nome)
                partes.append(f"- Nome em {n} lanç.")
            if prop_c:
                n = _propagar_categoria(forn["id"], nova_cat)
                partes.append(f"- Categoria em {n} lanç.")
            st.session_state["fin_forn_msg"] = {"tipo": "sucesso", "texto": "\n".join(partes)}
            st.rerun()
        except Exception as e:
            st.session_state["fin_forn_msg"] = {"tipo": "erro", "texto": f"❌ {e}"}
            st.rerun()
