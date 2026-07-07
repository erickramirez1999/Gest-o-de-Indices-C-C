"""
Tela Inadimplência · Dashboard (acompanhamento da diretoria).

Filtro por mês. Três visões: King+Trio, PISA e Geral. Listagem ordenada por
maior dívida, com filtro por situação e selo de protesto. Valor vem do
"Em Aberto"; situação, do histórico.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.banco import repo_inadimplencia
from src.utils.formatadores import formatar_brl, nome_mes
from src.utils.estilo import card_kpi

AZUL = "#041747"      # PISA
AMARELO = "#FAC318"   # KING+TRIO
VERDE = "#0F8C3B"
VERMELHO = "#DC3545"
CINZA = "#6C757D"

COR_GRUPO = {"PISA": AZUL, "KING_TRIO": AMARELO}
NOME_GRUPO = {"PISA": "PISA", "KING_TRIO": "King + Trio"}
COR_SIT = {
    "Acordo": VERDE, "Ação Judicial": "#7B1FA2", "Terceirizada": "#0071FE",
    "Quebra de Acordo": VERMELHO, "Devolvido pela Terceirizada": "#E67E22",
    "Sem Registro": CINZA,
}
SITUACOES = ["Acordo", "Ação Judicial", "Terceirizada", "Quebra de Acordo",
             "Devolvido pela Terceirizada", "Sem Registro"]
TOP_N = 40


def renderizar_inad_dashboard(usuario):
    st.markdown(f"<h1 style='color:{AZUL}'>🔴 Inadimplência · Top {TOP_N}</h1>", unsafe_allow_html=True)
    st.caption("Dívida em aberto e situação dos maiores inadimplentes — PISA, King+Trio e Geral.")

    if repo_inadimplencia.contar_inadimplencia() == 0:
        st.info("📭 Nenhum dado carregado ainda. Vá em **📥 Carregar** e suba as planilhas do mês.")
        return

    refs = repo_inadimplencia.listar_referencias()
    mes_sel = st.selectbox("Mês", refs, index=0, format_func=nome_mes) if len(refs) > 1 else refs[0]
    if len(refs) == 1:
        st.caption(f"Mês: {nome_mes(mes_sel)}")

    dados = repo_inadimplencia.buscar_inadimplencia(mes_sel)
    if not dados:
        st.warning("Sem dados para este mês.")
        return
    df = pd.DataFrame(dados)
    df["valor_em_aberto"] = pd.to_numeric(df["valor_em_aberto"], errors="coerce").fillna(0.0)
    for b in ("tem_quebra", "tem_protesto"):
        df[b] = df[b].fillna(False).astype(bool)

    aba_kt, aba_pisa, aba_geral = st.tabs(["🔺 King + Trio", "🏢 PISA", "📊 Geral"])
    with aba_kt:
        _view(df[df["grupo"] == "KING_TRIO"].copy(), "KING_TRIO", key="kt")
    with aba_pisa:
        _view(df[df["grupo"] == "PISA"].copy(), "PISA", key="pisa")
    with aba_geral:
        _view_geral(df, key="geral")


# ============================================================

def _kpis_topo(g: pd.DataFrame, cor: str):
    top = g.head(TOP_N)
    total = g["valor_em_aberto"].sum()
    total_top = top["valor_em_aberto"].sum()
    n_acordo = int((top["situacao"] == "Acordo").sum())
    n_terc = int((top["situacao"] == "Terceirizada").sum())
    n_jud = int((top["situacao"] == "Ação Judicial").sum())
    n_prot = int(top["tem_protesto"].sum())
    linha1 = [
        ("Dívida Top 40", formatar_brl(total_top), f"{len(top)} clientes", cor),
        ("Em acordo", str(n_acordo), "clientes no Top 40", VERDE),
        ("Na terceirizada", str(n_terc), "clientes no Top 40", "#0071FE"),
    ]
    linha2 = [
        ("Ação judicial", str(n_jud), "clientes no Top 40", "#7B1FA2"),
        ("Protestados", str(n_prot), "com selo de protesto", VERMELHO),
        ("Maior devedor", formatar_brl(g.iloc[0]["valor_em_aberto"]) if len(g) else "—",
         (g.iloc[0]["nome_cliente"][:22] if len(g) else ""), cor),
    ]
    for linha in (linha1, linha2):
        cols = st.columns(3)
        for col, (t, v, s, c) in zip(cols, linha):
            with col:
                st.markdown(card_kpi(t, v, s, c), unsafe_allow_html=True)


def _grafico_situacao(top: pd.DataFrame):
    vc = top.groupby("situacao")["valor_em_aberto"].sum().reindex(SITUACOES).dropna()
    if vc.empty:
        return
    fig = go.Figure(go.Bar(
        x=vc.values, y=vc.index, orientation="h",
        marker_color=[COR_SIT.get(s, CINZA) for s in vc.index],
        text=[formatar_brl(v) for v in vc.values], textposition="auto",
        insidetextfont=dict(color="white"),
    ))
    fig.update_layout(height=300, margin=dict(l=0, r=10, t=8, b=0), plot_bgcolor="white",
                      xaxis=dict(showgrid=True, gridcolor="#EEE", tickformat=",.0f"),
                      yaxis=dict(showgrid=False))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _tabela(top: pd.DataFrame, key: str, mostrar_grupo=False):
    filtro = st.multiselect("Filtrar por situação", SITUACOES, default=[], key=f"filtro_{key}")
    so_prot = st.checkbox("Somente protestados 🔴", key=f"prot_{key}")
    d = top.copy()
    if filtro:
        d = d[d["situacao"].isin(filtro)]
    if so_prot:
        d = d[d["tem_protesto"]]
    d = d.sort_values("valor_em_aberto", ascending=False).reset_index(drop=True)

    linhas = []
    for i, r in d.iterrows():
        selos = ("🔴 " if r["tem_protesto"] else "") + ("⚠️ " if r["tem_quebra"] else "")
        reg = {"#": i + 1}
        if mostrar_grupo:
            reg["Grupo"] = NOME_GRUPO.get(r["grupo"], r["grupo"])
        reg["Cliente"] = r["nome_cliente"]
        reg["Dívida"] = formatar_brl(r["valor_em_aberto"])
        reg["Situação"] = r["situacao"]
        if r["situacao"] == "Terceirizada" and r.get("terceirizada"):
            reg["Situação"] += f" ({r['terceirizada']})"
        reg["Selos"] = selos.strip() or "—"
        if r["situacao"] == "Acordo" and pd.notna(r.get("acordo_parcelas")):
            per = r.get("acordo_periodicidade") or ""
            vp = f" R$ {r['acordo_valor_parcela']:,.2f}" if pd.notna(r.get("acordo_valor_parcela")) else ""
            reg["Acordo"] = f"{int(r['acordo_parcelas'])}x {per}{vp}".strip()
        else:
            reg["Acordo"] = "—"
        linhas.append(reg)
    st.caption(f"{len(d)} clientes" + (" · filtro ativo" if (filtro or so_prot) else ""))
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True, height=620)


def _view(g: pd.DataFrame, grupo: str, key: str):
    if g.empty:
        st.info(f"Sem dados para {NOME_GRUPO.get(grupo, grupo)}.")
        return
    g = g.sort_values("valor_em_aberto", ascending=False).reset_index(drop=True)
    cor = COR_GRUPO.get(grupo, AZUL)
    _kpis_topo(g, cor)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Dívida por situação (Top 40)**")
    _grafico_situacao(g.head(TOP_N))
    st.markdown(f"**Top {TOP_N} — {NOME_GRUPO.get(grupo, grupo)}**")
    _tabela(g.head(TOP_N), key)


def _view_geral(df: pd.DataFrame, key: str):
    # Geral = Top 40 de cada grupo juntos (80 clientes). Fecha com as abas.
    top_pisa = df[df["grupo"] == "PISA"].sort_values("valor_em_aberto", ascending=False).head(TOP_N)
    top_kt = df[df["grupo"] == "KING_TRIO"].sort_values("valor_em_aberto", ascending=False).head(TOP_N)
    base = pd.concat([top_pisa, top_kt], ignore_index=True)

    tot_pisa = top_pisa["valor_em_aberto"].sum()
    tot_kt = top_kt["valor_em_aberto"].sum()
    total = tot_pisa + tot_kt

    c = st.columns(3)
    c[0].markdown(card_kpi("Dívida total (Geral)", formatar_brl(total),
                           f"{len(base)} clientes (Top 40 de cada)", AZUL), unsafe_allow_html=True)
    c[1].markdown(card_kpi("PISA", formatar_brl(tot_pisa),
                           f"{(tot_pisa/total*100 if total else 0):.0f}% · {len(top_pisa)} clientes", AZUL), unsafe_allow_html=True)
    c[2].markdown(card_kpi("King + Trio", formatar_brl(tot_kt),
                           f"{(tot_kt/total*100 if total else 0):.0f}% · {len(top_kt)} clientes", AMARELO), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Dívida por situação (Top 40 de cada grupo)**")
    _grafico_situacao(base)
    st.markdown(f"**Top {TOP_N} de cada grupo — {len(base)} clientes**")
    _tabela(base.sort_values("valor_em_aberto", ascending=False), key, mostrar_grupo=True)
