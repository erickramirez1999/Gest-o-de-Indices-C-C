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

    if st.session_state.get("fin_hash_processado") == hash_combinado:
        st.warning(
            "ℹ️ **Esses arquivos já foram processados nessa sessão.** "
            "Remova os arquivos (✕) e selecione outros."
        )
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

            # Avalia o que fazer com o lançamento (criar / atualizar valor / duplicado)
            avaliacao = {"acao": "criar"}
            if nf.cnpj_prestador and nf.numero_nf:
                avaliacao = repo_financeiro.avaliar_lancamento(
                    nf.cnpj_prestador, nf.numero_nf, nf.valor_total,
                )

            # Status visual baseado na avaliação
            if avaliacao["acao"] == "duplicado_exato":
                status_emoji = "⚠️ Já lançada (duplicada)"
            elif avaliacao["acao"] == "atualizar_valor":
                vlr_antigo = float(avaliacao["gasto_existente"].get("valor", 0))
                status_emoji = f"🔄 Vai atualizar valor (era {formatar_brl(vlr_antigo)})"
            elif existente:
                status_emoji = "♻️ Fornecedor já existe"
            else:
                status_emoji = "🆕 Novo cadastro"

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
                "_avaliacao": avaliacao,
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
                "_avaliacao": {"acao": "erro"},
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
    def _eh_para_gravar(l):
        """Vai pro banco se: criar OU atualizar valor."""
        acao = l.get("_avaliacao", {}).get("acao")
        return (
            acao in ("criar", "atualizar_valor")
            and l["_nf"]
            and l["_nf"].cnpj_prestador
            and l["_valor_num"] > 0
        )

    total = sum(l["_valor_num"] for l in linhas_previa if _eh_para_gravar(l))
    qtd_validas = sum(1 for l in linhas_previa if _eh_para_gravar(l))
    qtd_novos = sum(
        1 for l in linhas_previa
        if _eh_para_gravar(l) and not l["_existente"]
    )
    qtd_atualizar = sum(
        1 for l in linhas_previa
        if l.get("_avaliacao", {}).get("acao") == "atualizar_valor"
    )
    qtd_duplicadas = sum(
        1 for l in linhas_previa
        if l.get("_avaliacao", {}).get("acao") == "duplicado_exato"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total a lançar", formatar_brl(total))
    c2.metric("NFs válidas", qtd_validas)
    c3.metric("Fornecedores novos", qtd_novos)
    c4.metric("🔄 Atualizar valor", qtd_atualizar)
    c5.metric("⚠️ Duplicadas (ignorar)", qtd_duplicadas)

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
            atualizados = 0
            duplicados = 0
            forn_novos = 0
            for l in linhas_previa:
                nf = l["_nf"]
                if not nf or not nf.cnpj_prestador or nf.valor_total <= 0:
                    continue

                avaliacao = l.get("_avaliacao", {"acao": "criar"})
                acao = avaliacao.get("acao")

                # Pula duplicado exato (mesma NF + mesmo valor)
                if acao == "duplicado_exato":
                    duplicados += 1
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

                # Atualizar valor de lançamento existente
                if acao == "atualizar_valor":
                    gasto_id = avaliacao["gasto_existente"]["id"]
                    repo_financeiro.atualizar_gasto(gasto_id, {
                        "valor": float(nf.valor_total),
                        "data_emissao": nf.data_emissao.isoformat() if nf.data_emissao else None,
                        "descricao_servico": nf.descricao_servico,
                        "nome_arquivo_pdf": l["Arquivo"],
                        "mes_ano": mes_ano,
                    })
                    atualizados += 1
                    continue

                # Caso padrão: criar
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

            partes = [f"✅ Processamento concluído em **{nome_mes(mes_ano)}/{ano}**."]
            if criados:
                partes.append(f"- 🆕 {criados} lançamento(s) criado(s)")
            if atualizados:
                partes.append(f"- 🔄 {atualizados} lançamento(s) atualizado(s) (valor mudou)")
            if duplicados:
                partes.append(f"- ⚠️ {duplicados} NF(s) ignorada(s) (duplicada exata)")
            if forn_novos:
                partes.append(f"- 🏢 {forn_novos} fornecedor(es) novo(s) cadastrado(s) automaticamente")
            if total > 0:
                partes.append(f"- 💰 Total processado: {formatar_brl(total)}")

            st.session_state["fin_upload_msg"] = {
                "tipo": "sucesso",
                "texto": "\n".join(partes),
            }
            st.toast("✅ Lançamentos processados!", icon="✅")
            st.rerun()
        except Exception as e:
            import traceback
            st.session_state["fin_upload_msg"] = {
                "tipo": "erro",
                "texto": f"❌ Erro ao gravar: {type(e).__name__}: {e}",
            }
            st.session_state["fin_upload_erros_detalhe"] = traceback.format_exc()
            st.rerun()
