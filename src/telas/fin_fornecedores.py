"""
Tela Financeiro · Cadastro de Fornecedores

CRUD de fornecedores:
  - Lista todos cadastrados
  - Permite editar nome, categoria, município, UF
  - Permite ativar/desativar
  - Mostra quantas NFs cada fornecedor já teve lançadas
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
    Atualiza o nome_fornecedor (snapshot) em TODOS os lançamentos
    desse fornecedor. Retorna quantos foram atualizados.
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

    # Carrega fornecedores
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

    # Filtro: ativos / inativos / todos
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
        help="Desativar não apaga os lançamentos existentes, só esconde nas listas de cadastro.",
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
