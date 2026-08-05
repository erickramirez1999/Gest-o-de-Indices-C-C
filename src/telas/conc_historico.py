"""Conciliação · Histórico (o que foi salvo, por data)."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from src.banco import repo_conciliacao
from src.servicos.conciliacao import gerar_xlsx_conciliacao
from src.utils.marca import AZUL_ESCURO
from src.utils.formatadores import formatar_brl


def _data_br(iso):
    try:
        y, m, d = str(iso)[:10].split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return str(iso)


def renderizar_conc_historico(usuario):
    st.markdown(f"<h1 style='color:{AZUL_ESCURO}'>📚 Conciliação · Histórico</h1>", unsafe_allow_html=True)
    regs = repo_conciliacao.listar_conciliacoes()
    if not regs:
        st.info("📭 Nenhuma conciliação salva ainda. Rode o **Processo 1** e clique em salvar.")
        return

    tabela = []
    for r in regs:
        tabela.append({
            "Data": _data_br(r["data_conciliacao"]),
            "QR Boleto": formatar_brl(r.get("valor_qrboleto") or 0),
            "PDV": formatar_brl(r.get("valor_pdv") or 0),
            "CobCloud": formatar_brl(r.get("valor_cobcloud") or 0),
            "Boleto CB": formatar_brl(r.get("valor_boletocb") or 0),
            "Sobrando": formatar_brl(r.get("valor_sobra") or 0),
            "Despesas": formatar_brl(r.get("valor_despesa") or 0),
        })
    st.dataframe(pd.DataFrame(tabela), use_container_width=True, hide_index=True)

    st.markdown("### Ver uma conciliação")
    opcoes = {f"{_data_br(r['data_conciliacao'])}": r for r in regs}
    sel = st.selectbox("Data", list(opcoes.keys()))
    r = opcoes[sel]

    resumo = repo_conciliacao.reconstruir_resumo(r)
    sobra_raw = repo_conciliacao.buscar_sobra(r["id"])
    sobra = [{"data": s.get("data"), "historico": s.get("historico"), "valor": float(s.get("valor") or 0)} for s in sobra_raw]
    ambiguos = repo_conciliacao.buscar_ambigua(r["id"])

    cols = st.columns(4)
    for i, x in enumerate(resumo):
        cols[i % 4].metric(x["tipo"], formatar_brl(x["valor"]), f"{x['qtd']} lçtos")

    if sobra:
        df = pd.DataFrame([{
            "Data": s["data"], "Histórico": s["historico"],
            "Cód Parceiro": s.get("cod") or "", "Parceiro": s.get("nome") or "",
            "Nota": s.get("nota") or "", "Valor": formatar_brl(s["valor"]),
        } for s in sobra])
        st.markdown("**PIX sobrando (Monday)**")
        st.dataframe(df, use_container_width=True, hide_index=True, height=360)

    if ambiguos:
        st.markdown("**🟡 PIX ambíguos (só um sobra — não somar os dois)**")
        linhas = [{"Valor": formatar_brl(g["valor"]), "Sobrando": f'{g["conta"]} de {len(g["candidatos"])}',
                   "Candidatos": "   |   ".join(f'{c["data"]} · {c["historico"]}' for c in g["candidatos"])}
                  for g in ambiguos]
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    xlsx = gerar_xlsx_conciliacao(resumo, sobra, sel, sobra_ambigua=ambiguos)
    st.download_button("📥 Baixar planilha desta conciliação", data=xlsx,
                       file_name=f"Conciliacao_{r['data_conciliacao']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
