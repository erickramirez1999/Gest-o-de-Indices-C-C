"""
Tela Financeiro · Cadastro Manual de Gasto

Pra casos onde o PDF não pode ser lido automaticamente:
  - Boletos imagem/scan (Bradesco Net Empresa)
  - Despesas sem NF (aluguel, salários, taxas)
  - Formatos de NF que o parser não reconhece

O usuário preenche tudo no formulário. Se o CNPJ informado já está
cadastrado, o nome e categoria são preenchidos automaticamente.
"""
from __future__ import annotations

import datetime
import re

import streamlit as st

from src.banco import repo_financeiro
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO


# Empresas LLE conhecidas (mesma lista do parser)
EMPRESAS_LLE = ["PISA", "KING", "TRIO", "OUTRO"]

# Categorias disponíveis (mesmas heurísticas do parser)
CATEGORIAS_PADRAO = [
    "PROTESTO", "SOFTWARE", "HOSPEDAGEM", "CONTABIL", "JURÍDICO",
    "MARKETING", "CONSULTORIA", "TRANSPORTE", "TELECOM", "ALUGUEL",
    "ENERGIA", "ÁGUA", "LIMPEZA", "MATERIAL", "BANCO",
    "SALÁRIOS", "IMPOSTOS", "OUTROS",
]


def _formatar_cnpj(s: str) -> str:
    """'05953543000147' -> '05.953.543/0001-47'"""
    if not s:
        return ""
    digs = re.sub(r"\D", "", s)
    if len(digs) != 14:
        return s.strip()
    return f"{digs[:2]}.{digs[2:5]}.{digs[5:8]}/{digs[8:12]}-{digs[12:14]}"


def renderizar_fin_manual(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>✍️ Financeiro · Cadastro Manual</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Cadastre um gasto digitando os dados. Use isso pra boletos sem NF "
        "eletrônica, despesas recorrentes (aluguel, salários) ou casos em "
        "que o upload PDF não reconheceu corretamente."
    )

    # Mensagem persistente
    msg = st.session_state.pop("fin_manual_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    # ─── Mês de competência ─────────────────────────
    st.markdown("### 1️⃣ Competência")
    col_mes, col_ano = st.columns(2)
    with col_mes:
        meses = list(range(1, 13))
        mes_idx = datetime.date.today().month - 1
        mes = st.selectbox(
            "Mês",
            meses,
            index=mes_idx,
            format_func=lambda m: nome_mes(f"2026-{m:02d}"),
            key="fin_man_mes",
        )
    with col_ano:
        ano_atual = datetime.date.today().year
        ano = st.selectbox(
            "Ano",
            list(range(ano_atual - 2, ano_atual + 2)),
            index=2,
            key="fin_man_ano",
        )

    mes_ano = f"{ano:04d}-{mes:02d}"

    # ─── Fornecedor ─────────────────────────
    st.markdown("### 2️⃣ Fornecedor")

    fornecedores = repo_financeiro.listar_fornecedores()

    modo_forn = st.radio(
        "Como informar o fornecedor?",
        ["🔍 Buscar cadastrado", "🆕 Cadastrar novo"],
        horizontal=True,
        key="fin_man_modo_forn",
    )

    cnpj_forn = ""
    nome_forn = ""
    categoria = "OUTROS"
    forn_existente = None
    municipio = ""
    uf = ""

    if modo_forn == "🔍 Buscar cadastrado":
        if not fornecedores:
            st.warning(
                "⚠️ Nenhum fornecedor cadastrado ainda. "
                "Use **🆕 Cadastrar novo** ou suba uma NF em PDF primeiro."
            )
        else:
            opcoes = {
                f"{f['nome']} — {f['cnpj']} ({f.get('categoria') or 'OUTROS'})": f
                for f in fornecedores
            }
            escolha = st.selectbox(
                "Selecione o fornecedor",
                list(opcoes.keys()),
                key="fin_man_forn_sel",
            )
            forn_existente = opcoes[escolha]
            cnpj_forn = forn_existente["cnpj"]
            nome_forn = forn_existente["nome"]
            categoria = forn_existente.get("categoria") or "OUTROS"
            municipio = forn_existente.get("municipio") or ""
            uf = forn_existente.get("uf") or ""

            col_i1, col_i2, col_i3 = st.columns(3)
            col_i1.metric("CNPJ", cnpj_forn)
            col_i2.metric("Categoria", categoria)
            col_i3.metric("Local", f"{municipio}/{uf}" if municipio else "—")
    else:
        # Cadastrar novo fornecedor
        col_cnpj, col_nome = st.columns([1, 2])
        with col_cnpj:
            cnpj_raw = st.text_input(
                "CNPJ * (só números ou formatado)",
                key="fin_man_cnpj",
                placeholder="00.000.000/0000-00",
            )
            cnpj_forn = _formatar_cnpj(cnpj_raw) if cnpj_raw else ""
            if cnpj_raw and cnpj_forn != cnpj_raw.strip():
                st.caption(f"Formatado: `{cnpj_forn}`")

        with col_nome:
            nome_forn = st.text_input(
                "Nome do fornecedor *",
                key="fin_man_nome",
                placeholder="Razão social",
            ).upper()

        # Se o CNPJ digitado já existe, avisa pra usar a busca
        if cnpj_forn and len(re.sub(r"\D", "", cnpj_forn)) == 14:
            existe = repo_financeiro.buscar_fornecedor_por_cnpj(cnpj_forn)
            if existe:
                st.info(
                    f"ℹ️ Esse CNPJ **já está cadastrado** como "
                    f"`{existe['nome']}` (categoria: {existe.get('categoria') or 'OUTROS'}). "
                    f"O lançamento vai usar esse cadastro existente."
                )
                forn_existente = existe
                nome_forn = existe["nome"]
                categoria = existe.get("categoria") or "OUTROS"
                municipio = existe.get("municipio") or ""
                uf = existe.get("uf") or ""

        col_cat, col_mun, col_uf = st.columns([2, 2, 1])
        with col_cat:
            categoria = st.selectbox(
                "Categoria *",
                CATEGORIAS_PADRAO,
                index=CATEGORIAS_PADRAO.index(categoria) if categoria in CATEGORIAS_PADRAO else len(CATEGORIAS_PADRAO) - 1,
                key="fin_man_cat",
                disabled=forn_existente is not None,
            )
        with col_mun:
            municipio = st.text_input("Município", value=municipio, key="fin_man_mun",
                                      disabled=forn_existente is not None)
        with col_uf:
            uf = st.text_input("UF", value=uf, max_chars=2, key="fin_man_uf",
                               disabled=forn_existente is not None).upper()

    # ─── Dados da nota/gasto ─────────────────────────
    st.markdown("### 3️⃣ Dados do gasto")

    col_emp, col_data = st.columns(2)
    with col_emp:
        empresa_lle = st.selectbox(
            "Empresa LLE pagadora *",
            EMPRESAS_LLE,
            key="fin_man_emp",
            help="Qual empresa do grupo LLE pagou esse gasto",
        )
    with col_data:
        data_emissao = st.date_input(
            "Data de emissão",
            value=datetime.date.today(),
            key="fin_man_data",
            format="DD/MM/YYYY",
        )

    col_nf, col_valor = st.columns(2)
    with col_nf:
        numero_nf = st.text_input(
            "Número da NF / documento",
            key="fin_man_nf",
            placeholder="Ex: 419, BOL-001, ou deixe vazio",
        )
    with col_valor:
        valor = st.number_input(
            "Valor (R$) *",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f",
            key="fin_man_valor",
        )

    descricao = st.text_area(
        "Descrição do serviço/gasto",
        key="fin_man_desc",
        placeholder="Ex: Manutenção mensal do sistema, Aluguel sede, etc",
        height=80,
    )

    # ─── Validação e gravar ─────────────────────────
    st.markdown("---")

    cnpj_digs = re.sub(r"\D", "", cnpj_forn or "")
    erros = []
    if not cnpj_forn or len(cnpj_digs) != 14:
        erros.append("CNPJ inválido (precisa ter 14 dígitos)")
    if not nome_forn or len(nome_forn) < 3:
        erros.append("Nome do fornecedor é obrigatório")
    if valor <= 0:
        erros.append("Valor deve ser maior que zero")

    if erros:
        st.warning("Preencha os campos obrigatórios antes de gravar:\n\n" + "\n".join(f"- {e}" for e in erros))
        return

    # Confere se a NF já foi lançada (anti-duplicação)
    ja_lancado = False
    if cnpj_forn and numero_nf:
        ja_lancado = repo_financeiro.gasto_ja_lancado(cnpj_forn, numero_nf, valor)
        if ja_lancado:
            st.warning(
                f"⚠️ Já existe um lançamento com **mesmo CNPJ + nº NF + valor**. "
                f"Se for o caso, mude algo (ex: valor ou nº da NF) pra distinguir."
            )

    # Mostra resumo
    st.markdown("### 4️⃣ Confirmar")
    st.markdown(
        f"""<div style='background:{AZUL_ESCURO}11; border-left:4px solid {AZUL_ESCURO};
        padding:14px; border-radius:6px;'>
        <b>Resumo do lançamento:</b><br>
        - Competência: <b>{nome_mes(mes_ano)}/{ano}</b><br>
        - Fornecedor: <b>{nome_forn}</b> ({cnpj_forn})<br>
        - Categoria: <b>{categoria}</b><br>
        - Empresa LLE: <b>{empresa_lle}</b><br>
        - NF nº: <b>{numero_nf or '—'}</b><br>
        - Data: <b>{data_emissao.strftime('%d/%m/%Y')}</b><br>
        - Valor: <b>{formatar_brl(valor)}</b>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("")

    if st.button(
        f"💾 Gravar lançamento de {formatar_brl(valor)}",
        type="primary",
        use_container_width=True,
        key="btn_gravar_fin_manual",
        disabled=ja_lancado,
    ):
        try:
            # Obtem ou cria fornecedor
            forn = repo_financeiro.obter_ou_criar_fornecedor(
                cnpj=cnpj_forn,
                nome=nome_forn,
                descricao_servico=descricao,
                municipio=municipio or None,
                uf=uf or None,
                criado_por_id=usuario.id,
            )

            # Se a categoria foi alterada manualmente (modo "cadastrar novo"),
            # garante que vai pra base com a categoria escolhida
            if not forn_existente and forn.get("categoria") != categoria:
                try:
                    repo_financeiro.atualizar_categoria_fornecedor(forn["id"], categoria)
                except Exception:
                    pass

            # Cria gasto
            repo_financeiro.criar_gasto(
                mes_ano=mes_ano,
                fornecedor_id=forn["id"],
                cnpj_fornecedor=cnpj_forn,
                nome_fornecedor=nome_forn,
                categoria=categoria,
                cnpj_pagador=None,
                empresa_lle=empresa_lle if empresa_lle != "OUTRO" else None,
                numero_nf=numero_nf or None,
                data_emissao=data_emissao,
                valor=float(valor),
                descricao_servico=descricao or None,
                nome_arquivo_pdf=None,
                criado_por_id=usuario.id,
            )

            st.session_state["fin_manual_msg"] = {
                "tipo": "sucesso",
                "texto": (
                    f"✅ Lançamento gravado em **{nome_mes(mes_ano)}/{ano}**.\n\n"
                    f"- Fornecedor: {nome_forn}\n"
                    f"- Valor: {formatar_brl(valor)}"
                ),
            }
            st.toast("✅ Gravado!", icon="✅")
            # Limpa o formulário forçando trocar as keys
            import time
            t = int(time.time())
            for k in ["fin_man_cnpj", "fin_man_nome", "fin_man_nf", "fin_man_valor", "fin_man_desc"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()
        except Exception as e:
            import traceback
            st.session_state["fin_manual_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao gravar: {type(e).__name__}: {e}",
            }
            st.session_state["fin_manual_erros_detalhe"] = traceback.format_exc()
            st.rerun()
