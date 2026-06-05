"""
Tela Financeiro · Cadastro Manual de Gasto

Pra casos onde o PDF não pode ser lido automaticamente:
  - Boletos imagem/scan (Bradesco Net Empresa)
  - Despesas sem NF (aluguel, salários, taxas)
  - Formatos de NF que o parser não reconhece

Fluxo simples e direto:
  1. Preenche os dados (mês, fornecedor, valor, etc)
  2. Sistema verifica o CNPJ:
     - Se já existe → reusa o cadastro existente (preenche sugestões)
     - Se não existe → cadastra automaticamente com o que você digitou
  3. Grava o lançamento
"""
from __future__ import annotations

import datetime
import re

import streamlit as st

from src.banco import repo_financeiro
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO


EMPRESAS_LLE = ["PISA", "KING", "TRIO", "OUTRO"]

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
        "Cadastre um gasto digitando os dados. Se o CNPJ ainda não estiver "
        "cadastrado, o fornecedor é criado automaticamente com o que você "
        "digitar aqui."
    )

    msg = st.session_state.pop("fin_manual_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    # ─── Bloco 1: Competência ─────────────────────────
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

    # ─── Bloco 2: Fornecedor ─────────────────────────
    st.markdown("### 2️⃣ Fornecedor")
    st.caption(
        "Digite o CNPJ. Se já estiver cadastrado, os campos abaixo vêm preenchidos. "
        "Senão, preencha tudo — o fornecedor é cadastrado automaticamente ao gravar."
    )

    col_cnpj, col_nome = st.columns([1, 2])
    with col_cnpj:
        cnpj_raw = st.text_input(
            "CNPJ *",
            key="fin_man_cnpj",
            placeholder="00.000.000/0000-00",
        )
        cnpj_forn = _formatar_cnpj(cnpj_raw) if cnpj_raw else ""
        if cnpj_raw and cnpj_forn != cnpj_raw.strip():
            st.caption(f"📌 Formatado: `{cnpj_forn}`")

    # Verifica se já existe pra preencher sugestões (mas SEM travar nada)
    forn_existente = None
    sugestao_nome = ""
    sugestao_categoria = "OUTROS"
    sugestao_municipio = ""
    sugestao_uf = ""

    if cnpj_forn and len(re.sub(r"\D", "", cnpj_forn)) == 14:
        forn_existente = repo_financeiro.buscar_fornecedor_por_cnpj(cnpj_forn)
        if forn_existente:
            sugestao_nome = forn_existente["nome"]
            sugestao_categoria = forn_existente.get("categoria") or "OUTROS"
            sugestao_municipio = forn_existente.get("municipio") or ""
            sugestao_uf = forn_existente.get("uf") or ""

    if forn_existente:
        st.success(
            f"✓ Esse CNPJ já está cadastrado como **{forn_existente['nome']}**. "
            f"Os campos abaixo vieram do cadastro existente — você pode mudar se quiser."
        )

    with col_nome:
        nome_forn = st.text_input(
            "Nome / Razão Social *",
            value=sugestao_nome,
            key="fin_man_nome",
            placeholder="Ex: ABC SERVIÇOS LTDA",
        ).upper().strip()

    col_cat, col_mun, col_uf = st.columns([2, 2, 1])
    with col_cat:
        try:
            cat_idx = CATEGORIAS_PADRAO.index(sugestao_categoria)
        except ValueError:
            cat_idx = CATEGORIAS_PADRAO.index("OUTROS")
        categoria = st.selectbox(
            "Categoria *",
            CATEGORIAS_PADRAO,
            index=cat_idx,
            key="fin_man_cat",
        )
    with col_mun:
        municipio = st.text_input(
            "Município",
            value=sugestao_municipio,
            key="fin_man_mun",
        )
    with col_uf:
        uf = st.text_input(
            "UF",
            value=sugestao_uf,
            max_chars=2,
            key="fin_man_uf",
        ).upper()

    # ─── Bloco 3: Dados do gasto ─────────────────────────
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

    # ─── Validação ─────────────────────────
    st.markdown("---")

    cnpj_digs = re.sub(r"\D", "", cnpj_forn or "")
    erros = []
    if not cnpj_forn or len(cnpj_digs) != 14:
        erros.append("CNPJ deve ter 14 dígitos")
    if not nome_forn or len(nome_forn) < 3:
        erros.append("Nome / Razão Social é obrigatório")
    if valor <= 0:
        erros.append("Valor deve ser maior que zero")

    if erros:
        st.warning(
            "Preencha os campos obrigatórios antes de gravar:\n\n"
            + "\n".join(f"- {e}" for e in erros)
        )
        return

    # ─── Decisão sobre duplicação ─────────────────────────
    avaliacao = {"acao": "criar"}
    if cnpj_forn and numero_nf:
        avaliacao = repo_financeiro.avaliar_lancamento(cnpj_forn, numero_nf, valor)

    eh_atualizacao = avaliacao["acao"] == "atualizar_valor"
    eh_duplicado = avaliacao["acao"] == "duplicado_exato"

    if eh_duplicado:
        st.error(
            "⛔ **NF duplicada:** já existe um lançamento com **mesmo CNPJ + nº NF + mesmo valor**. "
            "Não vou cadastrar de novo. Se for um lançamento diferente, mude algo (ex: número da NF)."
        )
    elif eh_atualizacao:
        valor_antigo = float(avaliacao["gasto_existente"].get("valor", 0))
        st.warning(
            f"🔄 Já existe um lançamento com **mesma NF nº {numero_nf}** "
            f"desse fornecedor, com valor **{formatar_brl(valor_antigo)}**. "
            f"Vou **ATUALIZAR** esse lançamento pro novo valor **{formatar_brl(valor)}** ao salvar."
        )

    # ─── Resumo + gravar ─────────────────────────
    st.markdown("### 4️⃣ Confirmar")
    status_fornecedor = (
        "🔄 Vai reusar cadastro existente"
        if forn_existente
        else "🆕 Vai cadastrar fornecedor automaticamente"
    )
    acao_resumo = (
        "🔄 ATUALIZAR lançamento existente"
        if eh_atualizacao
        else "🆕 Criar novo lançamento"
    )
    st.markdown(
        f"""<div style='background:{AZUL_ESCURO}11; border-left:4px solid {AZUL_ESCURO};
        padding:14px; border-radius:6px;'>
        <b>Resumo:</b><br>
        - Ação: <b>{acao_resumo}</b><br>
        - Competência: <b>{nome_mes(mes_ano)}/{ano}</b><br>
        - Fornecedor: <b>{nome_forn}</b> ({cnpj_forn}) — {status_fornecedor}<br>
        - Categoria: <b>{categoria}</b><br>
        - Empresa LLE: <b>{empresa_lle}</b><br>
        - NF nº: <b>{numero_nf or '—'}</b><br>
        - Data: <b>{data_emissao.strftime('%d/%m/%Y')}</b><br>
        - Valor: <b>{formatar_brl(valor)}</b>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("")

    label_botao = (
        f"🔄 Atualizar lançamento (mudar valor pra {formatar_brl(valor)})"
        if eh_atualizacao
        else f"💾 Gravar lançamento de {formatar_brl(valor)}"
    )

    if st.button(
        label_botao,
        type="primary",
        use_container_width=True,
        key="btn_gravar_fin_manual",
        disabled=eh_duplicado,
    ):
        try:
            forn = repo_financeiro.obter_ou_criar_fornecedor(
                cnpj=cnpj_forn,
                nome=nome_forn,
                descricao_servico=descricao,
                municipio=municipio or None,
                uf=uf or None,
                criado_por_id=usuario.id,
            )

            # Atualiza categoria se diferente do cadastro
            if forn.get("categoria") != categoria:
                try:
                    repo_financeiro.atualizar_categoria_fornecedor(forn["id"], categoria)
                except Exception:
                    pass

            if eh_atualizacao:
                # Atualiza o lançamento existente
                gasto_id = avaliacao["gasto_existente"]["id"]
                repo_financeiro.atualizar_gasto(gasto_id, {
                    "valor": float(valor),
                    "data_emissao": data_emissao.isoformat(),
                    "empresa_lle": empresa_lle if empresa_lle != "OUTRO" else None,
                    "categoria": categoria,
                    "descricao_servico": descricao or None,
                    "mes_ano": mes_ano,
                    "nome_fornecedor": nome_forn,
                })
                msg_texto = (
                    f"🔄 Lançamento ATUALIZADO em **{nome_mes(mes_ano)}/{ano}**.\n\n"
                    f"- NF nº {numero_nf} da {nome_forn}\n"
                    f"- Novo valor: {formatar_brl(valor)}"
                )
            else:
                # Cria novo lançamento
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
                msg_texto = (
                    f"✅ Lançamento gravado em **{nome_mes(mes_ano)}/{ano}**.\n\n"
                    f"- Fornecedor: {nome_forn} "
                    f"({'reusado' if forn_existente else 'cadastrado agora'})\n"
                    f"- Valor: {formatar_brl(valor)}"
                )

            st.session_state["fin_manual_msg"] = {
                "tipo": "sucesso",
                "texto": msg_texto,
            }
            st.toast("✅ Gravado!", icon="✅")

            # Limpa o formulário
            for k in [
                "fin_man_cnpj", "fin_man_nome", "fin_man_nf",
                "fin_man_valor", "fin_man_desc", "fin_man_mun", "fin_man_uf",
            ]:
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
