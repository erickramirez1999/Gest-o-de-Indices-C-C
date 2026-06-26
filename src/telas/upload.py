"""Tela de Upload Mensal — LLE Índices. Aceita múltiplos arquivos."""
from __future__ import annotations
import streamlit as st
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE
from src.utils.formatadores import nome_mes
import datetime


def renderizar_upload(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📤 Upload Mensal</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Faça o upload dos arquivos mensais para atualizar os dashboards. Você pode enviar múltiplos arquivos de uma vez.")

    area = st.radio(
        "Área",
        ["COBRANCA", "CREDITO"],
        format_func=lambda x: "📊 Cobrança" if x == "COBRANCA" else "💳 Crédito",
        horizontal=True,
    )

    st.markdown("---")

    if area == "COBRANCA":
        _upload_cobranca(usuario)
    else:
        _upload_credito(usuario)


# ============================================================
# UPLOAD COBRANÇA
# ============================================================

def _upload_cobranca(usuario):
    from src.servicos.leitor_cobranca import ler_multiplos_arquivos_cobranca
    from src.banco import repo_dados

    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11; border-left:4px solid {AZUL_ESCURO}; "
        f"padding:12px; border-radius:6px; margin-bottom:16px;'>"
        f"<b>Arquivos aceitos (pode enviar vários de uma vez):</b><br>"
        f"• Acordos Realizados Detalhado (.xlsx) — 1 linha por parcela, agrupado por acordo<br>"
        f"• Ocorrências de Acordo (.xlsx) — acordos e quebras de acordo<br>"
        f"• Cobrança Baixada por Cobrador (.xls/.xlsx) — baixas e aging<br>"
        f"• Relatório de Produtividade (.xlsx) — TTO diário por negociador<br>"
        f"<i>Pode subir em momentos diferentes: cada envio substitui só a sua categoria, sem apagar o resto do mês.</i>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col_mes, col_ano = st.columns(2)
    with col_mes:
        mes = st.selectbox(
            "Mês", list(range(1, 13)),
            format_func=lambda m: nome_mes(f"2026-{m:02d}").split("/")[0],
        )
    with col_ano:
        ano = st.number_input("Ano", min_value=2024, max_value=2030,
                              value=datetime.date.today().year)

    mes_ano = f"{ano}-{mes:02d}"

    arquivos = st.file_uploader(
        "Selecione os arquivos de Cobrança",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="upload_cob_multi",
    )

    if arquivos:
        st.markdown(f"**{len(arquivos)} arquivo(s) selecionado(s):**")
        for arq in arquivos:
            st.caption(f"• {arq.name} · {arq.size / 1024:.0f} KB")

        # Preview
        with st.expander("👁 Preview — verificar antes de confirmar"):
            lista = [(arq.read(), arq.name) for arq in arquivos]
            # Rebobina os arquivos
            for arq in arquivos:
                arq.seek(0)
            resultado = ler_multiplos_arquivos_cobranca(lista)

            st.markdown("**Arquivos identificados:**")
            for proc in resultado["arquivos_processados"]:
                st.caption(f"✓ {proc}")

            ocor = resultado.get("ocorrencias")
            n_quebras = int(ocor["eh_quebra"].sum()) if ocor is not None and not ocor.empty and "eh_quebra" in ocor else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Acordos", len(resultado["acordos"]))
            c2.metric("Baixas", len(resultado["baixas"]))
            c3.metric("Cobradores (perf.)", len(resultado["performance"]))
            c4.metric("Quebras", n_quebras)

            if resultado["erros"]:
                for e in resultado["erros"]:
                    st.warning(f"⚠ {e}")

        if st.button("✅ Confirmar Upload", type="primary", use_container_width=True, key="btn_conf_cob"):
            with st.spinner("Processando e salvando..."):
                lista = [(arq.read(), arq.name) for arq in arquivos]
                resultado = ler_multiplos_arquivos_cobranca(lista)

                # Só substitui as categorias que vieram neste envio
                tem_acordos = not resultado["acordos"].empty
                tem_baixas = not resultado["baixas"].empty
                tem_perf = not resultado["performance"].empty
                ocor = resultado.get("ocorrencias")
                tem_ocor = ocor is not None and not ocor.empty

                tabelas = []
                if tem_acordos: tabelas.append("dados_cobranca_acordo")
                if tem_baixas: tabelas.append("dados_cobranca_baixa")
                if tem_perf: tabelas.append("dados_cobranca_performance")
                if tem_ocor: tabelas.append("dados_cobranca_ocorrencia")

                if not tabelas:
                    st.warning("Nenhum dado reconhecido nos arquivos enviados.")
                    st.stop()

                nome_ref = " + ".join(arq.name for arq in arquivos)
                upload_id = repo_dados.registrar_upload_incremental(
                    "COBRANCA", mes_ano, nome_ref, usuario.id, tabelas
                )

                if tem_acordos:
                    repo_dados.inserir_acordos(
                        upload_id, mes_ano,
                        resultado["acordos"].where(resultado["acordos"].notna(), None).to_dict("records"),
                    )
                if tem_baixas:
                    repo_dados.inserir_baixas(
                        upload_id, mes_ano,
                        resultado["baixas"].where(resultado["baixas"].notna(), None).to_dict("records"),
                    )
                if tem_perf:
                    repo_dados.inserir_performance(
                        upload_id, mes_ano,
                        resultado["performance"].where(resultado["performance"].notna(), None).to_dict("records"),
                    )
                n_quebras = 0
                if tem_ocor:
                    n_quebras = int(ocor["eh_quebra"].sum()) if "eh_quebra" in ocor else 0
                    try:
                        repo_dados.inserir_ocorrencias(
                            upload_id, mes_ano,
                            ocor.where(ocor.notna(), None).to_dict("records"),
                        )
                    except Exception as e:
                        det = {
                            "code": getattr(e, "code", None),
                            "message": getattr(e, "message", None),
                            "details": getattr(e, "details", None),
                            "hint": getattr(e, "hint", None),
                        }
                        st.error(
                            "Falha ao gravar OCORRÊNCIAS no Supabase.\n\n"
                            f"**code:** {det['code']}\n\n"
                            f"**message:** {det['message']}\n\n"
                            f"**details:** {det['details']}\n\n"
                            f"**hint:** {det['hint']}\n\n"
                            f"**raw:** {repr(e)[:800]}"
                        )
                        st.stop()

            partes = []
            if tem_acordos: partes.append(f"{len(resultado['acordos'])} acordos")
            if tem_baixas: partes.append(f"{len(resultado['baixas'])} baixas")
            if tem_perf: partes.append(f"{len(resultado['performance'])} cobradores")
            if tem_ocor: partes.append(f"{n_quebras} quebras")
            st.success(
                f"✓ Cobrança de **{nome_mes(mes_ano)}** atualizada! "
                + " · ".join(partes)
                + ". (Só as categorias enviadas foram substituídas; o restante do mês foi mantido.)"
            )
            from src.banco.repo_auditoria import registrar as _audit
            _audit(usuario.id, usuario.nome, "UPLOAD_COBRANCA", "COBRANCA",
                   f"Mês: {nome_mes(mes_ano)} · Arquivo: {nome_ref}")
            st.balloons()


# ============================================================
# UPLOAD CRÉDITO
# ============================================================

def _upload_credito(usuario):
    from src.servicos.leitor_credito import ler_multiplos_arquivos_credito
    from src.banco import repo_dados

    st.markdown(
        f"<div style='background:{AZUL_ESCURO}11; border-left:4px solid {AZUL_ESCURO}; "
        f"padding:12px; border-radius:6px; margin-bottom:16px;'>"
        f"<b>Arquivos aceitos (pode enviar vários de uma vez):</b><br>"
        f"• FIN - Liberações por pedido (.xlsx ou .xls) — blocos: Passaram Direto, Liberados, Negados<br>"
        f"• FIN - Aumento de Limite (.xls) — reanálises de limite de crédito"
        f"</div>",
        unsafe_allow_html=True,
    )

    col_mes, col_ano = st.columns(2)
    with col_mes:
        mes = st.selectbox(
            "Mês", list(range(1, 13)),
            format_func=lambda m: nome_mes(f"2026-{m:02d}").split("/")[0],
            key="mes_cred",
        )
    with col_ano:
        ano = st.number_input("Ano", min_value=2024, max_value=2030,
                              value=datetime.date.today().year, key="ano_cred")

    mes_ano = f"{ano}-{mes:02d}"

    arquivos = st.file_uploader(
        "Selecione os arquivos de Crédito",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="upload_cred_multi",
    )

    if arquivos:
        st.markdown(f"**{len(arquivos)} arquivo(s) selecionado(s):**")
        for arq in arquivos:
            st.caption(f"• {arq.name} · {arq.size / 1024:.0f} KB")

        # Preview
        with st.expander("👁 Preview — verificar antes de confirmar"):
            lista = [(arq.read(), arq.name) for arq in arquivos]
            for arq in arquivos:
                arq.seek(0)
            resultado = ler_multiplos_arquivos_credito(lista)

            st.markdown("**Arquivos identificados:**")
            for proc in resultado["arquivos_processados"]:
                st.caption(f"✓ {proc}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Passaram Direto", len(resultado["passaram_direto"]))
            c2.metric("Liberados", len(resultado["liberados"]))
            c3.metric("Negados", len(resultado["negados"]))
            c4.metric("Reanálises Limite", len(resultado["limites"]))
            c5.metric("Tempo Tela", len(resultado["tempo_tela"]) if "tempo_tela" in resultado and resultado["tempo_tela"] is not None and not resultado["tempo_tela"].empty else 0)

            if resultado["erros"]:
                for e in resultado["erros"]:
                    st.warning(f"⚠ {e}")

        if st.button("✅ Confirmar Upload", type="primary", use_container_width=True, key="btn_conf_cred"):
            with st.spinner("Processando e salvando..."):
                lista = [(arq.read(), arq.name) for arq in arquivos]
                resultado = ler_multiplos_arquivos_credito(lista)

                nome_ref = " + ".join(arq.name for arq in arquivos)
                upload_id = repo_dados.registrar_upload(
                    "CREDITO", mes_ano, nome_ref, usuario.id
                )

                registros_lib = []
                for tipo, df in [
                    ("DIRETO", resultado["passaram_direto"]),
                    ("LIBERADO", resultado["liberados"]),
                    ("NEGADO", resultado["negados"]),
                ]:
                    if not df.empty:
                        for rec in df.where(df.notna(), None).to_dict("records"):
                            rec["tipo"] = tipo
                            registros_lib.append(rec)

                if registros_lib:
                    repo_dados.inserir_liberacoes(upload_id, mes_ano, registros_lib)

                if not resultado["limites"].empty:
                    repo_dados.inserir_limites(
                        upload_id, mes_ano,
                        resultado["limites"].where(resultado["limites"].notna(), None).to_dict("records"),
                    )

                tempo_tela = resultado.get("tempo_tela")
                total_tempo = 0
                if tempo_tela is not None and not tempo_tela.empty:
                    repo_dados.inserir_tempo_tela(
                        upload_id, mes_ano,
                        tempo_tela.where(tempo_tela.notna(), None).to_dict("records"),
                    )
                    total_tempo = len(tempo_tela)

            total_lib = len(registros_lib) if registros_lib else 0
            total_lim = len(resultado["limites"])
            st.success(
                f"✓ Crédito de **{nome_mes(mes_ano)}** carregado! "
                f"{total_lib} liberações · {total_lim} reanálises · {total_tempo} analistas (tempo tela)."
            )
            from src.banco.repo_auditoria import registrar as _audit
            _audit(usuario.id, usuario.nome, "UPLOAD_CREDITO", "CREDITO",
                   f"Mês: {nome_mes(mes_ano)} · Arquivo: {nome_ref}")
            st.balloons()
