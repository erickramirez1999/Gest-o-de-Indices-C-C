"""Atendimento · Dashboard (Cobrança) — por período, tipo (motivo) e linha do tempo."""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.banco import repo_atendimento
from src.utils.marca import AZUL_ESCURO, AMARELO, VERDE
from src.utils.formatadores import formatar_inteiro, nome_mes

AZUL = "#0071FE"
MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _card(col, titulo, valor, sub, cor):
    col.markdown(
        f"<div style='border:1px solid #E8EDF5;border-left:5px solid {cor};border-radius:8px;padding:12px 14px;'>"
        f"<div style='font-size:12px;color:#6C757D;font-weight:600'>{titulo}</div>"
        f"<div style='font-size:22px;font-weight:700;color:{cor}'>{valor}</div>"
        f"<div style='font-size:11px;color:#6C757D'>{sub}</div></div>", unsafe_allow_html=True)


def renderizar_atend_dashboard(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>💬 Atendimento · Indicadores</h1>", unsafe_allow_html=True)

    anos = repo_atendimento.listar_anos()
    if not anos:
        st.info("📭 Nenhum dado de atendimento ainda. Faça o upload do CSV em **Atendimento · Upload**.")
        return

    c1, c2 = st.columns([1, 2])
    opcoes_ano = ["Todos os anos"] + [str(a) for a in anos]
    ano_esc = c1.selectbox("Ano", opcoes_ano, index=0)
    todos = ano_esc == "Todos os anos"

    dados = repo_atendimento.buscar_atendimentos(None if todos else int(ano_esc))
    df = pd.DataFrame(dados)
    if df.empty:
        st.warning("Sem dados para este período.")
        return
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0).astype(int)
    df["mes"] = df["data"].dt.month

    if todos:
        c2.selectbox("Período", ["Toda a vida"], index=0)
        d = df
        titulo_periodo = "Toda a vida"
        modo_timeline = "ano"
    else:
        ano = int(ano_esc)
        meses_disp = sorted(df["mes"].dropna().unique())
        opcoes = ["Ano inteiro"] + [f"{MESES[m-1]}/{ano}" for m in meses_disp]
        escolha = c2.selectbox("Período", opcoes, index=0)
        if escolha == "Ano inteiro":
            d = df
            titulo_periodo = f"Ano {ano}"
            modo_timeline = "mes"
        else:
            mes_sel = meses_disp[opcoes.index(escolha) - 1]
            d = df[df["mes"] == mes_sel]
            titulo_periodo = escolha
            modo_timeline = "dia"

    total = int(d["total"].sum())
    n_motivos = d["motivo"].nunique()
    dias_ativos = d["data"].dt.date.nunique()
    media_dia = total / dias_ativos if dias_ativos else 0

    cols = st.columns(4)
    _card(cols[0], "Total de finalizações", formatar_inteiro(total), titulo_periodo, AZUL_ESCURO)
    _card(cols[1], "Tipos de atendimento", str(n_motivos), "motivos distintos", AZUL)
    _card(cols[2], "Dias com atendimento", formatar_inteiro(dias_ativos), "no período", VERDE)
    _card(cols[3], "Média por dia", formatar_inteiro(round(media_dia)), "finalizações/dia", AMARELO)

    # ---- por tipo de atendimento (motivo) ----
    st.markdown("<br>", unsafe_allow_html=True)
    if todos and len(anos) >= 2:
        _comparativo(df, sorted(anos))
    else:
        st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Por tipo de atendimento</h3>", unsafe_allow_html=True)
        por_motivo = d.groupby("motivo")["total"].sum().sort_values(ascending=False)
        fig = go.Figure(go.Bar(
            x=por_motivo.values[::-1], y=por_motivo.index[::-1], orientation="h",
            marker_color=AZUL, text=[formatar_inteiro(v) for v in por_motivo.values[::-1]],
            textposition="outside"))
        fig.update_layout(height=max(320, 26 * len(por_motivo)), margin=dict(l=10, r=30, t=10, b=10),
                          xaxis_title="Finalizações", plot_bgcolor="white", font=dict(size=12))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        tab = por_motivo.reset_index()
        tab.columns = ["Motivo", "Total"]
        tab["%"] = (tab["Total"] / total * 100).round(1).astype(str) + "%"
        tab["Total"] = tab["Total"].map(formatar_inteiro)
        st.dataframe(tab, use_container_width=True, hide_index=True)

    # ---- linha do tempo ----
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Linha do tempo</h3>", unsafe_allow_html=True)
    if modo_timeline == "ano":
        serie = df.groupby("ano")["total"].sum().sort_index()
        x = [str(a) for a in serie.index]
        y = serie.values
        titulo_x = "Ano"
    elif modo_timeline == "mes":
        serie = d.groupby("mes")["total"].sum().reindex(range(1, 13), fill_value=0)
        x = [MESES[m-1] for m in serie.index]
        y = serie.values
        titulo_x = "Mês"
    else:
        serie = d.groupby(d["data"].dt.date)["total"].sum().sort_index()
        x = [pd.Timestamp(dt).strftime("%d/%m") for dt in serie.index]
        y = serie.values
        titulo_x = "Dia"
    figl = go.Figure(go.Scatter(x=x, y=y, mode="lines+markers", line=dict(color=AZUL_ESCURO, width=2.5),
                                marker=dict(size=6, color=AMARELO), fill="tozeroy",
                                fillcolor="rgba(4,23,71,0.08)"))
    figl.update_layout(height=340, margin=dict(l=10, r=10, t=10, b=10), xaxis_title=titulo_x,
                       yaxis_title="Finalizações", plot_bgcolor="white", font=dict(size=12))
    st.plotly_chart(figl, use_container_width=True, config={"displayModeBar": False})


def _comparativo(df, anos):
    """Comparativo por motivo entre anos: totais por ano, variação e onde cresceu/diminuiu."""
    st.markdown(f"<h3 style='color:{AZUL_ESCURO}'>Comparativo por tipo de atendimento (ano a ano)</h3>", unsafe_allow_html=True)

    piv = df.pivot_table(index="motivo", columns="ano", values="total", aggfunc="sum", fill_value=0)
    for a in anos:
        if a not in piv.columns:
            piv[a] = 0
    piv = piv[anos]
    ult, pen = anos[-1], anos[-2]
    piv["delta"] = piv[ult] - piv[pen]
    piv["delta_pct"] = piv.apply(lambda r: (r["delta"] / r[pen] * 100) if r[pen] else (100.0 if r["delta"] > 0 else 0.0), axis=1)
    piv = piv.sort_values(ult, ascending=False)

    # tabela
    linhas = []
    for motivo in piv.index:
        reg = {"Motivo": motivo}
        for a in anos:
            reg[str(a)] = formatar_inteiro(int(piv.loc[motivo, a]))
        d_abs = int(piv.loc[motivo, "delta"])
        d_pct = piv.loc[motivo, "delta_pct"]
        seta = "▲" if d_abs > 0 else ("▼" if d_abs < 0 else "—")
        reg[f"Variação {pen}→{ult}"] = f"{seta} {formatar_inteiro(abs(d_abs))} ({d_pct:+.0f}%)"
        linhas.append(reg)
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    st.caption(f"Variação = {ult} comparado a {pen}. Atenção: anos parciais podem distorcer a comparação.")

    # gráfico divergente: onde cresceu (verde) / diminuiu (vermelho)
    st.markdown(f"<h4 style='color:{AZUL_ESCURO}'>Onde cresceu e onde diminuiu ({pen} → {ult})</h4>", unsafe_allow_html=True)
    dd = piv.sort_values("delta")
    cores = [VERDE if v > 0 else ("#DC3545" if v < 0 else "#9AA5B1") for v in dd["delta"].values]
    figd = go.Figure(go.Bar(
        x=dd["delta"].values, y=dd.index, orientation="h", marker_color=cores,
        text=[f"{'+' if v>0 else ''}{formatar_inteiro(int(v))}" for v in dd["delta"].values],
        textposition="outside"))
    figd.update_layout(height=max(340, 28 * len(dd)), margin=dict(l=10, r=40, t=10, b=10),
                       xaxis_title=f"Diferença de finalizações ({pen} → {ult})",
                       plot_bgcolor="white", font=dict(size=12))
    figd.add_vline(x=0, line_width=1, line_color="#9AA5B1")
    st.plotly_chart(figd, use_container_width=True, config={"displayModeBar": False})
