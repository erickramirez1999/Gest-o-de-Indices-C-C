"""
Tela Financeiro · Reparo / Recuperação

Pra casos onde alguma unificação ou exclusão deu errado:
  - Reatribuir lançamentos de um fornecedor pra outro (desfazer unificação)
  - Reativar fornecedor desativado
  - Ver auditoria de quais lançamentos estão em cada fornecedor
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.banco import repo_financeiro
from src.banco.conexao import obter_conexao
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO


def _reatribuir_lancamentos_por_ids(ids_lancamentos: list, fornecedor_destino: dict) -> int:
    """Move uma lista específica de lançamentos pra um fornecedor."""
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({
               "fornecedor_id": fornecedor_destino["id"],
               "cnpj_fornecedor": fornecedor_destino["cnpj"],
               "nome_fornecedor": fornecedor_destino["nome"],
               "categoria": fornecedor_destino.get("categoria"),
           })
           .in_("id", ids_lancamentos)
           .execute())
    return len(res.data) if res.data else 0


def _reativar_fornecedor(fornecedor_id: int) -> None:
    sb = obter_conexao()
    sb.table("fornecedor_financeiro").update({"ativo": True}).eq("id", fornecedor_id).execute()


def renderizar_fin_reparo(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🔧 Financeiro · Reparo / Recuperação</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Ferramentas pra corrigir erros de unificação ou recuperar dados. "
        "Use com cautela — você seleciona exatamente quais lançamentos mover."
    )

    msg = st.session_state.pop("fin_rep_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    # ─── Tab 1: Reatribuir lançamentos ─────────────────────────
    aba_realoc, aba_reativ = st.tabs([
        "🔄 Reatribuir lançamentos",
        "✅ Reativar fornecedor",
    ])

    fornecedores = repo_financeiro.listar_fornecedores(apenas_ativos=False)

    with aba_realoc:
        st.caption(
            "Selecione um fornecedor pra ver TODOS os lançamentos dele. "
            "Marque os que estão errados e escolha pra qual fornecedor mandar."
        )

        if not fornecedores:
            st.info("Nenhum fornecedor cadastrado.")
        else:
            # Mostra TODOS (ativos + inativos) — porque a maioria dos casos
            # de erro é exatamente em fornecedor que absorveu lançamentos errados
            opcoes_origem = {
                f"{f['nome']} — {f['cnpj']} (ID {f['id']}, "
                f"{'ATIVO' if f.get('ativo', True) else 'INATIVO'})": f
                for f in fornecedores
            }
            sel_origem = st.selectbox(
                "Fornecedor de ORIGEM (de onde tirar os lançamentos)",
                list(opcoes_origem.keys()),
                key="fin_rep_origem",
            )
            forn_origem = opcoes_origem[sel_origem]

            # Lista lançamentos desse fornecedor
            sb = obter_conexao()
            lancs = (sb.table("dados_financeiro_gasto")
                     .select("*")
                     .eq("fornecedor_id", forn_origem["id"])
                     .order("data_emissao", desc=True)
                     .execute().data or [])

            if not lancs:
                st.info(f"📭 Esse fornecedor não tem lançamentos.")
            else:
                st.markdown(f"##### 📋 Lançamentos de **{forn_origem['nome']}** ({len(lancs)} total)")

                # Tabela
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
                df = pd.DataFrame(rows)

                edited = st.data_editor(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["ID", "Mês", "Data", "NF", "Valor", "Descrição"],
                    column_config={
                        "✓": st.column_config.CheckboxColumn(
                            "Marcar pra mover",
                            help="Marque as linhas que quer reatribuir",
                            default=False,
                        ),
                    },
                    key=f"fin_rep_editor_{forn_origem['id']}",
                )

                ids_selecionados = edited.loc[edited["✓"] == True, "ID"].tolist()

                if not ids_selecionados:
                    st.info("👆 Marque pelo menos um lançamento.")
                else:
                    valor_total_sel = sum(
                        float(l.get("valor", 0)) for l in lancs
                        if l["id"] in ids_selecionados
                    )

                    st.markdown(f"##### 🎯 Mover **{len(ids_selecionados)}** lançamento(s) (total {formatar_brl(valor_total_sel)}) pra:")

                    opcoes_dest = {
                        f"{f['nome']} — {f['cnpj']} (ID {f['id']})": f
                        for f in fornecedores if f["id"] != forn_origem["id"]
                    }

                    sel_dest = st.selectbox(
                        "Fornecedor de DESTINO",
                        list(opcoes_dest.keys()),
                        key="fin_rep_destino",
                    )
                    forn_dest = opcoes_dest[sel_dest]

                    st.warning(
                        f"**Vai mover {len(ids_selecionados)} lançamento(s) "
                        f"({formatar_brl(valor_total_sel)})** de "
                        f"`{forn_origem['nome']}` → `{forn_dest['nome']}`"
                    )

                    confirma_txt = st.text_input(
                        "Pra confirmar, digite **MOVER**:",
                        key="fin_rep_conf",
                        placeholder="MOVER",
                    )
                    confirma_ok = confirma_txt.strip().upper() == "MOVER"

                    if st.button(
                        f"🔄 Mover {len(ids_selecionados)} lançamento(s)",
                        type="primary",
                        disabled=not confirma_ok,
                        use_container_width=True,
                        key="fin_rep_btn_mover",
                    ):
                        try:
                            movidos = _reatribuir_lancamentos_por_ids(ids_selecionados, forn_dest)

                            # Se o fornecedor destino estava inativo, reativa
                            if not forn_dest.get("ativo", True):
                                _reativar_fornecedor(forn_dest["id"])

                            st.session_state["fin_rep_msg"] = {
                                "tipo": "sucesso",
                                "texto": (
                                    f"✅ **{movidos}** lançamento(s) movido(s) "
                                    f"de `{forn_origem['nome']}` "
                                    f"pra `{forn_dest['nome']}`."
                                ),
                            }
                            st.toast("✅ Movidos!", icon="✅")
                            st.rerun()
                        except Exception as e:
                            st.session_state["fin_rep_msg"] = {
                                "tipo": "erro",
                                "texto": f"❌ Erro ao mover: {type(e).__name__}: {e}",
                            }
                            st.rerun()

    with aba_reativ:
        st.caption(
            "Fornecedores que foram desativados (por unificação acidental, por exemplo) "
            "podem ser reativados aqui. **Os lançamentos NÃO voltam automaticamente** — "
            "use a aba 'Reatribuir lançamentos' pra recuperá-los."
        )

        inativos = [f for f in fornecedores if not f.get("ativo", True)]

        if not inativos:
            st.info("✅ Nenhum fornecedor inativo.")
        else:
            st.markdown(f"**{len(inativos)}** fornecedor(es) inativo(s):")
            for f in inativos:
                col_n, col_b = st.columns([3, 1])
                with col_n:
                    st.markdown(f"- **ID {f['id']}**: `{f['nome']}` ({f['cnpj']})")
                with col_b:
                    if st.button(
                        "✅ Reativar",
                        key=f"fin_rep_reat_{f['id']}",
                    ):
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
                                "texto": f"❌ Erro: {e}",
                            }
                            st.rerun()
