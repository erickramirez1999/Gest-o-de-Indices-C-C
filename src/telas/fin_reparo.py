"""Tela Financeiro · Reparo / Recuperação."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.banco import repo_financeiro
from src.banco.conexao import obter_conexao
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO


def _reatribuir_lancamentos_por_ids(ids_lancamentos, fornecedor_destino):
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({
               "fornecedor_id": fornecedor_destino["id"],
               "cnpj_fornecedor": fornecedor_destino["cnpj"],
               "nome_fornecedor": fornecedor_destino["nome"],
               "categoria": fornecedor_destino.get("categoria"),
           })
           .in_("id", ids_lancamentos).execute())
    return len(res.data) if res.data else 0


def _reativar_fornecedor(fornecedor_id):
    sb = obter_conexao()
    sb.table("fornecedor_financeiro").update({"ativo": True}).eq("id", fornecedor_id).execute()


def renderizar_fin_reparo(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🔧 Financeiro · Reparo</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Recuperar lançamentos que foram movidos errado, reativar fornecedores.")

    msg = st.session_state.pop("fin_rep_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    aba1, aba2 = st.tabs(["🔄 Reatribuir lançamentos", "✅ Reativar fornecedor"])
    fornecedores = repo_financeiro.listar_fornecedores(apenas_ativos=False)

    with aba1:
        st.caption("Selecione um fornecedor, marque os lançamentos errados, escolha pra qual mandar.")
        if not fornecedores:
            st.info("Nenhum fornecedor cadastrado.")
        else:
            opcoes_origem = {
                f"{f['nome']} — {f['cnpj']} (ID {f['id']}, "
                f"{'ATIVO' if f.get('ativo', True) else 'INATIVO'})": f
                for f in fornecedores
            }
            sel_origem = st.selectbox(
                "Fornecedor de ORIGEM (de onde tirar)",
                list(opcoes_origem.keys()),
                key="fin_rep_origem",
            )
            forn_origem = opcoes_origem[sel_origem]

            sb = obter_conexao()
            lancs = (sb.table("dados_financeiro_gasto")
                     .select("*").eq("fornecedor_id", forn_origem["id"])
                     .order("data_emissao", desc=True).execute().data or [])

            if not lancs:
                st.info("📭 Sem lançamentos nesse fornecedor.")
            else:
                st.markdown(f"##### 📋 Lançamentos de **{forn_origem['nome']}** ({len(lancs)})")
                rows = []
                for l in lancs:
                    rows.append({
                        "✓": False,
                        "ID": l["id"],
                        "Mês": l.get("mes_ano"),
                        "Data": l.get("data_emissao") or "—",
                        "NF": l.get("numero_nf") or "—",
                        "Valor": formatar_brl(l.get("valor", 0)),
                        "Descrição": (l.get("descricao_servico") or "")[:60],
                    })
                edited = st.data_editor(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                    disabled=["ID", "Mês", "Data", "NF", "Valor", "Descrição"],
                    column_config={
                        "✓": st.column_config.CheckboxColumn(
                            "Marcar pra mover", default=False,
                        ),
                    },
                    key=f"fin_rep_editor_{forn_origem['id']}",
                )
                ids_sel = edited.loc[edited["✓"] == True, "ID"].tolist()

                if not ids_sel:
                    st.info("👆 Marque pelo menos um lançamento.")
                else:
                    valor_total = sum(
                        float(l.get("valor", 0)) for l in lancs if l["id"] in ids_sel
                    )
                    st.markdown(
                        f"##### 🎯 Mover **{len(ids_sel)}** ({formatar_brl(valor_total)}) pra:"
                    )
                    opcoes_d = {
                        f"{f['nome']} — {f['cnpj']} (ID {f['id']})": f
                        for f in fornecedores if f["id"] != forn_origem["id"]
                    }
                    sel_d = st.selectbox("DESTINO", list(opcoes_d.keys()), key="fin_rep_dest")
                    forn_d = opcoes_d[sel_d]

                    st.warning(
                        f"**Vai mover {len(ids_sel)} lançamento(s) ({formatar_brl(valor_total)})** "
                        f"de `{forn_origem['nome']}` → `{forn_d['nome']}`"
                    )

                    conf = st.text_input(
                        "Pra confirmar, digite **MOVER**:",
                        key="fin_rep_conf",
                        placeholder="MOVER",
                    )
                    ok = conf.strip().upper() == "MOVER"

                    if st.button(
                        f"🔄 Mover {len(ids_sel)} lançamento(s)",
                        type="primary",
                        disabled=not ok,
                        use_container_width=True,
                        key="fin_rep_btn",
                    ):
                        try:
                            mov = _reatribuir_lancamentos_por_ids(ids_sel, forn_d)
                            if not forn_d.get("ativo", True):
                                _reativar_fornecedor(forn_d["id"])
                            st.session_state["fin_rep_msg"] = {
                                "tipo": "sucesso",
                                "texto": (
                                    f"✅ **{mov}** lançamento(s) movido(s) "
                                    f"de `{forn_origem['nome']}` "
                                    f"pra `{forn_d['nome']}`."
                                ),
                            }
                            st.toast("✅ Movidos!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.session_state["fin_rep_msg"] = {
                                "tipo": "erro",
                                "texto": f"❌ Erro: {type(e).__name__}: {e}",
                            }
                            st.rerun()

    with aba2:
        st.caption("Reativar fornecedores que foram desativados.")
        inativos = [f for f in fornecedores if not f.get("ativo", True)]
        if not inativos:
            st.info("✅ Nenhum inativo.")
        else:
            st.markdown(f"**{len(inativos)}** inativo(s):")
            for f in inativos:
                col_n, col_b = st.columns([3, 1])
                with col_n:
                    st.markdown(f"- **ID {f['id']}**: `{f['nome']}` ({f['cnpj']})")
                with col_b:
                    if st.button("✅ Reativar", key=f"fin_rep_re_{f['id']}"):
                        try:
                            _reativar_fornecedor(f["id"])
                            st.session_state["fin_rep_msg"] = {
                                "tipo": "sucesso",
                                "texto": f"✅ `{f['nome']}` reativado.",
                            }
                            st.rerun()
                        except Exception as e:
                            st.session_state["fin_rep_msg"] = {
                                "tipo": "erro",
                                "texto": f"❌ {e}",
                            }
                            st.rerun()
