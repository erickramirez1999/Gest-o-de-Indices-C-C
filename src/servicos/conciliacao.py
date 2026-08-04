"""
Serviço de Conciliação de Recebimentos — LLE Índices.

PROCESSO 1 (conciliação diária):
  Entradas: extrato bancário (Data/Histórico/Documento/Valor/Saldo) e base de
  recebimentos (com "Identificador do pagamento").
  - Classifica os automáticos: QR Boleto (YKP), PDV (010), CobCloud (3455/).
  - CobCloud é lido do EXTRATO (histórico contém "3455/").
  - Do EXTRATO pega os PIX RECEBIDO positivos e remove, por VALOR (um-para-um),
    os que batem com os automáticos (QR Boleto + PDV). O que sobra vai pro Monday.
  Saída: resumo por tipo + lista do que sobrou + total.
"""
from __future__ import annotations
import io
import re
from collections import Counter
from typing import Optional

import pandas as pd

QR_BOLETO = "QR Boleto"
PDV = "PDV"
COBCLOUD = "CobCloud"
BOLETO_CB = "Boleto Cód Barras"
SOBRA = "Sobrando (Monday)"

ID_COBCLOUD = "3455/000554357"
ID_BOLETO_CB = "3455/003475395"


def processar_conciliacao(arquivos: list[tuple[bytes, str]]) -> dict:
    res = {"resumo": [], "sobra": [], "total_sobra": 0.0, "erros": [],
           "arquivos": [], "ok": False}

    base_df = extrato_df = None
    for bytes_arq, nome in arquivos:
        tipo = _detectar(bytes_arq, nome)
        if tipo == "BASE":
            base_df = _ler_base(bytes_arq, nome); res["arquivos"].append(f"{nome} → Base recebimentos")
        elif tipo == "EXTRATO":
            extrato_df = _ler_extrato(bytes_arq, nome); res["arquivos"].append(f"{nome} → Extrato bancário")
        else:
            res["erros"].append(f"'{nome}': não reconhecido (esperado extrato bancário ou base com 'Identificador do pagamento').")

    if base_df is None:
        res["erros"].append("Faltou a **base de recebimentos** (com 'Identificador do pagamento').")
    if extrato_df is None:
        res["erros"].append("Faltou o **extrato bancário**.")
    if base_df is None or extrato_df is None:
        return res

    # classifica base
    base_df["cat"] = base_df["identificador"].apply(_classificar_id)
    base_df["valor"] = pd.to_numeric(base_df["valor"], errors="coerce").round(2)

    qtd_qr = int((base_df["cat"] == QR_BOLETO).sum())
    val_qr = round(base_df[base_df["cat"] == QR_BOLETO]["valor"].sum(), 2)
    qtd_pdv = int((base_df["cat"] == PDV).sum())
    val_pdv = round(base_df[base_df["cat"] == PDV]["valor"].sum(), 2)

    # cobcloud e boleto cód barras vêm do extrato (histórico com 3455/...)
    cob = extrato_df[extrato_df["historico"].astype(str).str.contains(ID_COBCLOUD, na=False, regex=False)]
    qtd_cob = len(cob); val_cob = round(pd.to_numeric(cob["valor"], errors="coerce").sum(), 2)
    bcb = extrato_df[extrato_df["historico"].astype(str).str.contains(ID_BOLETO_CB, na=False, regex=False)]
    qtd_bcb = len(bcb); val_bcb = round(pd.to_numeric(bcb["valor"], errors="coerce").sum(), 2)

    # pix positivo do extrato
    pix = extrato_df[
        extrato_df["historico"].astype(str).str.upper().str.contains("PIX RECEBIDO")
        & (pd.to_numeric(extrato_df["valor"], errors="coerce") > 0)
    ].copy()
    pix["valor"] = pd.to_numeric(pix["valor"], errors="coerce").round(2)

    # remove por valor os automáticos (QR Boleto + PDV) da base
    auto = [round(v, 2) for v in base_df[base_df["cat"].isin([QR_BOLETO, PDV])]["valor"].dropna().tolist()]
    cont = Counter(auto)
    sobra = []
    for _, r in pix.iterrows():
        v = round(float(r["valor"]), 2)
        if cont.get(v, 0) > 0:
            cont[v] -= 1
        else:
            sobra.append({"data": str(r["data"]), "historico": str(r["historico"]).strip(), "valor": v})

    total_sobra = round(sum(s["valor"] for s in sobra), 2)

    # SAÍDAS (Valor < 0) no extrato → separa Aplicação de Despesa
    ext_v = pd.to_numeric(extrato_df["valor"], errors="coerce")
    saidas = extrato_df[ext_v < 0].copy()
    saidas["valor"] = pd.to_numeric(saidas["valor"], errors="coerce").round(2)
    lista = [{"data": str(r["data"]), "historico": str(r["historico"]).strip(),
              "valor": round(float(r["valor"]), 2)} for _, r in saidas.iterrows()]

    def _eh_aplicacao(h):
        return "APLICA" in str(h).upper()  # APLICAÇÃO / APLICACAO

    aplicacoes = sorted([x for x in lista if _eh_aplicacao(x["historico"])], key=lambda d: d["valor"])
    despesas = sorted([x for x in lista if not _eh_aplicacao(x["historico"])], key=lambda d: d["valor"])
    total_despesa = round(sum(d["valor"] for d in despesas), 2)
    total_aplicacao = round(sum(d["valor"] for d in aplicacoes), 2)

    res["resumo"] = [
        {"tipo": QR_BOLETO, "qtd": qtd_qr, "valor": val_qr},
        {"tipo": PDV, "qtd": qtd_pdv, "valor": val_pdv},
        {"tipo": COBCLOUD, "qtd": qtd_cob, "valor": val_cob},
        {"tipo": BOLETO_CB, "qtd": qtd_bcb, "valor": val_bcb},
        {"tipo": SOBRA, "qtd": len(sobra), "valor": total_sobra},
    ]
    res["sobra"] = sorted(sobra, key=lambda s: -s["valor"])
    res["total_sobra"] = total_sobra
    res["despesas"] = despesas
    res["total_despesa"] = total_despesa
    res["aplicacoes"] = aplicacoes
    res["total_aplicacao"] = total_aplicacao
    res["ok"] = True
    return res


# ---------- detecção e leitura ----------

def _detectar(bytes_arq: bytes, nome: str) -> str:
    try:
        amostra = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=None, nrows=6)
    except Exception:
        return "DESCONHECIDO"
    textos = " ".join(str(v).upper() for _, row in amostra.iterrows() for v in row.values if pd.notna(v))
    if "IDENTIFICADOR DO PAGAMENTO" in textos:
        return "BASE"
    if "SALDO" in textos and ("HISTÓRICO" in textos or "HISTORICO" in textos):
        return "EXTRATO"
    if "AGENCIA" in textos and "CONTA" in textos:
        return "EXTRATO"
    return "DESCONHECIDO"


def _ler_base(bytes_arq: bytes, nome: str) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    idc = _col(df, ["identificador do pagamento", "identificador"])
    valc = _col(df, ["valor"])
    out = pd.DataFrame({"identificador": df[idc], "valor": df[valc]})
    return out[out["valor"].notna()].copy()


def _ler_extrato(bytes_arq: bytes, nome: str) -> pd.DataFrame:
    # cabeçalho costuma estar na linha 2 (0-based)
    raw = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=None)
    hdr = 0
    for i in range(min(6, len(raw))):
        linha = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if any("histórico" in c or "historico" in c for c in linha) and any("valor" in c for c in linha):
            hdr = i; break
    df = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=hdr)
    df.columns = [str(c).strip() for c in df.columns]
    col_data = _col(df, ["data"])
    col_hist = _col(df, ["histórico", "historico"])
    col_val = _col(df, ["valor (r$)", "valor"])
    out = pd.DataFrame({"data": df[col_data], "historico": df[col_hist], "valor": df[col_val]})
    return out[out["data"].astype(str).str.contains(r"\d{2}/\d{2}", na=False)].copy()


def _classificar_id(x) -> str:
    s = str(x).strip().upper()
    if s.startswith("YKP"):
        return QR_BOLETO
    if s.startswith(ID_COBCLOUD):
        return COBCLOUD
    if s.startswith(ID_BOLETO_CB):
        return BOLETO_CB
    if s.startswith("3455/"):
        return BOLETO_CB
    if s.startswith("010"):
        return PDV
    return "SEM ID"


def _col(df, nomes) -> Optional[str]:
    low = [str(c).strip().lower() for c in df.columns]
    for n in nomes:
        for i, c in enumerate(low):
            if c == n:
                return df.columns[i]
    for n in nomes:
        for i, c in enumerate(low):
            if n in c:
                return df.columns[i]
    return None


def gerar_xlsx_conciliacao(resumo: list[dict], sobra: list[dict], data_label: str,
                           despesas: list[dict] | None = None,
                           aplicacoes: list[dict] | None = None) -> bytes:
    """Gera a planilha do Processo 1 (resumo + PIX sobrando + despesas + aplicações)."""
    despesas = despesas or []
    aplicacoes = aplicacoes or []
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    AZUL = "041747"; VERM = "DC3545"; CINZA = "6C757D"
    COR = {QR_BOLETO: "0F8C3B", PDV: "0071FE", COBCLOUD: "041747", BOLETO_CB: "0071FE", SOBRA: "DC3545"}
    thin = Side(style="thin", color="D9DCE3")

    def F(**k): return Font(name="Arial", **k)

    wb = Workbook(); ws = wb.active; ws.title = "Conciliação"
    ws["A1"] = f"Conciliação de Recebimentos — {data_label}"; ws["A1"].font = F(size=15, bold=True, color=AZUL)
    ws["A2"] = "Recebimentos automáticos classificados e PIX sobrando para o Monday"; ws["A2"].font = F(size=9, color=CINZA)

    ws["A4"] = "RESUMO POR TIPO"; ws["A4"].font = F(size=11, bold=True, color=AZUL)
    for j, c in enumerate(["Tipo", "Qtd", "Valor (R$)"], 1):
        cell = ws.cell(row=5, column=j, value=c); cell.font = F(size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=AZUL); cell.alignment = Alignment(horizontal="left" if j == 1 else "center")
    for i, x in enumerate(resumo):
        rr = 6 + i
        ws.cell(row=rr, column=1, value=x["tipo"]).font = F(size=10, bold=True, color=COR.get(x["tipo"], AZUL))
        qc = ws.cell(row=rr, column=2, value=x["qtd"]); qc.font = F(size=10); qc.alignment = Alignment(horizontal="center")
        vc = ws.cell(row=rr, column=3, value=x["valor"]); vc.font = F(size=10); vc.number_format = '#,##0.00'
        for j in range(1, 4): ws.cell(row=rr, column=j).border = Border(bottom=thin)
    tr = 6 + len(resumo)
    ws.cell(row=tr, column=1, value="TOTAL geral").font = F(size=10, bold=True, color=AZUL)
    tg = ws.cell(row=tr, column=3, value=f"=SUM(C6:C{tr-1})"); tg.font = F(size=10, bold=True, color=AZUL)
    tg.number_format = '#,##0.00'; tg.fill = PatternFill("solid", fgColor="FFF6D9")

    base = tr + 2
    ws.cell(row=base, column=1, value="DETALHE — PIX SOBRANDO (Monday)").font = F(size=11, bold=True, color=VERM)
    for j, c in enumerate(["#", "Data", "Histórico", "Valor (R$)"], 1):
        cell = ws.cell(row=base + 1, column=j, value=c); cell.font = F(size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=VERM); cell.alignment = Alignment(horizontal="left" if j == 3 else "center")
    for i, s in enumerate(sobra):
        rr = base + 2 + i
        ws.cell(row=rr, column=1, value=i + 1).font = F(size=10)
        ws.cell(row=rr, column=2, value=s["data"]).font = F(size=10)
        ws.cell(row=rr, column=3, value=s["historico"]).font = F(size=10)
        vc = ws.cell(row=rr, column=4, value=float(s["valor"])); vc.font = F(size=10); vc.number_format = '#,##0.00'
        for j in range(1, 5): ws.cell(row=rr, column=j).border = Border(bottom=thin)
    tr2 = base + 2 + len(sobra)
    ws.cell(row=tr2, column=3, value="TOTAL sobrando").font = F(size=11, bold=True, color=VERM)
    ws.cell(row=tr2, column=3).alignment = Alignment(horizontal="right")
    ts = ws.cell(row=tr2, column=4, value=f"=SUM(D{base+2}:D{tr2-1})" if sobra else 0)
    ts.font = F(size=11, bold=True, color=VERM); ts.number_format = '#,##0.00'; ts.fill = PatternFill("solid", fgColor="FDE7E9")

    for j, w in zip(range(1, 5), [6, 12, 42, 16]): ws.column_dimensions[get_column_letter(j)].width = w

    # DESPESAS (saídas do extrato — valores em vermelho)
    dbase = tr2 + 2
    ws.cell(row=dbase, column=1, value="DESPESAS — saídas do extrato (Valor em vermelho)").font = F(size=11, bold=True, color="B00020")
    for j, c in enumerate(["#", "Data", "Histórico", "Valor (R$)"], 1):
        cell = ws.cell(row=dbase + 1, column=j, value=c); cell.font = F(size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="B00020"); cell.alignment = Alignment(horizontal="left" if j == 3 else "center")
    for i, d in enumerate(despesas):
        rr = dbase + 2 + i
        ws.cell(row=rr, column=1, value=i + 1).font = F(size=10)
        ws.cell(row=rr, column=2, value=d["data"]).font = F(size=10)
        ws.cell(row=rr, column=3, value=d["historico"]).font = F(size=10)
        vc = ws.cell(row=rr, column=4, value=float(d["valor"])); vc.font = F(size=10, color="B00020")
        vc.number_format = '#,##0.00;[Red]-#,##0.00'
        for j in range(1, 5): ws.cell(row=rr, column=j).border = Border(bottom=thin)
    dr = dbase + 2 + len(despesas)
    ws.cell(row=dr, column=3, value="TOTAL despesas").font = F(size=11, bold=True, color="B00020")
    ws.cell(row=dr, column=3).alignment = Alignment(horizontal="right")
    td = ws.cell(row=dr, column=4, value=f"=SUM(D{dbase+2}:D{dr-1})" if despesas else 0)
    td.font = F(size=11, bold=True, color="B00020"); td.number_format = '#,##0.00;[Red]-#,##0.00'
    td.fill = PatternFill("solid", fgColor="FDE7E9")

    # APLICAÇÕES (destaque — movimentação financeira, não é despesa)
    abase = dr + 2
    ws.cell(row=abase, column=1, value="APLICAÇÕES — movimentação financeira (não é despesa)").font = F(size=11, bold=True, color="7B5800")
    for j, c in enumerate(["#", "Data", "Histórico", "Valor (R$)"], 1):
        cell = ws.cell(row=abase + 1, column=j, value=c); cell.font = F(size=10, bold=True, color="3A2D00")
        cell.fill = PatternFill("solid", fgColor="FAC318"); cell.alignment = Alignment(horizontal="left" if j == 3 else "center")
    for i, a in enumerate(aplicacoes):
        rr = abase + 2 + i
        ws.cell(row=rr, column=1, value=i + 1).font = F(size=10)
        ws.cell(row=rr, column=2, value=a["data"]).font = F(size=10)
        ws.cell(row=rr, column=3, value=a["historico"]).font = F(size=10)
        vc = ws.cell(row=rr, column=4, value=float(a["valor"])); vc.font = F(size=10, color="7B5800")
        vc.number_format = '#,##0.00;[Red]-#,##0.00'
        for j in range(1, 5): ws.cell(row=rr, column=j).border = Border(bottom=thin)
    ar = abase + 2 + len(aplicacoes)
    ws.cell(row=ar, column=3, value="TOTAL aplicações").font = F(size=11, bold=True, color="7B5800")
    ws.cell(row=ar, column=3).alignment = Alignment(horizontal="right")
    ta = ws.cell(row=ar, column=4, value=f"=SUM(D{abase+2}:D{ar-1})" if aplicacoes else 0)
    ta.font = F(size=11, bold=True, color="7B5800"); ta.number_format = '#,##0.00;[Red]-#,##0.00'
    ta.fill = PatternFill("solid", fgColor="FFF6D9")

    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()
