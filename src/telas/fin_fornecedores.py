"""
Tela Financeiro · Cadastro de Fornecedores

CRUD de fornecedores:
  - Lista todos cadastrados
  - Permite editar nome, categoria, município, UF
  - Permite ativar/desativar
  - Mostra quantas NFs cada fornecedor já teve lançadas
  - Permite propagar mudanças de nome/categoria pros lançamentos existentes
"""
from __future__ import annotations

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


def _atualizar_fornecedor_completo(forn_id: int, nome: str, categoria: str,
                                   municipio: str, uf: str, ativo: bool) -> None:
    """Atualiza vários campos do fornecedor de uma vez."""
    sb = obter_conexao()
    payload = {
        "nome": nome,
        "categoria": categoria,
        "municipio": municipio or None,
        "uf": uf or None,
        "ativo": ativo,
    }
    sb.table("fornecedor_financeiro").update(payload).eq("id", forn_id).execute()


def _propagar_nome_para_gastos(forn_id: int, novo_nome: str) -> int:
    """
    Atualiza nome_fornecedor (snapshot) em TODOS os lançamentos do fornecedor.
    Retorna quantos foram atualizados.
    """
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"nome_fornecedor": novo_nome})
           .eq("fornecedor_id", forn_id)
           .execute())
    return len(res.data) if res.data else 0


def _propagar_categoria_para_gastos(forn_id: int, nova_cat: str) -> int:
    """Idem pra categoria."""
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .update({"categoria": nova_cat})
           .eq("fornecedor_id", forn_id)
           .execute())
    return len(res.data) if res.data else 0


def renderizar_fin_fornecedores(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>🏢 Financeiro · Fornecedores</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Edite o nome, categoria e outros dados dos fornecedores cadastrados. "
        "Útil quando o parser leu o nome errado (ex: pegou 'Código de Verificação' "
        "no lugar do nome real)."
    )

    # Mensagem persistente
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

    # Conta lançamentos por fornecedor
    sb = obter_conexao()
    gastos = sb.table("dados_financeiro_gasto").select(
        "fornecedor_id, valor"
    ).execute().data or []
    contagem = {}
    valores = {}
    for g in gastos:
        fid = g["fornecedor_id"]
        contagem[fid] = contagem.get(fid, 0) + 1
        valores[fid] = valores.get(fid, 0) + float(g.get("valor", 0))

    # ─── Tabela de fornecedores ─────────────────────────
    st.markdown("### 📋 Fornecedores cadastrados")

    filtro_status = st.radio(
        "Filtrar",
        ["Todos", "Só ativos", "Só inativos"],
        horizontal=True,
        key="fin_forn_filtro",
    )

    if filtro_status == "Só ativos":
        forn_filt = [f for f in fornecedores if f.get("ativo", True)]
    elif filtro_status == "Só inativos":
        forn_filt = [f for f in fornecedores if not f.get("ativo", True)]
    else:
        forn_filt = fornecedores

    rows = []
    for f in forn_filt:
        rows.append({
            "ID": f["id"],
            "Nome": f["nome"],
            "CNPJ": f["cnpj"],
            "Categoria": f.get("categoria") or "—",
            "Local": f"{f.get('municipio') or ''}/{f.get('uf') or ''}".strip("/"),
            "NFs lançadas": contagem.get(f["id"], 0),
            "Total gasto": formatar_brl(valores.get(f["id"], 0)),
            "Ativo": "✅" if f.get("ativo", True) else "❌",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Total: **{len(forn_filt)}** fornecedor(es)")

    # ─── DETECÇÃO DE DUPLICADOS POR CNPJ ─────────────────────────
    fornecedores_ativos = [f for f in fornecedores if f.get("ativo", True)]
    _bloco_detectar_duplicados(fornecedores_ativos, contagem, valores)

    # ─── Bloco de unificar fornecedores (manual) ─────────────────
    _bloco_unificar_fornecedores(fornecedores_ativos, contagem, valores)

    # ─── Editar fornecedor ─────────────────────────
    st.markdown("---")
    st.markdown("### ✏️ Editar fornecedor")

    opcoes = {f"{f['nome']} — {f['cnpj']} (ID {f['id']})": f for f in forn_filt}
    if not opcoes:
        st.info("Sem fornecedores pra editar nesse filtro.")
        return

    escolha = st.selectbox(
        "Selecione o fornecedor pra editar",
        list(opcoes.keys()),
        key="fin_forn_sel_edit",
    )
    forn = opcoes[escolha]

    qtd_lanc = contagem.get(forn["id"], 0)
    if qtd_lanc > 0:
        st.info(
            f"ℹ️ Esse fornecedor tem **{qtd_lanc}** lançamento(s) já gravado(s). "
            "Mudanças no nome/categoria podem ser propagadas pra esses lançamentos."
        )

    # Formulário de edição
    col_n, col_cnpj = st.columns([2, 1])
    with col_n:
        novo_nome = st.text_input(
            "Nome / Razão Social *",
            value=forn["nome"],
            key=f"edit_nome_{forn['id']}",
        ).upper().strip()
    with col_cnpj:
        st.text_input(
            "CNPJ (não editável)",
            value=forn["cnpj"],
            disabled=True,
            key=f"edit_cnpj_{forn['id']}",
        )

    col_cat, col_mun, col_uf = st.columns([2, 2, 1])
    with col_cat:
        cat_atual = forn.get("categoria") or "OUTROS"
        try:
            cat_idx = CATEGORIAS_PADRAO.index(cat_atual)
        except ValueError:
            cat_idx = CATEGORIAS_PADRAO.index("OUTROS")
        nova_cat = st.selectbox(
            "Categoria *",
            CATEGORIAS_PADRAO,
            index=cat_idx,
            key=f"edit_cat_{forn['id']}",
        )
    with col_mun:
        novo_mun = st.text_input(
            "Município",
            value=forn.get("municipio") or "",
            key=f"edit_mun_{forn['id']}",
        )
    with col_uf:
        novo_uf = st.text_input(
            "UF",
            value=forn.get("uf") or "",
            max_chars=2,
            key=f"edit_uf_{forn['id']}",
        ).upper()

    novo_ativo = st.checkbox(
        "Ativo",
        value=forn.get("ativo", True),
        key=f"edit_ativo_{forn['id']}",
        help="Desativar não apaga lançamentos, só esconde nas listas de novo cadastro.",
    )

    # Detecta o que mudou
    mudou_nome = novo_nome != forn["nome"]
    mudou_cat = nova_cat != (forn.get("categoria") or "OUTROS")

    propagar_nome = False
    propagar_cat = False
    if qtd_lanc > 0 and (mudou_nome or mudou_cat):
        st.markdown("##### Propagar pras NFs já gravadas?")
        col_p1, col_p2 = st.columns(2)
        if mudou_nome:
            with col_p1:
                propagar_nome = st.checkbox(
                    f"📝 Atualizar nome em {qtd_lanc} lançamento(s)",
                    value=True,
                    key=f"prop_nome_{forn['id']}",
                )
        if mudou_cat:
            with col_p2:
                propagar_cat = st.checkbox(
                    f"🏷️ Atualizar categoria em {qtd_lanc} lançamento(s)",
                    value=True,
                    key=f"prop_cat_{forn['id']}",
                )

    # Validação
    erros = []
    if not novo_nome or len(novo_nome) < 3:
        erros.append("Nome é obrigatório (mínimo 3 caracteres)")

    if erros:
        st.warning("Corrija antes de salvar:\n\n" + "\n".join(f"- {e}" for e in erros))
        return

    if st.button(
        "💾 Salvar alterações",
        type="primary",
        use_container_width=True,
        key=f"btn_salvar_forn_{forn['id']}",
    ):
        try:
            _atualizar_fornecedor_completo(
                forn_id=forn["id"],
                nome=novo_nome,
                categoria=nova_cat,
                municipio=novo_mun,
                uf=novo_uf,
                ativo=novo_ativo,
            )

            partes = ["✅ Cadastro atualizado!"]
            if propagar_nome:
                n = _propagar_nome_para_gastos(forn["id"], novo_nome)
                partes.append(f"- Nome atualizado em {n} lançamento(s)")
            if propagar_cat:
                n = _propagar_categoria_para_gastos(forn["id"], nova_cat)
                partes.append(f"- Categoria atualizada em {n} lançamento(s)")

            st.session_state["fin_forn_msg"] = {
                "tipo": "sucesso",
                "texto": "\n".join(partes),
            }
            st.toast("✅ Salvo!", icon="✅")
            st.rerun()
        except Exception as e:
            st.session_state["fin_forn_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao salvar: {type(e).__name__}: {e}",
            }
            st.rerun()


def _unificar_fornecedores(id_origem: int, id_destino: int) -> dict:
    """
    Move todos os lançamentos do fornecedor origem pro fornecedor destino,
    depois desativa o origem.

    Retorna estatísticas: quantos lançamentos foram movidos.
    """
    sb = obter_conexao()

    # Busca dados do destino (pra usar nome/categoria como snapshot nos lançamentos)
    destino_res = sb.table("fornecedor_financeiro").select("*").eq("id", id_destino).limit(1).execute()
    if not destino_res.data:
        raise ValueError(f"Fornecedor destino (ID {id_destino}) não encontrado.")
    destino = destino_res.data[0]

    # Move todos os lançamentos do origem → destino
    # Atualiza fornecedor_id, cnpj_fornecedor, nome_fornecedor e categoria
    upd = (sb.table("dados_financeiro_gasto")
           .update({
               "fornecedor_id": id_destino,
               "cnpj_fornecedor": destino["cnpj"],
               "nome_fornecedor": destino["nome"],
               "categoria": destino.get("categoria"),
           })
           .eq("fornecedor_id", id_origem)
           .execute())

    movidos = len(upd.data) if upd.data else 0

    # Desativa o fornecedor origem (não apaga pra não perder histórico)
    sb.table("fornecedor_financeiro").update({"ativo": False}).eq("id", id_origem).execute()

    return {"movidos": movidos}


def _bloco_unificar_fornecedores(fornecedores_ativos: list, contagem: dict, valores: dict):
    """Bloco da UI pra unificar 2 fornecedores num só."""
    import streamlit as st

    st.markdown("---")
    st.markdown("### 🔗 Unificar fornecedores")
    st.caption(
        "Usado quando um fornecedor virou outro (ex: empresa comprada, mudou CNPJ). "
        "Move TODOS os lançamentos do fornecedor **ORIGEM** pro **DESTINO**, "
        "depois desativa o origem. O cadastro origem fica inativo mas não é apagado."
    )

    if len(fornecedores_ativos) < 2:
        st.info("Precisa ter pelo menos 2 fornecedores ativos pra unificar.")
        return

    opcoes_origem = {
        f"{f['nome']} — {f['cnpj']} "
        f"({contagem.get(f['id'], 0)} NF · {formatar_brl(valores.get(f['id'], 0))})": f
        for f in fornecedores_ativos
    }

    col_o, col_d = st.columns(2)
    with col_o:
        st.markdown("**🔵 ORIGEM** (será desativado)")
        sel_origem = st.selectbox(
            "Fornecedor a ser absorvido",
            list(opcoes_origem.keys()),
            key="fin_unif_origem",
        )
        forn_origem = opcoes_origem[sel_origem]

    with col_d:
        st.markdown("**🟢 DESTINO** (vai receber os lançamentos)")
        opcoes_destino = {
            k: v for k, v in opcoes_origem.items()
            if v["id"] != forn_origem["id"]
        }
        sel_destino = st.selectbox(
            "Fornecedor que vai absorver",
            list(opcoes_destino.keys()),
            key="fin_unif_destino",
        )
        forn_destino = opcoes_destino[sel_destino]

    qtd_origem = contagem.get(forn_origem["id"], 0)
    valor_origem = valores.get(forn_origem["id"], 0)

    if qtd_origem == 0:
        st.warning(
            f"⚠️ **{forn_origem['nome']}** não tem lançamentos pra mover. "
            f"Você pode só desativar ele direto editando ali em cima."
        )
        return

    st.markdown("##### 📋 Resumo da operação")
    st.markdown(
        f"""<div style='background:#FFF3CD; border-left:4px solid #FFC107;
        padding:14px; border-radius:6px;'>
        <b>O que vai acontecer:</b><br>
        - <b>{qtd_origem}</b> lançamento(s) de <b>{forn_origem['nome']}</b>
          ({formatar_brl(valor_origem)}) serão movidos pra <b>{forn_destino['nome']}</b><br>
        - Nos lançamentos, o nome do fornecedor será atualizado pra <b>{forn_destino['nome']}</b><br>
        - O CNPJ snapshot dos lançamentos vai mudar pra <b>{forn_destino['cnpj']}</b><br>
        - A categoria será atualizada pra <b>{forn_destino.get('categoria') or 'OUTROS'}</b><br>
        - <b>{forn_origem['nome']}</b> será marcado como <b>inativo</b> (não é apagado)
        </div>""",
        unsafe_allow_html=True,
    )

    # Confirmação por texto
    confirma_txt = st.text_input(
        f"Pra confirmar, digite **UNIFICAR** no campo abaixo:",
        key="fin_unif_conf",
        placeholder="UNIFICAR",
    )

    confirma_ok = confirma_txt.strip().upper() == "UNIFICAR"

    if st.button(
        f"🔗 Unificar {forn_origem['nome']} → {forn_destino['nome']}",
        type="primary",
        disabled=not confirma_ok,
        use_container_width=True,
        key="btn_unificar_forn",
    ):
        try:
            res = _unificar_fornecedores(forn_origem["id"], forn_destino["id"])
            st.session_state["fin_forn_msg"] = {
                "tipo": "sucesso",
                "texto": (
                    f"✅ Unificação concluída!\n"
                    f"- **{res['movidos']}** lançamento(s) movido(s) de "
                    f"**{forn_origem['nome']}** pra **{forn_destino['nome']}**\n"
                    f"- **{forn_origem['nome']}** foi desativado"
                ),
            }
            st.toast("✅ Unificado!", icon="✅")
            st.rerun()
        except Exception as e:
            st.session_state["fin_forn_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao unificar: {type(e).__name__}: {e}",
            }
            st.rerun()


def _bloco_detectar_duplicados(fornecedores_ativos: list, contagem: dict, valores: dict):
    """
    Bloco da UI pra detectar cadastros duplicados pelo MESMO CNPJ.

    Lógica segura:
      - Agrupa fornecedores por CNPJ
      - Mostra grupos com 2+ cadastros
      - Sugere DESTINO = o que tem MAIS NFs lançadas (preserva histórico maior)
      - Usuário confirma cada unificação individualmente
    """
    import streamlit as st

    st.markdown("---")
    st.markdown("### 🔍 Detectar duplicados por CNPJ")
    st.caption(
        "Lista cadastros que têm o **mesmo CNPJ** (= mesma empresa). "
        "Pra cada par, sugere qual manter (o que tem mais NFs lançadas) e você confirma 1 por 1. "
        "**Nada é unificado automaticamente** — você decide cada caso."
    )

    if len(fornecedores_ativos) < 2:
        st.info("Precisa ter pelo menos 2 fornecedores ativos pra checar duplicados.")
        return

    # Agrupa por CNPJ
    por_cnpj = {}
    for f in fornecedores_ativos:
        cnpj = f.get("cnpj", "").strip()
        if not cnpj:
            continue
        por_cnpj.setdefault(cnpj, []).append(f)

    # Filtra grupos com 2+ cadastros
    duplicados = {cnpj: lst for cnpj, lst in por_cnpj.items() if len(lst) >= 2}

    if not duplicados:
        st.success("✅ Nenhum CNPJ duplicado detectado entre os fornecedores ativos.")
        return

    st.warning(
        f"⚠️ Encontrei **{len(duplicados)}** CNPJ(s) com mais de um cadastro. "
        f"Revise cada caso abaixo:"
    )

    for cnpj, grupo in duplicados.items():
        # Ordena: o que tem MAIS NFs vai como sugestão de destino
        grupo_ord = sorted(
            grupo,
            key=lambda f: (contagem.get(f["id"], 0), valores.get(f["id"], 0)),
            reverse=True,
        )
        destino_sugerido = grupo_ord[0]
        origens_sugeridas = grupo_ord[1:]

        # Resumo dos cadastros
        linhas_info = []
        for f in grupo_ord:
            qtd_nf = contagem.get(f["id"], 0)
            total = valores.get(f["id"], 0)
            marcador = "🟢 SUGERIDO: MANTER" if f["id"] == destino_sugerido["id"] else "🔴 SUGERIDO: ABSORVER"
            linhas_info.append(
                f"- **ID {f['id']}**: `{f['nome']}` — {qtd_nf} NF · {formatar_brl(total)} — {marcador}"
            )

        with st.expander(f"🔁 CNPJ **{cnpj}** ({len(grupo)} cadastros)", expanded=True):
            st.markdown("\n".join(linhas_info))

            st.markdown("##### Confirmar quem mantém e quem absorve:")

            opcoes_lista = {
                f"ID {f['id']} — {f['nome']} ({contagem.get(f['id'], 0)} NF, "
                f"{formatar_brl(valores.get(f['id'], 0))})": f
                for f in grupo_ord
            }

            col_d, col_o = st.columns(2)
            with col_d:
                st.markdown("**🟢 MANTER** (destino)")
                # Default: o sugerido
                opcoes_destino_keys = list(opcoes_lista.keys())
                idx_destino_sug = next(
                    (i for i, k in enumerate(opcoes_destino_keys)
                     if opcoes_lista[k]["id"] == destino_sugerido["id"]),
                    0,
                )
                sel_d = st.selectbox(
                    "Esse cadastro vai receber tudo",
                    opcoes_destino_keys,
                    index=idx_destino_sug,
                    key=f"dup_dest_{cnpj}",
                )
                forn_destino = opcoes_lista[sel_d]

            with col_o:
                st.markdown("**🔴 ABSORVER** (origem — vai ser desativado)")
                # Default: tudo menos o destino
                opcoes_origem_keys = [
                    k for k in opcoes_lista
                    if opcoes_lista[k]["id"] != forn_destino["id"]
                ]
                default_origens = opcoes_origem_keys  # marca todos por padrão
                sel_origens = st.multiselect(
                    "Esses cadastros serão absorvidos pelo destino",
                    opcoes_origem_keys,
                    default=default_origens,
                    key=f"dup_orig_{cnpj}",
                )
                forn_origens = [opcoes_lista[k] for k in sel_origens]

            if not forn_origens:
                st.info("Selecione pelo menos 1 cadastro pra absorver.")
                continue

            # Resumo da operação
            total_nfs_a_mover = sum(contagem.get(f["id"], 0) for f in forn_origens)
            total_valor_a_mover = sum(valores.get(f["id"], 0) for f in forn_origens)

            st.markdown(
                f"""<div style='background:#FFF3CD; border-left:4px solid #FFC107;
                padding:12px; border-radius:6px; margin-top:8px;'>
                <b>Resumo:</b><br>
                - <b>{total_nfs_a_mover}</b> NF(s) ({formatar_brl(total_valor_a_mover)})
                serão movidas pra <b>{forn_destino['nome']}</b><br>
                - <b>{len(forn_origens)}</b> cadastro(s) serão desativado(s)<br>
                </div>""",
                unsafe_allow_html=True,
            )

            if st.button(
                f"🔗 Unificar esses {len(forn_origens)} cadastro(s) → {forn_destino['nome'][:40]}",
                type="primary",
                use_container_width=True,
                key=f"dup_btn_{cnpj}",
            ):
                try:
                    total_movidos = 0
                    for forn_origem in forn_origens:
                        res = _unificar_fornecedores(forn_origem["id"], forn_destino["id"])
                        total_movidos += res["movidos"]

                    st.session_state["fin_forn_msg"] = {
                        "tipo": "sucesso",
                        "texto": (
                            f"✅ CNPJ **{cnpj}** unificado!\n"
                            f"- **{total_movidos}** lançamento(s) movido(s)\n"
                            f"- **{len(forn_origens)}** cadastro(s) desativado(s)\n"
                            f"- Mantido: **{forn_destino['nome']}**"
                        ),
                    }
                    st.toast("✅ Unificado!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.session_state["fin_forn_msg"] = {
                        "tipo": "erro",
                        "texto": f"❌ Erro ao unificar: {type(e).__name__}: {e}",
                    }
                    st.rerun()
