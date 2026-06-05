"""
Tela Financeiro · Upload de NFs

Fluxo:
  1. Usuário escolhe mês/ano de competência
  2. Faz upload de N PDFs de NF
  3. Sistema lê cada PDF:
     - Extrai CNPJ do prestador
     - Se CNPJ já cadastrado → reusa o fornecedor (com categoria já definida)
     - Se CNPJ novo → cadastra automaticamente (categoria sugerida pela
       descrição da NF)
  4. Mostra prévia em tabela com TUDO que vai gravar
  5. Botão "Gravar" → cria lançamentos no banco
"""
from __future__ import annotations

import datetime
import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from src.banco import repo_financeiro
from src.servicos.parser_nf import ler_nf_pdf
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE


def renderizar_fin_upload(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>💼 Financeiro · Upload de NFs</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Suba uma ou várias Notas Fiscais (PDF). O sistema lê cada NF e "
        "cadastra fornecedores novos automaticamente."
    )

    # Mensagem persistente do último processamento
    msg = st.session_state.pop("fin_upload_msg", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    # ─── Seletor de mês/ano ─────────────────────────
    st.markdown("### 1️⃣ Selecione o mês de competência")
    col_mes, col_ano = st.columns(2)
    with col_mes:
        meses = list(range(1, 13))
        mes_idx = datetime.date.today().month - 1
        mes = st.selectbox(
            "Mês",
            meses,
            index=mes_idx,
            format_func=lambda m: nome_mes(f"2026-{m:02d}"),
            key="fin_up_mes",
        )
    with col_ano:
        ano_atual = datetime.date.today().year
        ano = st.selectbox(
            "Ano",
            list(range(ano_atual - 2, ano_atual + 2)),
            index=2,  # ano atual
            key="fin_up_ano",
        )

    mes_ano = f"{ano:04d}-{mes:02d}"
    st.info(f"📅 Competência selecionada: **{nome_mes(mes_ano)} de {ano}** (`{mes_ano}`)")

    # ─── Upload ─────────────────────────
    st.markdown("### 2️⃣ Suba as NFs (PDFs)")

    uploader_key = st.session_state.get("fin_uploader_key", "fin_uploader_v1")
    arquivos = st.file_uploader(
        "Arraste ou clique pra escolher os PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=uploader_key,
        help="Aceita várias NFs de uma vez. Cada arquivo deve ser uma NF eletrônica em PDF.",
    )

    if not arquivos:
        st.markdown(
            f"<div style='color:#666; padding:20px; text-align:center;'>"
            f"📁 Nenhum arquivo selecionado ainda.</div>",
            unsafe_allow_html=True,
        )
        return

    # Hash combinado dos arquivos (anti-reprocessamento)
    h = hashlib.md5()
    for a in arquivos:
        h.update(a.getvalue())
    hash_combinado = h.hexdigest()

    # Se já foi processado nessa sessão, mostra aviso MAS deixa reprocessar
    if st.session_state.get("fin_hash_processado") == hash_combinado:
        st.warning(
            "ℹ️ **Esses arquivos já foram processados nessa sessão.** "
            "Se você excluiu os lançamentos e quer subir de novo, clique no botão abaixo."
        )
        if st.button(
            "🔄 Quero reprocessar mesmo assim",
            type="primary",
            key="fin_btn_reprocessar",
        ):
            # Limpa a trava e força rerun pra continuar o fluxo
            st.session_state.pop("fin_hash_processado", None)
            st.rerun()
        return

    # ─── Processa cada PDF e monta prévia ─────────────────────────
    st.markdown("### 3️⃣ Prévia dos lançamentos")

    linhas_previa = []
    avisos = []

    for arq in arquivos:
        try:
            nf = ler_nf_pdf(arq, arq.name)

            # Decide se é novo cadastro
            existente = (
                repo_financeiro.buscar_fornecedor_por_cnpj(nf.cnpj_prestador)
                if nf.cnpj_prestador else None
            )
            categoria_atual = (
                existente["categoria"] if existente
                else (repo_financeiro.sugerir_categoria(nf.descricao_servico, nf.nome_prestador) or "OUTROS")
            )

            # Verifica se já foi lançado antes
            ja_lancado = False
            if nf.cnpj_prestador and nf.numero_nf:
                ja_lancado = repo_financeiro.gasto_ja_lancado(
                    nf.cnpj_prestador, nf.numero_nf, nf.valor_total,
                )

            status_emoji = "♻️ Já existe" if existente else "🆕 Novo cadastro"
            if ja_lancado:
                status_emoji = "⚠️ Já lançada"

            linhas_previa.append({
                "Arquivo": arq.name,
                "Status": status_emoji,
                "CNPJ": nf.cnpj_prestador or "—",
                "Fornecedor": nf.nome_prestador,
                "Categoria": categoria_atual,
                "Empresa LLE": nf.empresa_lle or "—",
                "NF nº": nf.numero_nf or "—",
                "Data": nf.data_emissao.strftime("%d/%m/%Y") if nf.data_emissao else "—",
                "Competência detectada": nf.competencia_mes_ano or "—",
                "Valor": formatar_brl(nf.valor_total),
                "_valor_num": nf.valor_total,
                "_ja_lancado": ja_lancado,
                "_aviso": nf.aviso,
                "_existente": existente,
                "_nf": nf,
            })

            if nf.aviso:
                avisos.append(f"📄 **{arq.name}**: {nf.aviso}")
        except Exception as e:
            avisos.append(f"📄 **{arq.name}**: ❌ erro ao ler PDF: {e}")
            linhas_previa.append({
                "Arquivo": arq.name,
                "Status": "❌ Erro",
                "CNPJ": "—",
                "Fornecedor": "ERRO",
                "Categoria": "—",
                "Empresa LLE": "—",
                "NF nº": "—",
                "Data": "—",
                "Competência detectada": "—",
                "Valor": "—",
                "_valor_num": 0,
                "_ja_lancado": False,
                "_aviso": str(e),
                "_existente": None,
                "_nf": None,
            })

    # Mostra a tabela (sem colunas internas)
    df_previa = pd.DataFrame(linhas_previa)
    df_mostra = df_previa.drop(
        columns=[c for c in df_previa.columns if c.startswith("_")]
    )
    st.dataframe(df_mostra, use_container_width=True, hide_index=True)

    # Avisos detalhados (se houver)
    if avisos:
        with st.expander(f"⚠️ {len(avisos)} aviso(s) detectado(s)"):
            for a in avisos:
                st.markdown(f"- {a}")

    # Totalizadores
    total = sum(l["_valor_num"] for l in linhas_previa if not l["_ja_lancado"])
    qtd_validas = sum(
        1 for l in linhas_previa
        if l["_nf"] and l["_nf"].cnpj_prestador and l["_valor_num"] > 0 and not l["_ja_lancado"]
    )
    qtd_novos = sum(1 for l in linhas_previa if l["_nf"] and not l["_existente"] and not l["_ja_lancado"])
    qtd_ja_lancadas = sum(1 for l in linhas_previa if l["_ja_lancado"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total a lançar", formatar_brl(total))
    c2.metric("NFs válidas", qtd_validas)
    c3.metric("Fornecedores novos", qtd_novos)
    c4.metric("Já lançadas (ignoradas)", qtd_ja_lancadas)

    # ─── Botão de gravar ─────────────────────────
    st.markdown("---")

    if qtd_validas == 0:
        st.warning(
            "⚠️ Nenhuma NF válida pra gravar. Verifique os avisos acima ou "
            "remova arquivos com erro e suba outros."
        )
        return

    aviso_competencia = ""
    competencias_diferentes = set(
        l["_nf"].competencia_mes_ano for l in linhas_previa
        if l["_nf"] and l["_nf"].competencia_mes_ano and l["_nf"].competencia_mes_ano != mes_ano
    )
    if competencias_diferentes:
        aviso_competencia = (
            f"\n\n⚠️ Atenção: algumas NFs têm competência diferente "
            f"({', '.join(competencias_diferentes)}) mas serão gravadas em "
            f"**{nome_mes(mes_ano)}/{ano}** porque foi o que você selecionou."
        )
        st.warning(aviso_competencia)

    if st.button(
        f"💾 Gravar {qtd_validas} lançamento(s) em {nome_mes(mes_ano)}/{ano}",
        type="primary",
        use_container_width=True,
        key="btn_gravar_fin",
    ):
        try:
            criados = 0
            forn_novos = 0
            for l in linhas_previa:
                nf = l["_nf"]
                if not nf or not nf.cnpj_prestador or nf.valor_total <= 0:
                    continue
                if l["_ja_lancado"]:
                    continue

                # Obtem ou cria fornecedor
                existente_check = repo_financeiro.buscar_fornecedor_por_cnpj(nf.cnpj_prestador)
                if not existente_check:
                    forn_novos += 1
                forn = repo_financeiro.obter_ou_criar_fornecedor(
                    cnpj=nf.cnpj_prestador,
                    nome=nf.nome_prestador,
                    descricao_servico=nf.descricao_servico,
                    municipio=nf.municipio_prestador,
                    uf=nf.uf_prestador,
                    criado_por_id=usuario.id,
                )

                # Cria lançamento
                repo_financeiro.criar_gasto(
                    mes_ano=mes_ano,
                    fornecedor_id=forn["id"],
                    cnpj_fornecedor=nf.cnpj_prestador,
                    nome_fornecedor=nf.nome_prestador,
                    categoria=forn.get("categoria"),
                    cnpj_pagador=nf.cnpj_tomador,
                    empresa_lle=nf.empresa_lle,
                    numero_nf=nf.numero_nf,
                    data_emissao=nf.data_emissao,
                    valor=nf.valor_total,
                    descricao_servico=nf.descricao_servico,
                    nome_arquivo_pdf=l["Arquivo"],
                    criado_por_id=usuario.id,
                )
                criados += 1

            # Atualiza estado e força limpeza do uploader
            st.session_state["fin_hash_processado"] = hash_combinado
            import time
            st.session_state["fin_uploader_key"] = f"fin_uploader_{int(time.time())}"

            st.session_state["fin_upload_msg"] = {
                "tipo": "sucesso",
                "texto": (
                    f"✅ **{criados}** lançamento(s) gravado(s) em "
                    f"**{nome_mes(mes_ano)}/{ano}**.\n\n"
                    f"- 🆕 {forn_novos} fornecedor(es) novo(s) cadastrado(s) automaticamente\n"
                    f"- 💰 Total: {formatar_brl(total)}"
                ),
            }
            st.toast("✅ Lançamentos gravados!", icon="✅")
            st.rerun()
        except Exception as e:
            import traceback
            st.session_state["fin_upload_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao gravar: {type(e).__name__}: {e}",
            }
            st.session_state["fin_upload_erros_detalhe"] = traceback.format_exc()
            st.rerun()
