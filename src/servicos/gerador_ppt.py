"""
Gerador de apresentação PPT profissional — LLE Índices.

Gera PPT individual (por mês) e PPT Geral (consolidado histórico).
Inclui:
  - Layout LLE com cores e tipografia oficiais
  - Gráficos reais exportados como imagem (plotly → PNG)
  - Cards de KPI estilizados
  - Textos analíticos automáticos
  - Slide de alertas e destaques
"""
from __future__ import annotations
import io
from typing import Optional

# Cores LLE (hex sem #)
AZUL     = "041747"
AMARELO  = "FAC318"
VERDE    = "0F8C3B"
VERMELHO = "DC3545"
BRANCO   = "FFFFFF"
CINZA_F  = "F8F9FA"
CINZA_M  = "6C757D"
AZUL_V   = "0071FE"


# ============================================================
# ENTRYPOINTS PÚBLICOS
# ============================================================

def gerar_ppt_cobranca(dados: dict, mes_label: str) -> bytes:
    """PPT individual de Cobrança."""
    prs = _nova_apresentacao()
    _slide_capa(prs, "Relatório de Cobrança", mes_label, "Crédito & Cobrança · Grupo LLE")
    _slide_kpis_cobranca(prs, dados, mes_label)
    _slide_acordos_graficos(prs, dados.get("df_acordos"), mes_label)
    _slide_baixas_graficos(prs, dados.get("df_baixas"), mes_label)
    _slide_performance_graficos(prs, dados.get("df_performance"), mes_label)
    _slide_destaques_cobranca(prs, dados, mes_label)
    _slide_encerramento(prs, "COBRANÇA")
    return _salvar(prs)


def gerar_ppt_credito(dados: dict, mes_label: str) -> bytes:
    """PPT individual de Crédito."""
    prs = _nova_apresentacao()
    _slide_capa(prs, "Relatório de Crédito", mes_label, "Análise de Crédito · Grupo LLE")
    _slide_kpis_credito(prs, dados, mes_label)
    _slide_fluxo_pedidos_grafico(prs, dados.get("df_liberacoes"), mes_label)
    _slide_limites_grafico(prs, dados.get("df_limites"), mes_label)
    _slide_ranking_analistas_slide(prs, dados.get("df_liberacoes"), mes_label)
    _slide_destaques_credito(prs, dados, mes_label)
    _slide_encerramento(prs, "CRÉDITO")
    return _salvar(prs)


def gerar_ppt_geral(dados_cobranca: list[dict], dados_credito: list[dict]) -> bytes:
    """PPT Geral consolidado com histórico de todos os meses."""
    prs = _nova_apresentacao()
    _slide_capa(prs, "Relatório Geral", "Consolidado Histórico", "Crédito & Cobrança · Grupo LLE")
    _slide_resumo_executivo(prs, dados_cobranca, dados_credito)
    _slide_evolucao_cobranca(prs, dados_cobranca)
    _slide_evolucao_credito(prs, dados_credito)
    _slide_comparativo_cobradores(prs, dados_cobranca)
    _slide_comparativo_analistas(prs, dados_credito)
    _slide_alertas_geral(prs, dados_cobranca, dados_credito)
    _slide_encerramento(prs, "GERAL")
    return _salvar(prs)


# ============================================================
# HELPERS GERAIS
# ============================================================

def _nova_apresentacao():
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    return prs


def _salvar(prs) -> bytes:
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _rgb(hex6: str):
    from pptx.dml.color import RGBColor
    return RGBColor.from_string(hex6)


def _grafico_para_bytes(fig) -> Optional[bytes]:
    """
    Exporta figura Plotly como PNG usando matplotlib como fallback.
    Funciona sem kaleido no Streamlit Cloud.
    """
    # Tenta kaleido primeiro (mais fiel)
    try:
        return fig.to_image(format="png", width=900, height=420, scale=2)
    except Exception:
        pass

    # Fallback: converte Plotly → matplotlib → PNG
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.figure import Figure

        data = fig.data
        layout = fig.layout
        title = layout.title.text if layout.title and layout.title.text else ""

        fig_mpl, ax = plt.subplots(figsize=(10, 4.5))
        fig_mpl.patch.set_facecolor("white")
        ax.set_facecolor("white")

        plotted = False
        for trace in data:
            tipo = type(trace).__name__.lower()

            if "bar" in tipo:
                x = list(trace.x) if trace.x is not None else []
                y = list(trace.y) if trace.y is not None else []
                if not x or not y:
                    continue
                colors = _extrair_cor_plotly(trace)
                orientation = getattr(trace, "orientation", "v")
                if orientation == "h":
                    bars = ax.barh(x, y, color=colors, edgecolor="white", linewidth=0.5)
                    for bar, val in zip(bars, y):
                        if val and val > 0:
                            ax.text(bar.get_width() * 1.01, bar.get_y() + bar.get_height()/2,
                                   _fmt_val(val), va='center', ha='left', fontsize=8)
                else:
                    bars = ax.bar(x, y, color=colors, edgecolor="white", linewidth=0.5)
                    for bar, val in zip(bars, y):
                        if val and val > 0:
                            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.01,
                                   _fmt_val(val), ha='center', va='bottom', fontsize=8)
                plotted = True

            elif "pie" in tipo or "donut" in tipo:
                labels = list(trace.labels) if trace.labels is not None else []
                values = list(trace.values) if trace.values is not None else []
                if not labels or not values:
                    continue
                cores_pizza = ["#0F8C3B", "#0071FE", "#DC3545", "#FAC318", "#041747"]
                hole = getattr(trace, "hole", 0) or 0
                wedges, texts, autotexts = ax.pie(
                    values, labels=labels,
                    colors=cores_pizza[:len(values)],
                    autopct='%1.1f%%', startangle=90,
                    wedgeprops=dict(width=1-hole) if hole > 0 else {},
                    textprops={"fontsize": 9},
                )
                plotted = True

            elif "scatter" in tipo:
                x = list(trace.x) if trace.x is not None else []
                y = list(trace.y) if trace.y is not None else []
                if not x or not y:
                    continue
                mode = getattr(trace, "mode", "lines") or "lines"
                marker_color = "#0071FE"
                try:
                    mc = trace.marker.color if trace.marker and trace.marker.color else None
                    if mc and isinstance(mc, str) and mc.startswith("#"):
                        marker_color = mc
                except Exception:
                    pass
                if "lines" in mode:
                    ax.plot(x, y, color=marker_color, linewidth=2, marker="o" if "markers" in mode else "")
                elif "markers" in mode:
                    ax.scatter(x, y, color=marker_color, s=40)
                plotted = True

        if not plotted:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center",
                   transform=ax.transAxes, fontsize=12, color="#888")

        if title:
            ax.set_title(title, fontsize=11, fontweight="bold", pad=10, color="#041747")

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#DDD")
        ax.spines["bottom"].set_color("#DDD")
        ax.tick_params(labelsize=8, colors="#555")
        ax.yaxis.grid(True, color="#EEE", linewidth=0.5)
        ax.set_axisbelow(True)

        plt.tight_layout(pad=1.5)

        buf = io.BytesIO()
        fig_mpl.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                       facecolor="white", edgecolor="none")
        plt.close(fig_mpl)
        buf.seek(0)
        return buf.read()

    except Exception:
        return None


def _extrair_cor_plotly(trace) -> list:
    """Extrai cores de um trace Plotly para uso no matplotlib."""
    try:
        mc = trace.marker.color if trace.marker else None
        if isinstance(mc, str) and mc.startswith("#"):
            return [mc]
        if isinstance(mc, (list, tuple)):
            return [c if (isinstance(c, str) and c.startswith("#")) else "#0071FE" for c in mc]
    except Exception:
        pass
    return ["#0071FE"]


def _fmt_val(v) -> str:
    """Formata valor para rótulo nos gráficos."""
    try:
        f = float(v)
        if f >= 1_000_000:
            return f"R$ {f/1_000_000:.1f}M"
        if f >= 1_000:
            return f"R$ {f/1_000:.0f}K"
        if f < 10:
            return f"{f:.2f}"
        return f"R$ {f:,.0f}".replace(",", ".")
    except Exception:
        return str(v)


def _inserir_grafico(slide, fig, left, top, width, height):
    """Insere gráfico Plotly como imagem no slide."""
    img_bytes = _grafico_para_bytes(fig)
    if img_bytes:
        from pptx.util import Inches
        slide.shapes.add_picture(
            io.BytesIO(img_bytes), left, top, width, height
        )


def _brl(v) -> str:
    try:
        return f"R$ {float(v):,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0"


def _pct(v) -> str:
    try:
        return f"{float(v):.1f}%"
    except Exception:
        return "0%"


# ============================================================
# COMPONENTES DE SLIDE
# ============================================================

def _slide_capa(prs, titulo: str, periodo: str, subtitulo: str):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    w, h = prs.slide_width, prs.slide_height

    # Fundo azul escuro
    _retangulo(slide, 0, 0, w, h, AZUL)

    # Faixa amarela lateral esquerda
    _retangulo(slide, 0, 0, Inches(0.5), h, AMARELO)

    # Faixa inferior sutil
    _retangulo(slide, 0, h - Inches(0.08), w, Inches(0.08), AMARELO)

    # Título grande
    _texto(slide, titulo.upper(), Inches(1), Inches(2.2), Inches(11), Inches(1.2),
           Pt(44), BRANCO, bold=True)

    # Linha separadora
    _retangulo(slide, Inches(1), Inches(3.5), Inches(5), Inches(0.04), AMARELO)

    # Período
    _texto(slide, periodo, Inches(1), Inches(3.7), Inches(8), Inches(0.6),
           Pt(22), AMARELO, bold=True)

    # Subtítulo
    _texto(slide, subtitulo, Inches(1), Inches(4.4), Inches(10), Inches(0.5),
           Pt(14), "AAAAAA")

    # Rodapé
    _texto(slide, "GRUPO LLE  ·  Gestão Financeira 2026", Inches(1), Inches(6.8),
           Inches(10), Inches(0.4), Pt(10), AMARELO)


def _slide_kpis_cobranca(prs, dados: dict, periodo: str):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "RESUMO EXECUTIVO — COBRANÇA", periodo)

    ac = dados.get("acordos", {})
    bx = dados.get("baixas", {})
    pf = dados.get("performance", {})

    kpis = [
        ("Total Acordos", str(ac.get("total_acordos", 0)), "no período", AZUL_V),
        ("Valor Acordado", _brl(ac.get("valor_total", 0)), "acordos ativos", VERDE),
        ("Ticket Médio", _brl(ac.get("ticket_medio", 0)), "por acordo", AZUL_V),
        ("Total Recebido", _brl(bx.get("total_recebido", 0)), "cobrança baixada", VERDE),
        ("Cancelamentos", _pct(ac.get("pct_cancelamento", 0)), "dos acordos", VERMELHO),
        ("Aderência Média", _pct(pf.get("aderencia_media", 0)), "à meta de 2h/dia", AZUL_V),
    ]
    _grid_kpis(slide, kpis, top=Inches(1.6))


def _slide_kpis_credito(prs, dados: dict, periodo: str):
    from pptx.util import Inches
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "RESUMO EXECUTIVO — CRÉDITO", periodo)

    lib = dados.get("liberacoes", {})
    lim = dados.get("limites", {})

    kpis = [
        ("Total Pedidos", f"{lib.get('total', 0):,}".replace(",", "."), "processados", AZUL_V),
        ("Passaram Direto", _pct(lib.get("pct_direto", 0)), f"{lib.get('qtd_direto', 0):,} pedidos".replace(",", "."), VERDE),
        ("Liberados", _pct(lib.get("pct_liberados", 0)), f"{lib.get('qtd_liberados', 0):,} pedidos".replace(",", "."), AZUL_V),
        ("Negados", _pct(lib.get("pct_negados", 0)), f"{lib.get('qtd_negados', 0):,} pedidos".replace(",", "."), VERMELHO),
        ("Valor Aprovado", _brl(lib.get("vlr_aprovado", 0)), "direto + analista", VERDE),
        ("Reanálises Limite", str(lim.get("total", 0)), _brl(lim.get("total_variacao", 0)) + " concedido", AMARELO),
    ]
    _grid_kpis(slide, kpis, top=Inches(1.6))


def _slide_acordos_graficos(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "ÍNDICES DE ACORDO", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Gráfico esquerdo: valor por cobrador
        if "negociador" in df.columns and "valor_total" in df.columns:
            df_at = df[~df["cancelado"]] if "cancelado" in df.columns else df
            por_neg = df_at.groupby("negociador")["valor_total"].sum().reset_index().sort_values("valor_total")
            fig1 = go.Figure(go.Bar(
                x=por_neg["valor_total"], y=por_neg["negociador"],
                orientation="h",
                marker_color=f"#{AZUL_V}",
                text=[_brl(v) for v in por_neg["valor_total"]],
                textposition="outside",
            ))
            fig1.update_layout(
                title="Valor Acordado por Cobrador",
                height=380, margin=dict(l=10, r=80, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
                xaxis=dict(showgrid=True, gridcolor="#EEE"),
            )
            _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Gráfico direito: forma de pagamento
        if "forma_pagto" in df.columns:
            df_at = df[~df["cancelado"]] if "cancelado" in df.columns else df
            por_forma = df_at.groupby("forma_pagto").size().reset_index(name="qtd")
            fig2 = go.Figure(go.Pie(
                labels=por_forma["forma_pagto"],
                values=por_forma["qtd"],
                hole=0.45,
                marker_colors=[f"#{AZUL}", f"#{AZUL_V}", f"#{AMARELO}", f"#{VERDE}"],
            ))
            fig2.update_layout(
                title="Forma de Pagamento",
                height=380, margin=dict(l=10, r=10, t=40, b=10),
                font=dict(family="Arial", size=11),
            )
            _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_baixas_graficos(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "ÍNDICES DE COBRANÇA — BAIXAS", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df

        FAIXAS = ["0-30", "31-60", "60-91", "91-180", "181-360", "+360"]
        CORES_AGING = [f"#{VERDE}", f"#{AMARELO}", "#FF8C00", f"#{VERMELHO}", "#8B0000", "#4A0000"]

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Esquerdo: recebido por cobrador
        if "cobrador" in df.columns and "vlr_liquido" in df.columns:
            por_cob = df.groupby("cobrador")["vlr_liquido"].sum().reset_index().sort_values("vlr_liquido")
            fig1 = go.Figure(go.Bar(
                x=por_cob["vlr_liquido"], y=por_cob["cobrador"],
                orientation="h",
                marker_color=f"#{VERDE}",
                text=[_brl(v) for v in por_cob["vlr_liquido"]],
                textposition="outside",
            ))
            fig1.update_layout(
                title="Total Recebido por Cobrador",
                height=380, margin=dict(l=10, r=80, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
            )
            _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Direito: aging
        if "faixa_aging" in df.columns:
            aging = (
                df.dropna(subset=["faixa_aging"])
                .groupby("faixa_aging")["vlr_liquido"]
                .sum()
                .reindex(FAIXAS, fill_value=0)
                .reset_index()
            )
            fig2 = go.Figure(go.Bar(
                x=aging["faixa_aging"], y=aging["vlr_liquido"],
                marker_color=CORES_AGING,
                text=[_brl(v) for v in aging["vlr_liquido"]],
                textposition="outside",
            ))
            fig2.update_layout(
                title="Aging — Valor Recebido por Faixa de Atraso",
                height=380, margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
            )
            _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_performance_graficos(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches, Pt
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "ÍNDICES DE PERFORMANCE", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df
        df_ind = df[~df["cobrador"].str.upper().str.contains("EQUIPE|TOTAL", na=False)]

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Esquerdo: tempo médio vs meta
        if "tempo_medio_diario_h" in df_ind.columns:
            cores = [f"#{VERDE}" if v >= 2.0 else f"#{VERMELHO}"
                     for v in df_ind["tempo_medio_diario_h"]]
            fig1 = go.Figure()
            fig1.add_trace(go.Bar(
                x=df_ind["cobrador"], y=df_ind["tempo_medio_diario_h"],
                marker_color=cores,
                text=[f"{v:.2f}h" for v in df_ind["tempo_medio_diario_h"]],
                textposition="outside",
                name="Tempo Médio",
            ))
            fig1.add_hline(y=2.0, line_dash="dash", line_color=f"#{AMARELO}",
                           annotation_text="Meta 2h")
            fig1.update_layout(
                title="Tempo Médio Diário vs Meta (2h)",
                height=380, margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
                yaxis=dict(ticksuffix="h"),
            )
            _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Direito: valor total acordos
        if "total_acordos_valor" in df_ind.columns:
            df_sort = df_ind.sort_values("total_acordos_valor", ascending=True)
            fig2 = go.Figure(go.Bar(
                x=df_sort["total_acordos_valor"], y=df_sort["cobrador"],
                orientation="h",
                marker_color=f"#{AZUL_V}",
                text=[_brl(v) for v in df_sort["total_acordos_valor"]],
                textposition="outside",
            ))
            fig2.update_layout(
                title="Valor Total de Acordos por Cobrador",
                height=380, margin=dict(l=10, r=80, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
            )
            _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)

        # Tabela de aderência
        _slide_tabela_performance(prs, df_ind, periodo)
    except Exception:
        pass


def _slide_tabela_performance(prs, df, periodo: str):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "PERFORMANCE DETALHADA POR COBRADOR", periodo)

    try:
        y = Inches(1.7)
        colunas = ["cobrador", "tempo_medio_diario_h", "pct_aderencia",
                   "ocorrencias_media_dia", "acordos_media_dia", "total_acordos_valor"]
        headers = ["Cobrador", "Tempo Médio", "% Aderência", "Ocorr./dia", "Acordos/dia", "Total Acordos"]
        larguras = [Inches(2.5), Inches(1.6), Inches(1.6), Inches(1.6), Inches(1.6), Inches(2.2)]

        # Cabeçalho
        x = Inches(0.4)
        for i, (h, w) in enumerate(zip(headers, larguras)):
            cell = slide.shapes.add_shape(1, x, y, w, Inches(0.4))
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(AZUL)
            cell.line.fill.background()
            _texto(slide, h, x + Inches(0.05), y + Inches(0.05), w - Inches(0.1), Inches(0.3),
                   Pt(10), BRANCO, bold=True)
            x += w

        y += Inches(0.42)
        for idx, (_, row) in enumerate(df.iterrows()):
            x = Inches(0.4)
            bg = CINZA_F if idx % 2 == 0 else BRANCO
            ader = row.get("pct_aderencia", 0)
            ader_pct = ader * 100 if ader <= 1 else ader
            cor_ader = VERDE if ader_pct >= 100 else (AMARELO if ader_pct >= 80 else VERMELHO)

            valores = [
                str(row.get("cobrador", "")),
                f"{row.get('tempo_medio_diario_h', 0):.2f}h",
                f"{ader_pct:.1f}%",
                f"{row.get('ocorrencias_media_dia', 0):.0f}",
                f"{row.get('acordos_media_dia', 0):.2f}",
                _brl(row.get("total_acordos_valor", 0)),
            ]
            for i, (val, w) in enumerate(zip(valores, larguras)):
                cell = slide.shapes.add_shape(1, x, y, w, Inches(0.38))
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb(bg)
                cell.line.color.rgb = _rgb("DDDDDD")
                cor_txt = cor_ader if i == 2 else AZUL
                _texto(slide, val, x + Inches(0.05), y + Inches(0.04),
                       w - Inches(0.1), Inches(0.28), Pt(10), cor_txt)
                x += w
            y += Inches(0.4)
    except Exception:
        pass


def _slide_fluxo_pedidos_grafico(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "FLUXO DE PEDIDOS DE CRÉDITO", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df

        total = len(df)
        qtd_d = len(df[df["tipo"] == "DIRETO"])
        qtd_l = len(df[df["tipo"] == "LIBERADO"])
        qtd_n = len(df[df["tipo"] == "NEGADO"])

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Rosca
        fig1 = go.Figure(go.Pie(
            labels=["Passaram Direto", "Liberados (Analista)", "Negados"],
            values=[qtd_d, qtd_l, qtd_n],
            hole=0.5,
            marker_colors=[f"#{VERDE}", f"#{AZUL_V}", f"#{VERMELHO}"],
            textinfo="label+percent",
            textfont_size=12,
        ))
        fig1.update_layout(
            title=f"Distribuição de {total:,} pedidos".replace(",", "."),
            height=380, margin=dict(l=10, r=10, t=40, b=10),
            font=dict(family="Arial", size=11),
        )
        _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Valores
        vlr_d = float(df[df["tipo"] == "DIRETO"]["vlr_pedido"].sum())
        vlr_l = float(df[df["tipo"] == "LIBERADO"]["vlr_pedido"].sum())
        vlr_n = float(df[df["tipo"] == "NEGADO"]["vlr_pedido"].sum())

        fig2 = go.Figure(go.Bar(
            x=["Direto", "Liberado", "Negado"],
            y=[vlr_d, vlr_l, vlr_n],
            marker_color=[f"#{VERDE}", f"#{AZUL_V}", f"#{VERMELHO}"],
            text=[_brl(v) for v in [vlr_d, vlr_l, vlr_n]],
            textposition="outside",
        ))
        fig2.update_layout(
            title="Valor Total por Tipo de Pedido",
            height=380, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="white", showlegend=False,
            font=dict(family="Arial", size=11),
            yaxis=dict(showgrid=True, gridcolor="#EEE"),
        )
        _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_limites_grafico(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "REANÁLISES DE LIMITE DE CRÉDITO", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Consolidado
        tot_ant = float(df["limite_anterior"].sum())
        tot_novo = float(df["novo_limite"].sum())
        tot_var = float(df["variacao"].sum())

        fig1 = go.Figure(go.Bar(
            x=["Limite Anterior", "Novo Limite", "Variação"],
            y=[tot_ant, tot_novo, tot_var],
            marker_color=[f"#{AMARELO}", f"#{VERDE}", f"#{AZUL_V}"],
            text=[_brl(v) for v in [tot_ant, tot_novo, tot_var]],
            textposition="outside",
        ))
        fig1.update_layout(
            title="Consolidado de Limites",
            height=380, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="white", showlegend=False,
            font=dict(family="Arial", size=11),
        )
        _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Por analista
        if "analista" in df.columns:
            por_an = df.groupby("analista")["variacao"].sum().reset_index().sort_values("variacao")
            fig2 = go.Figure(go.Bar(
                x=por_an["variacao"], y=por_an["analista"],
                orientation="h",
                marker_color=f"#{VERDE}",
                text=[_brl(v) for v in por_an["variacao"]],
                textposition="outside",
            ))
            fig2.update_layout(
                title="Variação de Limite por Analista",
                height=380, margin=dict(l=10, r=80, t=40, b=10),
                plot_bgcolor="white", showlegend=False,
                font=dict(family="Arial", size=11),
            )
            _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_ranking_analistas_slide(prs, df, periodo: str):
    if df is None or (hasattr(df, "empty") and df.empty):
        return
    from pptx.util import Inches, Pt
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "RANKING DE ANALISTAS — LIBERAÇÕES", periodo)

    try:
        import pandas as pd
        df = pd.DataFrame(df) if isinstance(df, list) else df
        df_lib = df[df["tipo"] == "LIBERADO"].copy()

        if "analista" not in df_lib.columns or df_lib["analista"].isna().all():
            return

        ranking = (
            df_lib.dropna(subset=["analista"])
            .groupby("analista")
            .agg(qtd=("vlr_pedido", "count"), valor=("vlr_pedido", "sum"))
            .sort_values("qtd", ascending=False)
            .reset_index()
        )

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Qtd Liberações",
            x=ranking["analista"], y=ranking["qtd"],
            marker_color=f"#{AZUL_V}",
            text=ranking["qtd"], textposition="outside",
            yaxis="y",
        ))
        fig.add_trace(go.Scatter(
            name="Valor Liberado",
            x=ranking["analista"], y=ranking["valor"],
            mode="lines+markers",
            line=dict(color=f"#{VERDE}", width=2.5),
            marker=dict(size=8),
            yaxis="y2",
        ))
        fig.update_layout(
            title="Qtd de Liberações e Valor por Analista",
            height=420, margin=dict(l=10, r=80, t=40, b=10),
            plot_bgcolor="white",
            font=dict(family="Arial", size=11),
            yaxis=dict(title="Liberações", showgrid=True, gridcolor="#EEE"),
            yaxis2=dict(title="Valor (R$)", overlaying="y", side="right",
                        tickprefix="R$ ", tickformat=",.0f"),
            legend=dict(orientation="h", y=-0.15),
        )
        _inserir_grafico(slide, fig, Inches(0.4), Inches(1.6), Inches(12.5), Inches(5.2))
    except Exception:
        pass


def _slide_destaques_cobranca(prs, dados: dict, periodo: str):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "DESTAQUES DO PERÍODO", periodo)

    ac = dados.get("acordos", {})
    bx = dados.get("baixas", {})
    pf = dados.get("performance", {})

    destaques = []

    # Acordos
    if ac.get("total_acordos"):
        destaques.append(("📋 Acordos", f"{ac['total_acordos']} acordos realizados · Total de {_brl(ac.get('valor_total', 0))} · Ticket médio {_brl(ac.get('ticket_medio', 0))}", AZUL_V))

    # Cancelamentos
    pct_c = ac.get("pct_cancelamento", 0)
    if pct_c > 10:
        destaques.append(("⚠ Atenção", f"Taxa de cancelamento em {_pct(pct_c)} — acima da faixa ideal", VERMELHO))
    elif pct_c > 0:
        destaques.append(("✓ Cancelamentos", f"Taxa de cancelamento controlada: {_pct(pct_c)}", VERDE))

    # Cobrança
    if bx.get("total_recebido"):
        destaques.append(("💰 Recebimento", f"{_brl(bx['total_recebido'])} recebidos · {bx.get('total_baixas', 0):,} baixas · Dias médios de atraso: {bx.get('dias_medio_atraso', 0):.0f}".replace(",", "."), VERDE))

    # Performance
    ader = pf.get("aderencia_media", 0)
    if ader:
        ader_pct = ader * 100 if ader <= 1 else ader
        cor = VERDE if ader_pct >= 100 else (AMARELO if ader_pct >= 80 else VERMELHO)
        destaques.append(("⚡ Performance", f"Aderência média à meta de 2h/dia: {_pct(ader_pct)} · Top cobrador: {pf.get('top_cobrador', '-')}", cor))

    _lista_destaques(slide, destaques)


def _slide_destaques_credito(prs, dados: dict, periodo: str):
    from pptx.util import Inches
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "DESTAQUES DO PERÍODO", periodo)

    lib = dados.get("liberacoes", {})
    lim = dados.get("limites", {})

    destaques = []

    if lib.get("total"):
        destaques.append(("💳 Fluxo", f"{lib['total']:,} pedidos · Direto: {_pct(lib.get('pct_direto', 0))} · Analista: {_pct(lib.get('pct_liberados', 0))}".replace(",", "."), AZUL_V))

    pct_neg = lib.get("pct_negados", 0)
    if pct_neg > 2:
        destaques.append(("⚠ Negados", f"Taxa de negação em {_pct(pct_neg)} — monitorar", VERMELHO))
    else:
        destaques.append(("✓ Negados", f"Taxa de negação controlada: {_pct(pct_neg)}", VERDE))

    if lib.get("vlr_aprovado"):
        destaques.append(("💵 Valor", f"Total aprovado: {_brl(lib['vlr_aprovado'])} · Negado: {_brl(lib.get('vlr_negado', 0))}", VERDE))

    if lim.get("total"):
        destaques.append(("🔄 Limites", f"{lim['total']} reanálises · {_brl(lim.get('total_variacao', 0))} de aumento concedido", AZUL_V))

    _lista_destaques(slide, destaques)


# ============================================================
# PPT GERAL
# ============================================================

def _slide_resumo_executivo(prs, dados_cob: list, dados_cred: list):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "RESUMO EXECUTIVO CONSOLIDADO", "Todos os Períodos")

    # Totais gerais
    total_acordos = sum(d.get("acordos", {}).get("total_acordos", 0) for d in dados_cob)
    total_recebido = sum(d.get("baixas", {}).get("total_recebido", 0) for d in dados_cob)
    total_pedidos = sum(d.get("liberacoes", {}).get("total", 0) for d in dados_cred)
    total_reanalises = sum(d.get("limites", {}).get("total", 0) for d in dados_cred)
    meses_cob = len(dados_cob)
    meses_cred = len(dados_cred)

    kpis = [
        ("Meses Cobrança", str(meses_cob), "períodos carregados", AZUL_V),
        ("Total Acordos", str(total_acordos), "em todos os meses", VERDE),
        ("Total Recebido", _brl(total_recebido), "cobrança acumulada", VERDE),
        ("Meses Crédito", str(meses_cred), "períodos carregados", AZUL_V),
        ("Total Pedidos", f"{total_pedidos:,}".replace(",", "."), "processados", AZUL_V),
        ("Reanálises Limite", str(total_reanalises), "em todos os meses", AMARELO),
    ]
    _grid_kpis(slide, kpis, top=Inches(1.6))


def _slide_evolucao_cobranca(prs, dados_cob: list):
    if not dados_cob:
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "EVOLUÇÃO DE COBRANÇA — MÊS A MÊS", "Histórico Completo")

    try:
        meses = [d.get("mes_label", "") for d in dados_cob]
        valores = [d.get("acordos", {}).get("valor_total", 0) for d in dados_cob]
        recebidos = [d.get("baixas", {}).get("total_recebido", 0) for d in dados_cob]
        cancelamentos = [d.get("acordos", {}).get("pct_cancelamento", 0) for d in dados_cob]

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Valor acordado mês a mês
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=meses, y=valores, name="Valor Acordado",
                              marker_color=f"#{AZUL_V}", text=[_brl(v) for v in valores],
                              textposition="outside"))
        fig1.add_trace(go.Scatter(x=meses, y=recebidos, name="Total Recebido",
                                  mode="lines+markers",
                                  line=dict(color=f"#{VERDE}", width=2.5),
                                  marker=dict(size=8), yaxis="y"))
        fig1.update_layout(
            title="Valor Acordado vs Total Recebido",
            height=400, margin=dict(l=10, r=10, t=40, b=30),
            plot_bgcolor="white", barmode="group",
            font=dict(family="Arial", size=10),
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(showgrid=True, gridcolor="#EEE"),
        )
        _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # % cancelamento mês a mês
        cores = [f"#{VERDE}" if v <= 10 else f"#{VERMELHO}" for v in cancelamentos]
        fig2 = go.Figure(go.Bar(
            x=meses, y=cancelamentos,
            marker_color=cores,
            text=[_pct(v) for v in cancelamentos],
            textposition="outside",
        ))
        fig2.add_hline(y=10, line_dash="dash", line_color=f"#{AMARELO}",
                       annotation_text="Limite 10%")
        fig2.update_layout(
            title="Taxa de Cancelamento (%)",
            height=400, margin=dict(l=10, r=10, t=40, b=30),
            plot_bgcolor="white", showlegend=False,
            font=dict(family="Arial", size=10),
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#EEE"),
        )
        _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_evolucao_credito(prs, dados_cred: list):
    if not dados_cred:
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "EVOLUÇÃO DE CRÉDITO — MÊS A MÊS", "Histórico Completo")

    try:
        meses = [d.get("mes_label", "") for d in dados_cred]
        pct_direto = [d.get("liberacoes", {}).get("pct_direto", 0) for d in dados_cred]
        pct_negados = [d.get("liberacoes", {}).get("pct_negados", 0) for d in dados_cred]
        reanalises = [d.get("limites", {}).get("total", 0) for d in dados_cred]
        variacoes = [d.get("limites", {}).get("total_variacao", 0) for d in dados_cred]

        col_l, col_r = Inches(0.4), Inches(6.9)
        w_g, h_g = Inches(6.2), Inches(4.8)

        # Tendência direto vs negados
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=meses, y=pct_direto, name="% Direto",
                                  mode="lines+markers+text",
                                  line=dict(color=f"#{VERDE}", width=2.5),
                                  text=[_pct(v) for v in pct_direto],
                                  textposition="top center"))
        fig1.add_trace(go.Scatter(x=meses, y=pct_negados, name="% Negados",
                                  mode="lines+markers+text",
                                  line=dict(color=f"#{VERMELHO}", width=2, dash="dot"),
                                  text=[_pct(v) for v in pct_negados],
                                  textposition="bottom center"))
        fig1.update_layout(
            title="Tendência: % Direto vs % Negados",
            height=400, margin=dict(l=10, r=10, t=40, b=30),
            plot_bgcolor="white",
            font=dict(family="Arial", size=10),
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#EEE"),
        )
        _inserir_grafico(slide, fig1, col_l, Inches(1.6), w_g, h_g)

        # Evolução de reanálises e variação
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=meses, y=reanalises, name="Qtd Reanálises",
                              marker_color=f"#{AZUL_V}", text=reanalises,
                              textposition="outside", yaxis="y"))
        fig2.add_trace(go.Scatter(x=meses, y=variacoes, name="Variação de Limite (R$)",
                                  mode="lines+markers",
                                  line=dict(color=f"#{VERDE}", width=2.5),
                                  marker=dict(size=8), yaxis="y2"))
        fig2.update_layout(
            title="Reanálises de Limite e Variação Concedida",
            height=400, margin=dict(l=10, r=80, t=40, b=30),
            plot_bgcolor="white",
            font=dict(family="Arial", size=10),
            legend=dict(orientation="h", y=-0.2),
            yaxis=dict(showgrid=True, gridcolor="#EEE"),
            yaxis2=dict(overlaying="y", side="right",
                        tickprefix="R$ ", tickformat=",.0f"),
        )
        _inserir_grafico(slide, fig2, col_r, Inches(1.6), w_g, h_g)
    except Exception:
        pass


def _slide_comparativo_cobradores(prs, dados_cob: list):
    if not dados_cob:
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "DESEMPENHO POR COBRADOR — HISTÓRICO", "Acumulado")

    try:
        # Agrega por cobrador em todos os meses
        from collections import defaultdict
        por_cob = defaultdict(lambda: {"valor": 0, "acordos": 0, "recebido": 0})

        for d in dados_cob:
            df_ac = d.get("df_acordos")
            df_bx = d.get("df_baixas")
            if df_ac is not None and hasattr(df_ac, "iterrows"):
                import pandas as pd
                df_ac = pd.DataFrame(df_ac) if isinstance(df_ac, list) else df_ac
                if "negociador" in df_ac.columns and "valor_total" in df_ac.columns:
                    for cob, g in df_ac.groupby("negociador"):
                        por_cob[cob]["valor"] += g["valor_total"].sum()
                        por_cob[cob]["acordos"] += len(g)
            if df_bx is not None and hasattr(df_bx, "iterrows"):
                df_bx = pd.DataFrame(df_bx) if isinstance(df_bx, list) else df_bx
                if "cobrador" in df_bx.columns and "vlr_liquido" in df_bx.columns:
                    for cob, g in df_bx.groupby("cobrador"):
                        por_cob[cob]["recebido"] += g["vlr_liquido"].sum()

        if not por_cob:
            return

        cobradores = list(por_cob.keys())
        valores = [por_cob[c]["valor"] for c in cobradores]
        recebidos = [por_cob[c]["recebido"] for c in cobradores]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Valor Acordado", x=cobradores, y=valores,
                             marker_color=f"#{AZUL_V}",
                             text=[_brl(v) for v in valores], textposition="outside"))
        fig.add_trace(go.Bar(name="Total Recebido", x=cobradores, y=recebidos,
                             marker_color=f"#{VERDE}",
                             text=[_brl(v) for v in recebidos], textposition="outside"))
        fig.update_layout(
            title="Valor Acordado vs Total Recebido por Cobrador (Acumulado)",
            height=440, barmode="group",
            margin=dict(l=10, r=10, t=40, b=30),
            plot_bgcolor="white",
            font=dict(family="Arial", size=11),
            legend=dict(orientation="h", y=-0.15),
            yaxis=dict(showgrid=True, gridcolor="#EEE"),
        )
        _inserir_grafico(slide, fig, Inches(0.4), Inches(1.6), Inches(12.5), Inches(5.5))
    except Exception:
        pass


def _slide_comparativo_analistas(prs, dados_cred: list):
    if not dados_cred:
        return
    from pptx.util import Inches
    import plotly.graph_objects as go

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "DESEMPENHO POR ANALISTA — HISTÓRICO", "Acumulado")

    try:
        from collections import defaultdict
        import pandas as pd

        por_analista = defaultdict(lambda: {"qtd": 0, "valor": 0})
        for d in dados_cred:
            df_lib = d.get("df_liberacoes")
            if df_lib is not None:
                df_lib = pd.DataFrame(df_lib) if isinstance(df_lib, list) else df_lib
                df_lib_f = df_lib[df_lib["tipo"] == "LIBERADO"] if "tipo" in df_lib.columns else df_lib
                if "analista" in df_lib_f.columns:
                    for an, g in df_lib_f.dropna(subset=["analista"]).groupby("analista"):
                        por_analista[an]["qtd"] += len(g)
                        por_analista[an]["valor"] += g["vlr_pedido"].sum() if "vlr_pedido" in g.columns else 0

        if not por_analista:
            return

        analistas = list(por_analista.keys())
        qtds = [por_analista[a]["qtd"] for a in analistas]
        valores = [por_analista[a]["valor"] for a in analistas]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Qtd Liberações", x=analistas, y=qtds,
                             marker_color=f"#{AZUL_V}",
                             text=qtds, textposition="outside", yaxis="y"))
        fig.add_trace(go.Scatter(name="Valor Liberado", x=analistas, y=valores,
                                 mode="lines+markers",
                                 line=dict(color=f"#{VERDE}", width=2.5),
                                 marker=dict(size=8), yaxis="y2"))
        fig.update_layout(
            title="Liberações e Valor por Analista (Acumulado)",
            height=440, margin=dict(l=10, r=80, t=40, b=30),
            plot_bgcolor="white",
            font=dict(family="Arial", size=11),
            legend=dict(orientation="h", y=-0.15),
            yaxis=dict(showgrid=True, gridcolor="#EEE"),
            yaxis2=dict(overlaying="y", side="right",
                        tickprefix="R$ ", tickformat=",.0f"),
        )
        _inserir_grafico(slide, fig, Inches(0.4), Inches(1.6), Inches(12.5), Inches(5.5))
    except Exception:
        pass


def _slide_alertas_geral(prs, dados_cob: list, dados_cred: list):
    from pptx.util import Inches
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _fundo_slide(slide, prs)
    _cabecalho_slide(slide, "ALERTAS E PONTOS DE ATENÇÃO", "Análise Global")

    alertas = []
    ok = []

    # Analisa cobrança
    for d in dados_cob:
        mes = d.get("mes_label", "")
        pct_c = d.get("acordos", {}).get("pct_cancelamento", 0)
        dias_atraso = d.get("baixas", {}).get("dias_medio_atraso", 0)
        ader = d.get("performance", {}).get("aderencia_media", 0)
        ader_pct = ader * 100 if ader and ader <= 1 else (ader or 0)

        if pct_c > 15:
            alertas.append(f"⚠ {mes}: Cancelamentos em {_pct(pct_c)} — acima do limite")
        if dias_atraso > 60:
            alertas.append(f"⚠ {mes}: Dias médios de atraso em {dias_atraso:.0f} dias")
        if ader_pct > 0 and ader_pct < 80:
            alertas.append(f"⚠ {mes}: Aderência à meta abaixo de 80% ({_pct(ader_pct)})")
        if pct_c <= 10 and ader_pct >= 90:
            ok.append(f"✓ {mes}: Cobrança com bom desempenho")

    # Analisa crédito
    for d in dados_cred:
        mes = d.get("mes_label", "")
        pct_neg = d.get("liberacoes", {}).get("pct_negados", 0)
        pct_dir = d.get("liberacoes", {}).get("pct_direto", 0)

        if pct_neg > 2:
            alertas.append(f"⚠ {mes}: Taxa de negados em {_pct(pct_neg)} — monitorar")
        if pct_dir < 70:
            alertas.append(f"⚠ {mes}: Liberação direta abaixo de 70% ({_pct(pct_dir)})")
        if pct_neg <= 1.5 and pct_dir >= 75:
            ok.append(f"✓ {mes}: Crédito com bom desempenho")

    destaques = [(a, "", VERMELHO) for a in alertas[:5]]
    destaques += [(o, "", VERDE) for o in ok[:4]]

    if not destaques:
        destaques = [("✓ Sem alertas críticos identificados no período", "", VERDE)]

    _lista_destaques(slide, destaques)


# ============================================================
# COMPONENTES REUTILIZÁVEIS
# ============================================================

def _fundo_slide(slide, prs):
    from pptx.util import Inches
    # Fundo branco
    _retangulo(slide, 0, 0, prs.slide_width, prs.slide_height, BRANCO)
    # Faixa azul no topo
    _retangulo(slide, 0, 0, prs.slide_width, Inches(1.4), AZUL)
    # Linha amarela no topo
    _retangulo(slide, 0, Inches(1.38), prs.slide_width, Inches(0.04), AMARELO)
    # Faixa lateral esquerda
    _retangulo(slide, 0, 0, Inches(0.08), prs.slide_height, AMARELO)


def _cabecalho_slide(slide, titulo: str, subtitulo: str):
    from pptx.util import Inches, Pt
    _texto(slide, titulo, Inches(0.3), Inches(0.12), Inches(10), Inches(0.7),
           Pt(20), BRANCO, bold=True)
    _texto(slide, subtitulo, Inches(0.3), Inches(0.82), Inches(10), Inches(0.4),
           Pt(11), AMARELO)
    # Logo texto no canto
    _texto(slide, "GRUPO LLE", Inches(10.5), Inches(0.25), Inches(2.5), Inches(0.4),
           Pt(12), AMARELO, bold=True)


def _grid_kpis(slide, kpis: list, top):
    from pptx.util import Inches, Pt, Emu
    cols = 3
    card_w = Inches(3.9)
    card_h = Inches(1.5)
    gap_x = Inches(0.27)
    gap_y = Inches(0.2)
    start_x = Inches(0.3)

    for i, (label, valor, sub, cor) in enumerate(kpis):
        row = i // cols
        col = i % cols
        x = start_x + col * (card_w + gap_x)
        y = top + row * (card_h + gap_y)

        # Card
        card = slide.shapes.add_shape(1, x, y, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = _rgb(CINZA_F)
        card.line.color.rgb = _rgb(cor)
        card.line.width = Emu(25400)

        # Barra colorida no topo do card
        barra = slide.shapes.add_shape(1, x, y, card_w, Inches(0.07))
        barra.fill.solid()
        barra.fill.fore_color.rgb = _rgb(cor)
        barra.line.fill.background()

        # Label
        _texto(slide, label, x + Inches(0.15), y + Inches(0.12),
               card_w - Inches(0.3), Inches(0.35), Pt(11), CINZA_M)

        # Valor
        _texto(slide, valor, x + Inches(0.15), y + Inches(0.5),
               card_w - Inches(0.3), Inches(0.6), Pt(24), cor, bold=True)

        # Sublabel
        _texto(slide, sub, x + Inches(0.15), y + Inches(1.15),
               card_w - Inches(0.3), Inches(0.25), Pt(9), CINZA_M)


def _lista_destaques(slide, destaques: list):
    from pptx.util import Inches, Pt, Emu

    y = Inches(1.7)
    for texto, sub, cor in destaques[:7]:
        # Linha colorida
        linha = slide.shapes.add_shape(1, Inches(0.3), y, Inches(0.06), Inches(0.5))
        linha.fill.solid()
        linha.fill.fore_color.rgb = _rgb(cor)
        linha.line.fill.background()

        # Fundo card
        card = slide.shapes.add_shape(1, Inches(0.5), y, Inches(12.4), Inches(0.52))
        card.fill.solid()
        card.fill.fore_color.rgb = _rgb(CINZA_F)
        card.line.fill.background()

        _texto(slide, texto, Inches(0.7), y + Inches(0.06),
               Inches(12), Inches(0.4), Pt(12), AZUL)

        y += Inches(0.6)


def _slide_encerramento(prs, area: str):
    from pptx.util import Inches, Pt
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    w, h = prs.slide_width, prs.slide_height
    _retangulo(slide, 0, 0, w, h, AZUL)
    _retangulo(slide, 0, 0, Inches(0.5), h, AMARELO)
    _retangulo(slide, 0, h - Inches(0.08), w, Inches(0.08), AMARELO)

    _texto(slide, "Obrigado.", Inches(1.5), Inches(2.8), Inches(10), Inches(1.2),
           Pt(54), BRANCO, bold=True)
    _texto(slide, f"Equipe de {area.title()}  ·  Grupo LLE Ferragens",
           Inches(1.5), Inches(4.2), Inches(10), Inches(0.5), Pt(16), AMARELO)
    _texto(slide, "GRUPO LLE  ·  Gestão Financeira",
           Inches(1.5), Inches(6.6), Inches(10), Inches(0.4), Pt(11), "AAAAAA")


# ============================================================
# PRIMITIVAS DE DESENHO
# ============================================================

def _retangulo(slide, x, y, w, h, cor_hex: str):
    shape = slide.shapes.add_shape(1, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(cor_hex)
    shape.line.fill.background()
    return shape


def _texto(slide, texto: str, x, y, w, h, tamanho, cor_hex: str, bold: bool = False):
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    tx = slide.shapes.add_textbox(x, y, w, h)
    tf = tx.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = str(texto)
    p.font.size = tamanho
    p.font.bold = bold
    p.font.color.rgb = _rgb(cor_hex)
    try:
        p.font.name = "Calibri"
    except Exception:
        pass
    return tx
