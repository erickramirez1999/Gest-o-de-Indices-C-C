"""
Tela Crédito — Comparativo Semanal.

Permite subir 2 conjuntos de arquivos do Sankhya/CobCloud (geralmente 2 semanas
seguidas) e comparar lado a lado todos os indicadores:
  - Liberações (Passaram Direto, Liberados, Negados) — qtd + valor
  - Aumento de Limite — qtd + valor médio + total
  - Tempo Médio de Liberação — minutos médios + minutos por evento
"""
from __future__ import annotations
import hashlib
import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.servicos.leitor_credito import ler_multiplos_arquivos_credito
from src.utils.marca import AZUL_ESCURO, VERDE, AZUL_VIVO

# Cores oficiais LLE
COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_VERMELHO = "#DC3545"
COR_AMARELO = "#FAC318"
COR_LARANJA = "#F57C00"
COR_ROXO = "#7B1FA2"


def renderizar_cred_comparativo(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO}'>📊 Comparativo Semanal — Crédito</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Suba os arquivos das **2 semanas** que deseja comparar. "
        "O sistema detecta automaticamente cada tipo de planilha e gera o comparativo completo."
    )

    # ─── Inputs de período (livre, só pra rotular os gráficos) ───────
    col_label1, col_label2 = st.columns(2)
    with col_label1:
        rotulo_a = st.text_input(
            "📅 Período A (rótulo)",
            value="Semana Anterior",
            key="cmp_rotulo_a",
            help="Ex: 15/06 a 19/06",
        )
    with col_label2:
        rotulo_b = st.text_input(
            "📅 Período B (rótulo)",
            value="Semana Atual",
            key="cmp_rotulo_b",
            help="Ex: 22/06 a 26/06",
        )

    st.markdown("---")

    # ─── Upload de cada semana ───────────────────────────────────────
    col_up1, col_up2 = st.columns(2)

    with col_up1:
        st.markdown(f"##### 📁 Arquivos · {rotulo_a}")
        arquivos_a = st.file_uploader(
            "Subir 1 ou mais arquivos (liberações, limite, tempo)",
            type=["xls", "xlsx", "csv"],
            accept_multiple_files=True,
            key="cmp_arquivos_a",
        )

    with col_up2:
        st.markdown(f"##### 📁 Arquivos · {rotulo_b}")
        arquivos_b = st.file_uploader(
            "Subir 1 ou mais arquivos (liberações, limite, tempo)",
            type=["xls", "xlsx", "csv"],
            accept_multiple_files=True,
            key="cmp_arquivos_b",
        )

    if not arquivos_a or not arquivos_b:
        st.info(
            "⬆️ Para gerar o comparativo, suba pelo menos 1 arquivo em cada semana. "
            "Pode ser qualquer combinação: liberações, aumento de limite, tempo de tela — "
            "o sistema reconhece automaticamente."
        )
        return

    # ─── Processar arquivos ──────────────────────────────────────────
    with st.spinner("📊 Processando arquivos..."):
        dados_a = _processar_arquivos(arquivos_a)
        dados_b = _processar_arquivos(arquivos_b)

    # Mostrar arquivos processados
    with st.expander("📋 Arquivos processados", expanded=False):
        col_diag_a, col_diag_b = st.columns(2)
        with col_diag_a:
            st.markdown(f"**{rotulo_a}**")
            for arq in dados_a["arquivos_processados"]:
                st.markdown(f"- ✅ {arq}")
            for erro in dados_a["erros"]:
                st.markdown(f"- ⚠️ {erro}")
        with col_diag_b:
            st.markdown(f"**{rotulo_b}**")
            for arq in dados_b["arquivos_processados"]:
                st.markdown(f"- ✅ {arq}")
            for erro in dados_b["erros"]:
                st.markdown(f"- ⚠️ {erro}")

    st.markdown("---")

    # ─── KPIs principais (Liberações) ────────────────────────────────
    _renderizar_kpis_liberacoes(dados_a, dados_b, rotulo_a, rotulo_b)

    # ─── Gráficos comparativos (Liberações) ──────────────────────────
    _renderizar_graficos_liberacoes(dados_a, dados_b, rotulo_a, rotulo_b)

    # ─── Aumento de Limite ───────────────────────────────────────────
    _renderizar_aumento_limite(dados_a, dados_b, rotulo_a, rotulo_b)

    # ─── Tempo Médio de Liberação ────────────────────────────────────
    _renderizar_tempo_tela(dados_a, dados_b, rotulo_a, rotulo_b)

    # ─── Exportar comparativo ────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Exportar Comparativo")

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        excel_bytes = _exportar_comparativo_excel(
            dados_a, dados_b, rotulo_a, rotulo_b
        )
        st.download_button(
            "💾 Baixar Excel",
            data=excel_bytes,
            file_name=f"comparativo_credito_{rotulo_a.replace(' ', '_')}_vs_{rotulo_b.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col_exp2:
        if st.button("📊 Gerar Apresentação PPT", use_container_width=True, type="primary"):
            with st.spinner("📊 Montando apresentação..."):
                try:
                    from src.servicos.gerador_ppt import gerar_ppt_comparativo_credito
                    ppt_bytes = gerar_ppt_comparativo_credito(
                        dados_a, dados_b, rotulo_a, rotulo_b
                    )
                    st.session_state["cmp_ppt_bytes"] = ppt_bytes
                    st.session_state["cmp_ppt_nome"] = (
                        f"comparativo_credito_{rotulo_a.replace(' ', '_')}_vs_{rotulo_b.replace(' ', '_')}.pptx"
                    )
                    st.toast("✅ Apresentação gerada!", icon="🎯")
                except Exception as e:
                    st.error(f"❌ Erro ao gerar PPT: {type(e).__name__}: {e}")

        # Aparece SÓ se já foi gerado
        if st.session_state.get("cmp_ppt_bytes"):
            st.download_button(
                "⬇️ Baixar PPT",
                data=st.session_state["cmp_ppt_bytes"],
                file_name=st.session_state.get("cmp_ppt_nome", "comparativo_credito.pptx"),
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )


# ============================================================
# PROCESSAMENTO DE ARQUIVOS
# ============================================================

def _processar_arquivos(arquivos) -> dict:
    """Lê múltiplos uploads e devolve resultado consolidado."""
    pacote = [(a.getvalue(), a.name) for a in arquivos]
    return ler_multiplos_arquivos_credito(pacote)


# ============================================================
# BLOCO 1 — KPIs DE LIBERAÇÕES
# ============================================================

def _renderizar_kpis_liberacoes(dados_a, dados_b, rot_a, rot_b):
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>🎯 Liberações — Resumo</h3>",
                unsafe_allow_html=True)

    # Contagem por tipo
    pd_a = len(dados_a["passaram_direto"])
    pd_b = len(dados_b["passaram_direto"])
    lib_a = len(dados_a["liberados"])
    lib_b = len(dados_b["liberados"])
    neg_a = len(dados_a["negados"])
    neg_b = len(dados_b["negados"])

    total_a = pd_a + lib_a + neg_a
    total_b = pd_b + lib_b + neg_b

    aprov_a = pd_a + lib_a
    aprov_b = pd_b + lib_b

    taxa_aprov_a = (aprov_a / total_a * 100) if total_a > 0 else 0
    taxa_aprov_b = (aprov_b / total_b * 100) if total_b > 0 else 0

    # KPI cards lado a lado
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        _kpi_card("📥 Total Pedidos", total_a, total_b, rot_a, rot_b)
    with col2:
        _kpi_card("⚡ Passaram Direto", pd_a, pd_b, rot_a, rot_b, cor=COR_VERDE)
    with col3:
        _kpi_card("✅ Liberados", lib_a, lib_b, rot_a, rot_b, cor=COR_AZUL)
    with col4:
        _kpi_card("❌ Negados", neg_a, neg_b, rot_a, rot_b, cor=COR_VERMELHO)

    # 2ª linha — taxa
    col5, col6 = st.columns(2)
    with col5:
        _kpi_card("📈 Taxa de Aprovação", taxa_aprov_a, taxa_aprov_b,
                  rot_a, rot_b, sufixo="%", formato="pct")
    with col6:
        taxa_neg_a = (neg_a / total_a * 100) if total_a > 0 else 0
        taxa_neg_b = (neg_b / total_b * 100) if total_b > 0 else 0
        _kpi_card("📉 Taxa de Negação", taxa_neg_a, taxa_neg_b,
                  rot_a, rot_b, sufixo="%", formato="pct", cor=COR_VERMELHO)


def _kpi_card(titulo, valor_a, valor_b, rot_a, rot_b, sufixo="", formato="int", cor=None):
    """Card com 2 valores e variação."""
    if cor is None:
        cor = AZUL_ESCURO

    if formato == "pct":
        v_a_str = f"{valor_a:.1f}{sufixo}"
        v_b_str = f"{valor_b:.1f}{sufixo}"
    else:
        v_a_str = f"{int(valor_a):,}{sufixo}".replace(",", ".")
        v_b_str = f"{int(valor_b):,}{sufixo}".replace(",", ".")

    # Variação
    if valor_a > 0:
        delta_pct = (valor_b - valor_a) / valor_a * 100
        if delta_pct > 0:
            seta = "▲"
            cor_delta = COR_VERDE
        elif delta_pct < 0:
            seta = "▼"
            cor_delta = COR_VERMELHO
        else:
            seta = "■"
            cor_delta = "#666"
        delta_str = f"{seta} {delta_pct:+.1f}%"
    else:
        delta_str = "—"
        cor_delta = "#666"

    st.markdown(
        f"""
        <div style='background:white; padding:14px; border-radius:8px;
        border-left:4px solid {cor}; box-shadow:0 1px 3px rgba(0,0,0,0.08);
        margin-bottom:10px;'>
            <div style='font-size:13px; color:#555; font-weight:600;'>{titulo}</div>
            <div style='font-size:11px; color:#888;'>{rot_a}</div>
            <div style='font-size:18px; color:{AZUL_ESCURO}; font-weight:500;'>{v_a_str}</div>
            <div style='font-size:11px; color:#888; margin-top:4px;'>{rot_b}</div>
            <div style='font-size:22px; color:{cor}; font-weight:700;'>{v_b_str}</div>
            <div style='font-size:13px; color:{cor_delta}; margin-top:6px; font-weight:600;'>{delta_str}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# BLOCO 2 — GRÁFICOS DE LIBERAÇÕES
# ============================================================

def _renderizar_graficos_liberacoes(dados_a, dados_b, rot_a, rot_b):
    st.markdown("##### 📊 Composição")

    pd_a = len(dados_a["passaram_direto"])
    pd_b = len(dados_b["passaram_direto"])
    lib_a = len(dados_a["liberados"])
    lib_b = len(dados_b["liberados"])
    neg_a = len(dados_a["negados"])
    neg_b = len(dados_b["negados"])

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        # Barras agrupadas
        fig = go.Figure()
        cats = ["Passaram Direto", "Liberados", "Negados"]
        vals_a = [pd_a, lib_a, neg_a]
        vals_b = [pd_b, lib_b, neg_b]

        fig.add_trace(go.Bar(
            name=rot_a, x=cats, y=vals_a,
            marker_color=AZUL_VIVO, text=vals_a, textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name=rot_b, x=cats, y=vals_b,
            marker_color=COR_AMARELO, text=vals_b, textposition="outside",
        ))
        fig.update_layout(
            barmode="group", height=350, margin=dict(t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_g2:
        # Pizza lado a lado — composição
        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=["Passaram", "Liberados", "Negados"],
            values=[pd_a, lib_a, neg_a],
            name=rot_a,
            marker_colors=[COR_VERDE, COR_AZUL, COR_VERMELHO],
            domain=dict(x=[0, 0.45]),
            title=dict(text=rot_a, font=dict(size=13)),
            hole=0.4,
        ))
        fig.add_trace(go.Pie(
            labels=["Passaram", "Liberados", "Negados"],
            values=[pd_b, lib_b, neg_b],
            name=rot_b,
            marker_colors=[COR_VERDE, COR_AZUL, COR_VERMELHO],
            domain=dict(x=[0.55, 1.0]),
            title=dict(text=rot_b, font=dict(size=13)),
            hole=0.4,
        ))
        fig.update_layout(height=350, margin=dict(t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# BLOCO 3 — AUMENTO DE LIMITE
# ============================================================

def _renderizar_aumento_limite(dados_a, dados_b, rot_a, rot_b):
    df_a = dados_a.get("limites", pd.DataFrame())
    df_b = dados_b.get("limites", pd.DataFrame())

    if df_a.empty and df_b.empty:
        return

    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>💳 Aumento de Limite</h3>",
                unsafe_allow_html=True)

    # KPIs
    qtd_a = len(df_a)
    qtd_b = len(df_b)

    soma_anterior_a = df_a["limite_anterior"].sum() if "limite_anterior" in df_a.columns and not df_a.empty else 0
    soma_novo_a = df_a["novo_limite"].sum() if "novo_limite" in df_a.columns and not df_a.empty else 0
    soma_anterior_b = df_b["limite_anterior"].sum() if "limite_anterior" in df_b.columns and not df_b.empty else 0
    soma_novo_b = df_b["novo_limite"].sum() if "novo_limite" in df_b.columns and not df_b.empty else 0

    incremento_a = soma_novo_a - soma_anterior_a
    incremento_b = soma_novo_b - soma_anterior_b

    col1, col2, col3 = st.columns(3)
    with col1:
        _kpi_card("🔢 Qtd. Alterações", qtd_a, qtd_b, rot_a, rot_b, cor=COR_LARANJA)
    with col2:
        _kpi_card_brl("💵 Incremento Total", incremento_a, incremento_b, rot_a, rot_b, cor=COR_VERDE)
    with col3:
        media_a = incremento_a / qtd_a if qtd_a > 0 else 0
        media_b = incremento_b / qtd_b if qtd_b > 0 else 0
        _kpi_card_brl("📊 Incremento Médio", media_a, media_b, rot_a, rot_b, cor=AZUL_VIVO)


# ============================================================
# BLOCO 4 — TEMPO DE TELA
# ============================================================

def _renderizar_tempo_tela(dados_a, dados_b, rot_a, rot_b):
    df_a = dados_a.get("tempo_tela", pd.DataFrame())
    df_b = dados_b.get("tempo_tela", pd.DataFrame())

    if df_a.empty and df_b.empty:
        return

    st.markdown("---")
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>⏱️ Tempo Médio de Liberação</h3>",
                unsafe_allow_html=True)

    col_tempo = None
    for c in ["tempo_minutos", "tempo", "Tempo (minutos)", "Tempo"]:
        if c in df_a.columns or c in df_b.columns:
            col_tempo = c
            break

    if col_tempo is None:
        st.info("Não foi possível identificar a coluna de tempo nas planilhas.")
        return

    media_a = df_a[col_tempo].mean() if not df_a.empty and col_tempo in df_a.columns else 0
    media_b = df_b[col_tempo].mean() if not df_b.empty and col_tempo in df_b.columns else 0
    qtd_a = len(df_a)
    qtd_b = len(df_b)

    col1, col2 = st.columns(2)
    with col1:
        _kpi_card("📋 Qtd. Eventos", qtd_a, qtd_b, rot_a, rot_b, cor=COR_ROXO)
    with col2:
        _kpi_card_min("⏱️ Tempo Médio", media_a, media_b, rot_a, rot_b, cor=COR_AZUL)

    # Comparar por tipo de evento, se houver
    col_evento = None
    for c in ["desc_evento", "Desc Evento", "evento", "Evento"]:
        if c in df_a.columns or c in df_b.columns:
            col_evento = c
            break

    if col_evento and (not df_a.empty or not df_b.empty):
        st.markdown("##### 📊 Tempo Médio por Tipo de Evento")
        evt_a = df_a.groupby(col_evento)[col_tempo].mean() if not df_a.empty else pd.Series(dtype=float)
        evt_b = df_b.groupby(col_evento)[col_tempo].mean() if not df_b.empty else pd.Series(dtype=float)
        eventos = sorted(set(evt_a.index) | set(evt_b.index))

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name=rot_a, x=eventos,
            y=[evt_a.get(e, 0) for e in eventos],
            marker_color=AZUL_VIVO,
            text=[f"{evt_a.get(e, 0):.1f}m" for e in eventos],
            textposition="outside",
        ))
        fig.add_trace(go.Bar(
            name=rot_b, x=eventos,
            y=[evt_b.get(e, 0) for e in eventos],
            marker_color=COR_AMARELO,
            text=[f"{evt_b.get(e, 0):.1f}m" for e in eventos],
            textposition="outside",
        ))
        fig.update_layout(
            barmode="group", height=380, margin=dict(t=20, b=20),
            yaxis_title="Minutos",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)


# Helpers extras (R$ e minutos)
def _kpi_card_brl(titulo, valor_a, valor_b, rot_a, rot_b, cor=None):
    from src.utils.formatadores import formatar_brl
    if cor is None:
        cor = AZUL_ESCURO
    v_a_str = formatar_brl(valor_a)
    v_b_str = formatar_brl(valor_b)
    if valor_a != 0:
        delta_pct = (valor_b - valor_a) / abs(valor_a) * 100
        seta = "▲" if delta_pct > 0 else ("▼" if delta_pct < 0 else "■")
        cor_delta = COR_VERDE if delta_pct > 0 else (COR_VERMELHO if delta_pct < 0 else "#666")
        delta_str = f"{seta} {delta_pct:+.1f}%"
    else:
        delta_str = "—"; cor_delta = "#666"

    st.markdown(
        f"""<div style='background:white; padding:14px; border-radius:8px;
        border-left:4px solid {cor}; box-shadow:0 1px 3px rgba(0,0,0,0.08); margin-bottom:10px;'>
            <div style='font-size:13px; color:#555; font-weight:600;'>{titulo}</div>
            <div style='font-size:11px; color:#888;'>{rot_a}</div>
            <div style='font-size:18px; color:{AZUL_ESCURO}; font-weight:500;'>{v_a_str}</div>
            <div style='font-size:11px; color:#888; margin-top:4px;'>{rot_b}</div>
            <div style='font-size:22px; color:{cor}; font-weight:700;'>{v_b_str}</div>
            <div style='font-size:13px; color:{cor_delta}; margin-top:6px; font-weight:600;'>{delta_str}</div>
        </div>""", unsafe_allow_html=True)


def _kpi_card_min(titulo, valor_a, valor_b, rot_a, rot_b, cor=None):
    if cor is None:
        cor = AZUL_ESCURO
    v_a_str = f"{valor_a:.1f} min"
    v_b_str = f"{valor_b:.1f} min"
    if valor_a != 0:
        delta_pct = (valor_b - valor_a) / valor_a * 100
        # Pra TEMPO, menos é melhor — invertemos cor
        seta = "▲" if delta_pct > 0 else ("▼" if delta_pct < 0 else "■")
        cor_delta = COR_VERMELHO if delta_pct > 0 else (COR_VERDE if delta_pct < 0 else "#666")
        delta_str = f"{seta} {delta_pct:+.1f}%"
    else:
        delta_str = "—"; cor_delta = "#666"

    st.markdown(
        f"""<div style='background:white; padding:14px; border-radius:8px;
        border-left:4px solid {cor}; box-shadow:0 1px 3px rgba(0,0,0,0.08); margin-bottom:10px;'>
            <div style='font-size:13px; color:#555; font-weight:600;'>{titulo}</div>
            <div style='font-size:11px; color:#888;'>{rot_a}</div>
            <div style='font-size:18px; color:{AZUL_ESCURO}; font-weight:500;'>{v_a_str}</div>
            <div style='font-size:11px; color:#888; margin-top:4px;'>{rot_b}</div>
            <div style='font-size:22px; color:{cor}; font-weight:700;'>{v_b_str}</div>
            <div style='font-size:13px; color:{cor_delta}; margin-top:6px; font-weight:600;'>{delta_str}</div>
        </div>""", unsafe_allow_html=True)


# ============================================================
# EXPORT EXCEL
# ============================================================

def _exportar_comparativo_excel(dados_a, dados_b, rot_a, rot_b) -> bytes:
    """Gera Excel com 1 aba por seção (resumo + dados detalhados)."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Aba Resumo
        resumo = pd.DataFrame({
            "Indicador": [
                "Passaram Direto", "Liberados", "Negados", "Total Pedidos",
                "Taxa Aprovação (%)", "Taxa Negação (%)",
                "Qtd. Alterações Limite", "Qtd. Eventos Tempo",
            ],
            rot_a: [
                len(dados_a["passaram_direto"]),
                len(dados_a["liberados"]),
                len(dados_a["negados"]),
                len(dados_a["passaram_direto"]) + len(dados_a["liberados"]) + len(dados_a["negados"]),
                _safe_pct(
                    len(dados_a["passaram_direto"]) + len(dados_a["liberados"]),
                    len(dados_a["passaram_direto"]) + len(dados_a["liberados"]) + len(dados_a["negados"]),
                ),
                _safe_pct(
                    len(dados_a["negados"]),
                    len(dados_a["passaram_direto"]) + len(dados_a["liberados"]) + len(dados_a["negados"]),
                ),
                len(dados_a.get("limites", pd.DataFrame())),
                len(dados_a.get("tempo_tela", pd.DataFrame())),
            ],
            rot_b: [
                len(dados_b["passaram_direto"]),
                len(dados_b["liberados"]),
                len(dados_b["negados"]),
                len(dados_b["passaram_direto"]) + len(dados_b["liberados"]) + len(dados_b["negados"]),
                _safe_pct(
                    len(dados_b["passaram_direto"]) + len(dados_b["liberados"]),
                    len(dados_b["passaram_direto"]) + len(dados_b["liberados"]) + len(dados_b["negados"]),
                ),
                _safe_pct(
                    len(dados_b["negados"]),
                    len(dados_b["passaram_direto"]) + len(dados_b["liberados"]) + len(dados_b["negados"]),
                ),
                len(dados_b.get("limites", pd.DataFrame())),
                len(dados_b.get("tempo_tela", pd.DataFrame())),
            ],
        })
        resumo.to_excel(writer, sheet_name="Resumo", index=False)

        # Abas detalhadas
        for chave, nome in [
            ("passaram_direto", "Passaram Direto"),
            ("liberados", "Liberados"),
            ("negados", "Negados"),
            ("limites", "Aumento Limite"),
            ("tempo_tela", "Tempo Tela"),
        ]:
            df_a = dados_a.get(chave, pd.DataFrame())
            df_b = dados_b.get(chave, pd.DataFrame())
            if not df_a.empty:
                df_a.to_excel(writer, sheet_name=f"{nome} - {rot_a}"[:31], index=False)
            if not df_b.empty:
                df_b.to_excel(writer, sheet_name=f"{nome} - {rot_b}"[:31], index=False)

    output.seek(0)
    return output.getvalue()


def _safe_pct(num, den):
    if den == 0:
        return 0.0
    return round(num / den * 100, 1)
