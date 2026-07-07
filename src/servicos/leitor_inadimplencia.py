"""
Leitor do módulo de Inadimplência (Top 40 por empresa).

Junta TRÊS arquivos de um mês:
  1) EM_ABERTO_PISA_*.xls   -> valor "Em Aberto" por cliente (grupo PISA)
  2) EM_ABERTO_KING_*.xls   -> valor "Em Aberto" por cliente (grupo KING_TRIO)
  3) PLANILHA_..._GERAL.xls -> histórico por título -> SITUAÇÃO por cliente

O VALOR da dívida vem das planilhas Em Aberto; a SITUAÇÃO vem do histórico,
casada por Cód.Parceiro. Cada arquivo é detectado por colunas/nome.

Situação (excludente, pelo ESTADO ATUAL — fim do histórico):
  Ação Judicial > Terceirizada > Acordo > Quebra de Acordo >
  Devolvido pela Terceirizada > Sem Registro
Flags paralelas: Protesto (selo). Quebra só vale se o cliente está conosco.
"""
from __future__ import annotations
import io
import re
import math
import pandas as pd
from typing import Optional

GRUPO_PISA = "PISA"
GRUPO_KING_TRIO = "KING_TRIO"

TERCEIRIZADAS = [
    ("Rennovare", r"RENNOVARE"),
    ("Solute", r"SOLUTE"),
    ("KnowHow", r"KNOW\s*-?\s*HOW|KNOWHOW"),
    ("Personalité", r"PERSONALIT"),
    ("D'Avila", r"D[\s'`´]*AVILA|DAVILA"),
]
RE_JURIDICO = r"ENVIAD\w*\s+AO\s+.*JUR|ENCAMINH\w*.*JUR|A[ÇC][ÃA]O\s+JUDICIAL|PROCESSO\s+JUDICIAL"
RE_DV = r"#?-?\bDV\b|-DV|#DV|\bPD\b|DEVOLVIDO"
# Acordo = apenas a palavra ACORDO (renegociação/reneg/prorrogação NÃO são acordo),
# e ignorando a ocorrência dentro de "QUEBRA DE ACORDO".

SIT_JUDICIAL = "Ação Judicial"
SIT_TERC = "Terceirizada"
SIT_ACORDO = "Acordo"
SIT_QUEBRA = "Quebra de Acordo"
SIT_DEVOLVIDO = "Devolvido pela Terceirizada"
SIT_SEM = "Sem Registro"

PRIORIDADE = [SIT_JUDICIAL, SIT_TERC, SIT_ACORDO, SIT_QUEBRA, SIT_DEVOLVIDO, SIT_SEM]
_RANK = {s: i for i, s in enumerate(PRIORIDADE)}


def ler_inadimplencia(arquivos: list[tuple[bytes, str]]) -> dict:
    resultado = {"registros": [], "por_grupo": {}, "arquivos_processados": [], "erros": []}

    emaberto = {}   # (grupo) -> {cod: {"nome":..., "valor":...}}
    historico_bytes = None
    historico_nome = None

    for bytes_arq, nome in arquivos:
        tipo, grupo = _detectar(bytes_arq, nome)
        if tipo == "EM_ABERTO":
            try:
                dados = _ler_em_aberto(bytes_arq, nome, grupo)
                emaberto.setdefault(grupo, {}).update(dados)
                resultado["arquivos_processados"].append(f"{nome} → Em Aberto {_rot(grupo)} ({len(dados)} clientes)")
            except Exception as e:
                resultado["erros"].append(f"Erro em '{nome}': {e}")
        elif tipo == "HISTORICO":
            historico_bytes, historico_nome = bytes_arq, nome
            resultado["arquivos_processados"].append(f"{nome} → Histórico (situação)")
        else:
            resultado["erros"].append(f"'{nome}': não reconhecido (esperado Em Aberto PISA/King ou planilha de histórico).")

    if not emaberto:
        resultado["erros"].append("Faltou a(s) planilha(s) de valor (Em Aberto PISA e/ou King).")
        return resultado

    # situação por cliente (a partir do histórico)
    situacoes = {}
    if historico_bytes is not None:
        try:
            situacoes = _situacao_por_cliente(historico_bytes, historico_nome)
        except Exception as e:
            resultado["erros"].append(f"Erro ao ler histórico '{historico_nome}': {e}")

    # monta registros por (cliente, grupo), rankeados por valor dentro do grupo
    for grupo, clientes in emaberto.items():
        ordenados = sorted(clientes.items(), key=lambda kv: -(kv[1]["valor"] or 0))
        for pos, (cod, info) in enumerate(ordenados, start=1):
            sit = situacoes.get(cod, {})
            resultado["registros"].append({
                "grupo": grupo,
                "posicao": pos,
                "cod_cliente": str(cod),
                "nome_cliente": info["nome"],
                "valor_em_aberto": round(info["valor"] or 0, 2),
                "situacao": sit.get("situacao", SIT_SEM),
                "tem_quebra": bool(sit.get("tem_quebra", False)),
                "tem_protesto": bool(sit.get("tem_protesto", False)),
                "terceirizada": sit.get("terceirizada"),
                "acordo_parcelas": sit.get("acordo_parcelas"),
                "acordo_periodicidade": sit.get("acordo_periodicidade"),
                "acordo_valor_parcela": sit.get("acordo_valor_parcela"),
                "acordo_responsavel": sit.get("acordo_responsavel"),
                "acordo_data": sit.get("acordo_data"),
            })
        resultado["por_grupo"][grupo] = len(ordenados)

    return resultado


# ============================================================
# DETECÇÃO
# ============================================================

def _detectar(bytes_arq: bytes, nome: str) -> tuple[str, Optional[str]]:
    n = nome.lower()
    engine = "xlrd" if n.endswith(".xls") else "openpyxl"
    try:
        amostra = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=None, nrows=6, engine=engine)
    except Exception:
        return ("DESCONHECIDO", None)
    textos = {str(v).strip().upper() for _, row in amostra.iterrows() for v in row.values if pd.notna(v)}

    def tem(*chaves):
        return any(any(c in t for c in chaves) for t in textos)

    if tem("HISTÓRICO", "HISTORICO") and tem("CENTRO DE RESULTADO", "VLR DO DESDOBRAMENTO"):
        return ("HISTORICO", None)
    if tem("EM ABERTO"):
        grupo = GRUPO_PISA if "pisa" in n else (GRUPO_KING_TRIO if ("king" in n or "trio" in n) else None)
        if grupo is None:
            grupo = GRUPO_PISA if tem("EM ABERTO PISA") else GRUPO_KING_TRIO
        return ("EM_ABERTO", grupo)
    return ("DESCONHECIDO", None)


def _rot(grupo: str) -> str:
    return {GRUPO_PISA: "PISA", GRUPO_KING_TRIO: "King+Trio"}.get(grupo, grupo)


# ============================================================
# EM ABERTO (valor)
# ============================================================

def _ler_em_aberto(bytes_arq: bytes, nome: str, grupo: str) -> dict:
    engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
    # cabeçalho pode estar na linha 2 (metadados nas linhas 0-1)
    df = _ler_com_cabecalho(bytes_arq, engine, ["Cód.Parceiro", "Parceiro"])
    col_cod = _col(df, ["cód.parceiro", "cod.parceiro", "cód parceiro", "codigo"])
    col_nome = _col(df, ["parceiro"])
    col_val = _col(df, ["em aberto pisa"] if grupo == GRUPO_PISA else ["em aberto king"]) \
        or _col(df, ["em aberto"])
    df = df[pd.to_numeric(df[col_cod], errors="coerce").notna()].copy()
    out = {}
    for _, r in df.iterrows():
        cod = int(float(r[col_cod]))
        out[cod] = {"nome": str(r.get(col_nome, "") or "").strip(),
                    "valor": _num(r.get(col_val)) or 0.0}
    return out


def _ler_com_cabecalho(bytes_arq: bytes, engine: str, chaves: list[str]):
    for hdr in (0, 1, 2, 3):
        try:
            df = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=hdr, engine=engine)
            df.columns = [str(c).strip() for c in df.columns]
            if all(any(k.lower() in str(c).lower() for c in df.columns) for k in chaves):
                return df
        except Exception:
            continue
    df = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=0, header=2, engine=engine)
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ============================================================
# HISTÓRICO -> SITUAÇÃO por cliente
# ============================================================

def _situacao_por_cliente(bytes_arq: bytes, nome: str) -> dict:
    engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
    df = _ler_com_cabecalho(bytes_arq, engine, ["Parceiro", "Histórico"])
    col_cod = _col(df, ["parceiro"])
    col_hist = _col(df, ["histórico", "historico"])
    df = df[pd.to_numeric(df[col_cod], errors="coerce").notna()].copy()

    por_cliente = {}
    for cod, g in df.groupby(col_cod):
        cod = int(float(cod))
        titulos = [_classificar_titulo(h) for h in g[col_hist].astype(str)]
        # situação do cliente = prioridade entre as situações dos títulos
        sit = sorted({t["situacao"] for t in titulos}, key=lambda s: _RANK.get(s, 99))[0]
        # quebra só sinaliza se NÃO há acordo ativo agora (situação atual != Acordo)
        tem_quebra = any(t["quebra"] for t in titulos) and sit in (SIT_QUEBRA, SIT_DEVOLVIDO, SIT_SEM)
        tem_protesto = any(t["protesto"] for t in titulos)
        terceirizada = None
        if sit == SIT_TERC:
            tercs = [t["terceirizada"] for t in titulos if t["situacao"] == SIT_TERC and t["terceirizada"]]
            terceirizada = max(set(tercs), key=tercs.count) if tercs else None
        info = {"situacao": sit, "tem_quebra": tem_quebra, "tem_protesto": tem_protesto,
                "terceirizada": terceirizada}
        # detalhes de acordo (se a situação for Acordo)
        if sit == SIT_ACORDO:
            for t in titulos:
                if t["situacao"] == SIT_ACORDO and t.get("acordo"):
                    info.update({
                        "acordo_parcelas": t["acordo"].get("parcelas"),
                        "acordo_periodicidade": t["acordo"].get("periodicidade"),
                        "acordo_valor_parcela": t["acordo"].get("valor_parcela"),
                        "acordo_responsavel": t["acordo"].get("responsavel"),
                        "acordo_data": t["acordo"].get("data"),
                    })
                    break
        por_cliente[cod] = info
    return por_cliente


def _classificar_titulo(hist: str) -> dict:
    H = str(hist).upper()
    toks = []
    for nome_t, pat in TERCEIRIZADAS:
        for m in re.finditer(pat, H):
            toks.append((m.start(), "TERC", nome_t))
    for m in re.finditer(RE_JURIDICO, H):
        toks.append((m.start(), "JUR", None))
    for m in re.finditer(RE_DV, H):
        toks.append((m.start(), "DV", None))
    for m in re.finditer(r"ACORDO", H):
        ini = m.start()
        # ignora "ACORDO" que faz parte de "QUEBRA DE ACORDO"
        if "QUEBRA DE" in H[max(0, ini - 11):ini]:
            continue
        toks.append((ini, "ACORDO", None))
    toks.sort(key=lambda x: x[0])

    holder = "NOS"
    acordo_nos = False
    passou_terc = False
    ult_terc = None
    for _, tp, val in toks:
        if tp == "TERC":
            holder = "TERC"; ult_terc = val; acordo_nos = False; passou_terc = True
        elif tp == "JUR":
            holder = "JUR"; acordo_nos = False
        elif tp == "DV":
            holder = "NOS"
        elif tp == "ACORDO" and holder == "NOS":
            acordo_nos = True

    quebra = "QUEBRA DE ACORDO" in H
    protesto = bool(re.search(r"PROT", H))

    if holder == "JUR":
        sit = SIT_JUDICIAL
    elif holder == "TERC":
        sit = SIT_TERC
    elif acordo_nos:
        sit = SIT_ACORDO
    elif quebra:
        sit = SIT_QUEBRA
    elif passou_terc or toks:
        sit = SIT_DEVOLVIDO
    else:
        sit = SIT_SEM

    res = {"situacao": sit, "quebra": quebra, "protesto": protesto, "terceirizada": ult_terc}
    if sit == SIT_ACORDO:
        res["acordo"] = _extrair_acordo(H)
    return res


def _extrair_acordo(H: str) -> dict:
    d = {"parcelas": None, "periodicidade": None, "valor_parcela": None,
         "responsavel": None, "data": None}
    m = re.search(r"(\d{1,3})\s*X", H)
    if m:
        d["parcelas"] = int(m.group(1))
    for pat, lbl in [(r"SEMAN", "Semanal"), (r"QUINZEN", "Quinzenal"),
                     (r"MENSA", "Mensal"), (r"DI[ÁA]RI", "Diário")]:
        if re.search(pat, H):
            d["periodicidade"] = lbl
            break
    m = re.search(r"R\$\s*([\d.]+(?:,\d{2})?)", H)
    if m:
        try:
            d["valor_parcela"] = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", H)
    if m:
        d["data"] = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    m = re.search(r"-\s*([A-ZÀ-Ü][A-ZÀ-Ü.]+(?:\s+[A-ZÀ-Ü][A-ZÀ-Ü.]+)?)\s*(?:\d{2}[./]\d{2}|$)", H)
    if m:
        cand = m.group(1).strip().title()
        _bloq = ("DV", "PD", "ACORDO", "COB", "COMPLEMENTO", "VENC", "ORIG", "QUEBRA",
                 "LOTE", "SEMANA", "SEMANAIS", "MENSAL", "QUINZENAL", "RENNOVARE",
                 "SOLUTE", "KNOWHOW", "KNOW", "DEVOLVIDO", "PROT", "JURIDICO", "RENEG")
        if not any(b in cand.upper() for b in _bloq):
            d["responsavel"] = cand
    return d


# ============================================================
# HELPERS
# ============================================================

def _col(df, nomes: list[str]) -> Optional[str]:
    cols = list(df.columns)
    low = [str(c).strip().lower() for c in cols]
    # 1º passe: match exato (evita 'Parceiro' casar dentro de 'Cód.Parceiro')
    for n in nomes:
        for i, cl in enumerate(low):
            if cl == n:
                return cols[i]
    # 2º passe: substring
    for n in nomes:
        for i, cl in enumerate(low):
            if n in cl:
                return cols[i]
    return None


def _num(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None
