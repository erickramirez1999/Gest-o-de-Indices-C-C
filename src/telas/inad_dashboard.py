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
TERCEIRIZADAS_OPCOES = ["", "Rennovare", "Solute", "KnowHow", "Personalité", "D'Avila"]
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

    # valores automáticos originais
    manuais = repo_inadimplencia.buscar_situacoes_manuais(mes_sel)
    df["cod_cliente"] = df["cod_cliente"].astype(str)
    df["situacao_auto"] = df["situacao"]
    df["terceirizada_auto"] = df["terceirizada"] if "terceirizada" in df.columns else None
    df["quebra_auto"] = df["tem_quebra"]
    df["protesto_auto"] = df["tem_protesto"]

    def _efetivo(r):
        m = manuais.get(r["cod_cliente"])
        if not m:
            return pd.Series([r["situacao_auto"], r["terceirizada_auto"],
                              bool(r["quebra_auto"]), bool(r["protesto_auto"]), None])
        sit = m.get("situacao") or r["situacao_auto"]
        terc = m.get("terceirizada") if m.get("terceirizada") is not None else r["terceirizada_auto"]
        q = m.get("tem_quebra") if m.get("tem_quebra") is not None else r["quebra_auto"]
        p = m.get("tem_protesto") if m.get("tem_protesto") is not None else r["protesto_auto"]
        return pd.Series([sit, terc, bool(q), bool(p), m.get("acordo_texto")])

    df[["situacao", "terceirizada", "tem_quebra", "tem_protesto", "acordo_manual"]] = df.apply(_efetivo, axis=1)
    df["editado_manual"] = df["cod_cliente"].isin(manuais.keys())

    editavel = getattr(usuario, "perfil", "") in ("ADMIN", "GESTOR_COBRANCA", "GESTOR_CREDITO")

    aba_kt, aba_pisa, aba_geral = st.tabs(["🔺 King + Trio", "🏢 PISA", "📊 Geral"])
    with aba_kt:
        _view(df[df["grupo"] == "KING_TRIO"].copy(), "KING_TRIO", "kt", mes_sel, usuario, editavel)
    with aba_pisa:
        _view(df[df["grupo"] == "PISA"].copy(), "PISA", "pisa", mes_sel, usuario, editavel)
    with aba_geral:
        _view_geral(df, "geral", mes_sel, usuario, editavel)


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


def _tabela(top: pd.DataFrame, key: str, mes_ano: str, usuario, editavel: bool, mostrar_grupo=False):
    busca = st.text_input("🔎 Buscar cliente (nome ou código)", key=f"busca_{key}",
                          placeholder="Digite parte do nome ou o código do parceiro")
    filtro = st.multiselect("Filtrar por situação", SITUACOES, default=[], key=f"filtro_{key}")
    so_prot = st.checkbox("Somente protestados 🔴", key=f"prot_{key}")
    d = top.copy()
    if busca:
        b = busca.strip().lower()
        d = d[d["nome_cliente"].astype(str).str.lower().str.contains(b, na=False)
              | d["cod_cliente"].astype(str).str.contains(b, na=False)]
    if filtro:
        d = d[d["situacao"].isin(filtro)]
    if so_prot:
        d = d[d["tem_protesto"]]
    d = d.sort_values("valor_em_aberto", ascending=False).reset_index(drop=True)

    editar = editavel and st.checkbox("✏️ Editar (situação, terceirizada, acordo, selos)", key=f"edit_{key}")

    linhas = []
    acordos_auto = []
    for i, r in d.iterrows():
        a_auto = _acordo_auto_str(r)
        acordos_auto.append(a_auto)
        reg = {"#": i + 1, "Cód": r["cod_cliente"]}
        if mostrar_grupo:
            reg["Grupo"] = NOME_GRUPO.get(r["grupo"], r["grupo"])
        reg["Cliente"] = r["nome_cliente"]
        reg["Dívida"] = formatar_brl(r["valor_em_aberto"])
        reg["Situação"] = r["situacao"]
        reg["Terceirizada"] = r.get("terceirizada") or ""
        reg["Acordo"] = (r.get("acordo_manual") or a_auto or "")
        if editar:
            reg["Protesto"] = bool(r["tem_protesto"])
            reg["Quebra"] = bool(r["tem_quebra"])
        else:
            selos = ("🔴 " if r["tem_protesto"] else "") + ("⚠️ " if r["tem_quebra"] else "") + ("✏️ " if r.get("editado_manual") else "")
            reg["Selos"] = selos.strip() or "—"
            reg["Acordo"] = reg["Acordo"] or "—"
        linhas.append(reg)
    disp = pd.DataFrame(linhas)
    st.caption(f"{len(d)} clientes" + (" · filtro/busca ativo" if (filtro or so_prot or busca) else ""))

    if not editar:
        st.dataframe(disp, use_container_width=True, hide_index=True, height=620)
        return

    # garante tipos coerentes p/ o data_editor (evita coluna vazia virar numérica)
    for c in ("Situação", "Terceirizada", "Acordo"):
        disp[c] = disp[c].fillna("").astype(str)
    for c in ("Protesto", "Quebra"):
        disp[c] = disp[c].fillna(False).astype(bool)

    st.info("Edite **Situação, Terceirizada, Acordo, Protesto e Quebra** direto na tabela e clique em salvar. "
            "O ajuste manual sobrepõe o automático e vale para este mês. Para voltar ao automático, "
            "deixe os campos iguais aos originais (Acordo em branco).")
    editaveis = ("Situação", "Terceirizada", "Acordo", "Protesto", "Quebra")
    editado = st.data_editor(
        disp, use_container_width=True, hide_index=True, height=620,
        key=f"editor_{key}",
        disabled=[c for c in disp.columns if c not in editaveis],
        column_config={
            "Situação": st.column_config.SelectboxColumn("Situação", options=SITUACOES, required=True),
            "Terceirizada": st.column_config.SelectboxColumn("Terceirizada", options=TERCEIRIZADAS_OPCOES),
            "Acordo": st.column_config.TextColumn("Acordo", help="Ex.: 12x mensal R$ 500,00 - Pedro 10/03/2026"),
            "Protesto": st.column_config.CheckboxColumn("Protesto"),
            "Quebra": st.column_config.CheckboxColumn("Quebra"),
        },
    )
    if st.button("💾 Salvar alterações", type="primary", key=f"save_{key}"):
        alterados = 0
        for i in range(len(disp)):
            r = d.iloc[i]
            cod = r["cod_cliente"]
            nova_sit = editado.iloc[i]["Situação"]
            val_terc = editado.iloc[i]["Terceirizada"]
            nova_terc = "" if pd.isna(val_terc) else str(val_terc).strip()
            val_ac = editado.iloc[i]["Acordo"]
            novo_ac = "" if pd.isna(val_ac) else str(val_ac).strip()
            novo_prot = bool(editado.iloc[i]["Protesto"]) if pd.notna(editado.iloc[i]["Protesto"]) else False
            nova_queb = bool(editado.iloc[i]["Quebra"]) if pd.notna(editado.iloc[i]["Quebra"]) else False

            # valores automáticos originais desta linha
            auto_sit = r["situacao_auto"]
            auto_terc = (r["terceirizada_auto"] or "") if r["terceirizada_auto"] is not None else ""
            auto_ac = (acordos_auto[i] or "").strip()
            auto_prot = bool(r["protesto_auto"])
            auto_queb = bool(r["quebra_auto"])

            igual_auto = (nova_sit == auto_sit and nova_terc == auto_terc
                          and novo_ac in ("", "—", auto_ac) and novo_prot == auto_prot and nova_queb == auto_queb)
            # detecta se houve mudança em relação ao que estava exibido
            mostrado_ac = "" if pd.isna(disp.iloc[i]["Acordo"]) else str(disp.iloc[i]["Acordo"]).strip()
            mudou = (nova_sit != disp.iloc[i]["Situação"]
                     or nova_terc != str(disp.iloc[i]["Terceirizada"]).strip()
                     or novo_ac != (mostrado_ac if mostrado_ac != "—" else "")
                     or novo_prot != bool(disp.iloc[i]["Protesto"])
                     or nova_queb != bool(disp.iloc[i]["Quebra"]))
            if not mudou:
                continue
            try:
                if igual_auto:
                    repo_inadimplencia.remover_situacao_manual(mes_ano, cod)
                else:
                    ac_manual = novo_ac if novo_ac not in ("", "—", auto_ac) else None
                    repo_inadimplencia.salvar_situacao_manual(
                        mes_ano, cod, nova_sit,
                        terceirizada=(nova_terc or None), acordo_texto=ac_manual,
                        tem_quebra=nova_queb, tem_protesto=novo_prot,
                        usuario_id=getattr(usuario, "id", None))
                alterados += 1
            except Exception as e:
                st.error(f"Erro ao salvar {cod}: {repr(e)[:200]}")
                st.stop()
        if alterados:
            st.success(f"✓ {alterados} cliente(s) atualizado(s).")
            st.rerun()
        else:
            st.info("Nenhuma alteração para salvar.")


def _acordo_auto_str(r) -> str:
    if r.get("situacao_auto") == "Acordo" and pd.notna(r.get("acordo_parcelas")):
        per = r.get("acordo_periodicidade") or ""
        vp = f" R$ {r['acordo_valor_parcela']:,.2f}" if pd.notna(r.get("acordo_valor_parcela")) else ""
        resp = f" - {r['acordo_responsavel']}" if r.get("acordo_responsavel") else ""
        return f"{int(r['acordo_parcelas'])}x {per}{vp}{resp}".strip()
    return ""


def _view(g: pd.DataFrame, grupo: str, key: str, mes_ano: str, usuario, editavel: bool):
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
    _tabela(g.head(TOP_N), key, mes_ano, usuario, editavel)


def _view_geral(df: pd.DataFrame, key: str, mes_ano: str, usuario, editavel: bool):
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
    _tabela(base.sort_values("valor_em_aberto", ascending=False), key, mes_ano, usuario, editavel, mostrar_grupo=True)
