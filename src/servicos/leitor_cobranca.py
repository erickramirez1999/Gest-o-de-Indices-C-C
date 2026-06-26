"""
Leitor dos arquivos mensais de Cobrança.

A partir de mai/2026 o Sankhya exporta TRÊS arquivos avulsos (1 aba cada),
não mais um único workbook "Dashboard". A detecção é feita pelas COLUNAS
(não pelo nome da aba), porque acordos e produtividade usam a mesma aba
'relatório'.

1) ACORDOS REALIZADOS DETALHADO (rel_acordos_realizados_detalhado_*.xlsx)
   Aba 'relatório', cabeçalho na linha 0. 1 linha por PARCELA.
   Colunas-chave: PROCESSO, CNPJ/CPF, DEVEDOR, DATA ACORDO, HORA ACORDO,
   NEGOCIADOR ACORDO, PARCELA ("NN/MM"), FORMA PAGTO, VALOR, VALOR PAGO,
   STATUS (ANDAMENTO/QUITADO), VALOR CAPITAL/JUROS/MULTA.
   -> Agrupado por acordo (PROCESSO + DATA + HORA + NEGOCIADOR).
   -> valor_total = SOMA de VALOR; valor_pago = SOMA de VALOR PAGO.

2) OCORRÊNCIAS DE ACORDO (ocorrencias_ACORDO_*.xlsx)
   Aba 'Ocorrencias', cabeçalho na linha 0. 1 linha por ocorrência.
   Colunas-chave: PROCESSO, DEVEDOR, CIDADE, UF, DATA OCORRÊNCIA,
   CADASTRADO POR, STATUS ("01.01 - ACORDO" / "98 - QUEBRA DE ACORDO").
   -> Fonte das QUEBRAS de acordo.

3) PRODUTIVIDADE / TTO (rel_produtividade_*.xlsx)
   Aba 'Relatorio'. Linha 0: cabeçalho duplo (ACORDOS REALIZADOS /
   ACORDOS PROVISIONADOS). Linha 1: cabeçalho real. Linha 2+: dados
   diários por negociador. 'Total' (1º) = ACORDOS REALIZADOS.

O formato antigo (workbook Dashboard multi-aba) continua suportado como
fallback para não quebrar uploads históricos.
"""
from __future__ import annotations
import io
import re
import pandas as pd
from datetime import date, datetime
from typing import Optional


def ler_multiplos_arquivos_cobranca(arquivos: list[tuple[bytes, str]]) -> dict:
    resultado = {
        "acordos": pd.DataFrame(),
        "baixas": pd.DataFrame(),
        "performance": pd.DataFrame(),
        "ocorrencias": pd.DataFrame(),
        "erros": [],
        "arquivos_processados": [],
    }

    for bytes_arq, nome in arquivos:
        tipo = _detectar_tipo(bytes_arq, nome)
        resultado["arquivos_processados"].append(f"{nome} → {_rotulo(tipo)}")

        if tipo == "ACORDOS_REALIZADOS":
            df, erros = _ler_acordos_realizados(bytes_arq, nome)
            resultado["erros"] += erros
            resultado["acordos"] = _acumular(resultado["acordos"], df)

        elif tipo == "OCORRENCIAS":
            df, erros = _ler_ocorrencias_arquivo(bytes_arq, nome)
            resultado["erros"] += erros
            resultado["ocorrencias"] = _acumular(resultado["ocorrencias"], df)

        elif tipo == "BAIXAS":
            df, erros = _ler_baixas_arquivo(bytes_arq, nome)
            resultado["erros"] += erros
            resultado["baixas"] = _acumular(resultado["baixas"], df)

        elif tipo == "TTO_BRUTO":
            r = _ler_tto_bruto(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            if not r["performance"].empty:
                resultado["performance"] = r["performance"]

        elif tipo == "DASHBOARD":
            r = _ler_dashboard(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            for chave in ["acordos", "baixas", "performance", "ocorrencias"]:
                if chave in r and not r[chave].empty:
                    resultado[chave] = _acumular(resultado[chave], r[chave])
        else:
            resultado["erros"].append(f"'{nome}': formato não reconhecido.")

    return resultado


def _acumular(acumulado: pd.DataFrame, novo: pd.DataFrame) -> pd.DataFrame:
    if novo is None or novo.empty:
        return acumulado
    if acumulado.empty:
        return novo
    return pd.concat([acumulado, novo], ignore_index=True)


def _rotulo(tipo: str) -> str:
    return {
        "ACORDOS_REALIZADOS": "Acordos Realizados",
        "OCORRENCIAS": "Ocorrências (acordo/quebra)",
        "BAIXAS": "Cobrança Baixada",
        "TTO_BRUTO": "Produtividade (TTO)",
        "DASHBOARD": "Dashboard (formato antigo)",
    }.get(tipo, "Desconhecido")


# ============================================================
# DETECÇÃO (por colunas)
# ============================================================

def _detectar_tipo(bytes_arq: bytes, nome: str) -> str:
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        abas = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=None, header=None,
                             nrows=4, engine=engine)
    except Exception:
        return "DESCONHECIDO"

    # Múltiplas abas conhecidas -> formato Dashboard antigo
    nomes_abas = [a.lower() for a in abas.keys()]
    if len(abas) > 1 and any(
        any(k in n for k in ["cobrança baixada", "baixada", "resumo acordo"])
        for n in nomes_abas
    ):
        return "DASHBOARD"

    # Conjunto de textos das primeiras linhas da 1ª aba
    primeira_aba = list(abas.values())[0]
    textos = {
        str(v).strip().upper()
        for _, row in primeira_aba.iterrows()
        for v in row.values
        if pd.notna(v)
    }

    def tem(*chaves):
        return all(any(c in t for t in textos) for c in chaves)

    if tem("DATA OCORR") or tem("HISTÓRICO INTERNO") or tem("HISTORICO INTERNO"):
        return "OCORRENCIAS"

    if tem("COBRADOR") and (tem("VLR.DESDOB") or tem("VLR LÍQUIDO") or tem("VLR LIQUIDO")) \
            and (tem("DIAS DE ATRASO") or tem("DE 0 A 30")):
        return "BAIXAS"

    if tem("PROCESSO", "DATA ACORDO", "PARCELA") and (
        tem("VALOR PAGO") or tem("FORMA PAGTO")
    ):
        return "ACORDOS_REALIZADOS"

    if tem("NEGOCIADOR") and tem("TTO"):
        return "TTO_BRUTO"

    if len(abas) > 1:
        return "DASHBOARD"

    return "DESCONHECIDO"


# ============================================================
# 1) ACORDOS REALIZADOS DETALHADO (arquivo avulso)
# ============================================================

def _ler_acordos_realizados(bytes_arq: bytes, nome: str) -> tuple[pd.DataFrame, list]:
    erros: list[str] = []
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arq), engine=engine)
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao abrir '{nome}': {e}"]

    try:
        return _agrupar_acordos(df), erros
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao processar acordos em '{nome}': {e}"]


def _agrupar_acordos(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    col_proc = _achar_col(df, ["processo"])
    if not col_proc:
        return pd.DataFrame()
    df = df[df[col_proc].astype(str).str.match(r"^\s*\d+/\d+")].copy()
    if df.empty:
        return pd.DataFrame()

    col_neg = _achar_col(df, ["negociador acordo", "negociador processo", "negociador"])
    col_dev = _achar_col(df, ["devedor"])
    col_cnpj = _achar_col(df, ["cnpj"])
    col_data = _achar_col(df, ["data acordo"])
    col_hora = _achar_col(df, ["hora acordo"])
    col_forma = _achar_col(df, ["forma pagto", "forma pagamento"])
    col_parc = _achar_col(df, ["parcela"])
    col_vlr = _achar_col(df, ["valor atualizado", "valor pago"])  # placeholder, sobrescrito abaixo
    # 'VALOR' puro: primeira coluna cujo nome é exatamente 'valor'
    col_vlr = next((c for c in df.columns if str(c).strip().lower() == "valor"), None) \
        or _achar_col(df, ["valor"])
    col_pago = _achar_col(df, ["valor pago"])
    col_atual = _achar_col(df, ["valor atualizado"])
    col_status = _achar_col(df, ["status"])

    # chave do acordo: processo + data + hora + negociador
    chaves = [c for c in [col_proc, col_data, col_hora, col_neg] if c]
    resultado = []
    for _, grupo in df.groupby(chaves, sort=False):
        primeira = grupo.iloc[0]

        # qtd de parcelas: maior denominador de "NN/MM"; fallback = nº de linhas
        qtd_parcelas = _qtd_parcelas(grupo[col_parc]) if col_parc else len(grupo)
        if not qtd_parcelas:
            qtd_parcelas = len(grupo)

        valor_total = _soma(grupo, col_vlr)
        valor_pago = _soma(grupo, col_pago)
        valor_atualizado = _soma(grupo, col_atual)

        # status do acordo derivado das parcelas
        quitadas = 0
        if col_status:
            s = grupo[col_status].astype(str).str.upper()
            quitadas = int(s.str.contains("QUITAD").sum())
        n = len(grupo)
        if n and quitadas >= n:
            status = "QUITADO"
        elif quitadas > 0:
            status = "PARCIAL"
        else:
            status = "ANDAMENTO"

        vlr_parcela = (valor_total / qtd_parcelas) if qtd_parcelas else None

        resultado.append({
            "negociador": _normalizar_nome(str(primeira.get(col_neg or "") or "")),
            "processo": str(primeira.get(col_proc or "") or ""),
            "devedor": str(primeira.get(col_dev or "") or ""),
            "cnpj": str(primeira.get(col_cnpj or "") or ""),
            "data_acordo": _parse_data(primeira.get(col_data)),
            "forma_pagto": str(primeira.get(col_forma or "") or ""),
            "qtd_parcelas": qtd_parcelas,
            "qtd_parcelas_quitadas": quitadas,
            "valor_parcela": round(vlr_parcela, 2) if vlr_parcela is not None else None,
            "valor_total": round(valor_total, 2),
            "valor_pago": round(valor_pago, 2),
            "valor_atualizado": round(valor_atualizado, 2),
            "status": status,
            "cancelado": False,  # quebras vêm do arquivo de ocorrências
        })
    return pd.DataFrame(resultado)


def _qtd_parcelas(serie: pd.Series) -> Optional[int]:
    maior = 0
    for v in serie:
        m = re.match(r"\s*\d+\s*/\s*(\d+)", str(v))
        if m:
            maior = max(maior, int(m.group(1)))
    return maior or None


# ============================================================
# 2) OCORRÊNCIAS DE ACORDO (arquivo avulso) — fonte das QUEBRAS
# ============================================================

def _ler_ocorrencias_arquivo(bytes_arq: bytes, nome: str) -> tuple[pd.DataFrame, list]:
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arq), engine=engine)
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao abrir '{nome}': {e}"]

    try:
        return _processar_ocorrencias(df), []
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao processar ocorrências em '{nome}': {e}"]


def _processar_ocorrencias(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    col_proc = _achar_col(df, ["processo"])
    if col_proc:
        df = df[df[col_proc].astype(str).str.match(r"^\s*\d+/\d+")].copy()

    col_cad = _achar_col(df, ["cadastrado por"])
    col_dev = _achar_col(df, ["devedor"])
    col_cnpj = _achar_col(df, ["cnpj"])
    col_cid = _achar_col(df, ["cidade"])
    col_uf = _achar_col(df, ["uf"])
    col_data = _achar_col(df, ["data ocorrência", "data ocorrencia"])
    col_status = _achar_col(df, ["status"])

    resultado = []
    for _, row in df.iterrows():
        status = str(row.get(col_status or "", "") or "").strip()
        su = status.upper()
        eh_quebra = "QUEBRA" in su
        eh_acordo = ("ACORDO" in su) and not eh_quebra
        resultado.append({
            "negociador": _normalizar_nome(str(row.get(col_cad or "") or "")),
            "processo": str(row.get(col_proc or "", "") or ""),
            "devedor": str(row.get(col_dev or "", "") or ""),
            "cnpj": str(row.get(col_cnpj or "", "") or ""),
            "cidade": str(row.get(col_cid or "", "") or ""),
            "uf": str(row.get(col_uf or "", "") or ""),
            "data_ocorrencia": _parse_data(row.get(col_data)),
            "status": status,
            "eh_quebra": eh_quebra,
            "eh_acordo": eh_acordo,
        })
    return pd.DataFrame(resultado)


# ============================================================
# 3) PRODUTIVIDADE / TTO (rel_produtividade_*.xlsx)
# ============================================================

def _ler_tto_bruto(bytes_arq: bytes, nome: str) -> dict:
    """
    Linha 0: cabeçalho duplo (ACORDOS REALIZADOS | ACORDOS PROVISIONADOS)
    Linha 1: Negociador | Qtde. Ocorrências | TTO | Qtde. Processos |
             Quantidade | Total | Quantidade | Total | Data
    Linha 2+: 1 linha por negociador por dia.
    'Total' (1ª ocorrência) = ACORDOS REALIZADOS (escolha do gestor).
    """
    erros: list[str] = []
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arq), header=None, engine=engine)

        header_idx = None
        for i, row in df.iterrows():
            vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
            if any("negociador" in v for v in vals) and any("tto" in v for v in vals):
                header_idx = i
                break
        if header_idx is None:
            return {"performance": pd.DataFrame(), "erros": [f"Cabeçalho TTO não encontrado em '{nome}'."]}

        # Renomeia colunas duplicadas (Quantidade, Total aparecem 2x)
        colunas_raw = [str(c).strip() for c in df.iloc[header_idx].values]
        colunas, contadores = [], {}
        for c in colunas_raw:
            if c in contadores:
                contadores[c] += 1
                colunas.append(f"{c}_{contadores[c]}")
            else:
                contadores[c] = 0
                colunas.append(c)
        df.columns = colunas
        df = df.iloc[header_idx + 1:].reset_index(drop=True)

        col_neg = _achar_col(df, ["negociador"])
        col_tto = _achar_col(df, ["tto"])
        col_occ = _achar_col(df, ["qtde. ocorrência", "qtde. ocorrencias", "ocorrência", "ocorrencia"])
        col_data = _achar_col(df, ["data"])
        # ACORDOS REALIZADOS = 1ª 'Total' e 1ª 'Quantidade'
        col_ac_val = "Total" if "Total" in df.columns else _achar_col(df, ["total"])
        col_ac_qtd = "Quantidade" if "Quantidade" in df.columns else None

        if not col_neg or not col_tto:
            return {"performance": pd.DataFrame(), "erros": [f"Colunas Negociador/TTO não encontradas em '{nome}'."]}

        df = df.dropna(subset=[col_neg])
        df = df[df[col_neg].astype(str).str.strip().str.len() > 0].copy()
        df["_tto_h"] = df[col_tto].apply(_tto_para_horas)
        df["_cobrador"] = df[col_neg].apply(lambda x: _normalizar_nome(str(x)))

        total_dias = df[col_data].nunique() if col_data else 1
        total_dias = total_dias or 1
        META_HORAS = 2.0
        resultado = []
        for cobrador, grupo in df.groupby("_cobrador"):
            if not cobrador or cobrador.lower() in ("nan", "none"):
                continue
            tempo_total_h = grupo["_tto_h"].sum()
            tempo_medio_h = tempo_total_h / total_dias
            total_ocorr = _safe_sum(grupo, col_occ)
            total_ac_val = _safe_sum(grupo, col_ac_val)
            total_ac_qtd = _safe_sum(grupo, col_ac_qtd)
            resultado.append({
                "cobrador": cobrador,
                "tempo_medio_diario_h": round(tempo_medio_h, 4),
                "meta_diaria_h": META_HORAS,
                "pct_aderencia": round(tempo_medio_h / META_HORAS, 4),
                "ocorrencias_media_dia": round(total_ocorr / total_dias, 2),
                "acordos_media_dia": round(total_ac_qtd / total_dias, 2),
                "valor_medio_diario": round(total_ac_val / total_dias, 2),
                "total_acordos_valor": round(total_ac_val, 2),
            })
        return {"performance": pd.DataFrame(resultado), "erros": erros}
    except Exception as e:
        return {"performance": pd.DataFrame(), "erros": [f"Erro TTO '{nome}': {e}"]}


def _tto_para_horas(v) -> float:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        if hasattr(v, 'hour'):
            return v.hour + v.minute / 60 + v.second / 3600
        s = str(v).strip()
        if not s or s in ("0", "00:00:00"):
            return 0.0
        partes = s.split(":")
        if len(partes) == 3:
            return int(partes[0]) + int(partes[1]) / 60 + int(float(partes[2])) / 3600
        return 0.0
    except Exception:
        return 0.0


def _safe_sum(grupo: pd.DataFrame, col: Optional[str]) -> float:
    if not col or col not in grupo.columns:
        return 0.0
    try:
        return float(pd.to_numeric(grupo[col], errors="coerce").fillna(0).sum())
    except Exception:
        return 0.0


# ============================================================
# FORMATO ANTIGO (workbook Dashboard multi-aba) — fallback
# ============================================================

def _ler_dashboard(bytes_arq: bytes, nome: str) -> dict:
    erros: list[str] = []
    resultado = {
        "acordos": pd.DataFrame(), "baixas": pd.DataFrame(),
        "performance": pd.DataFrame(), "ocorrencias": pd.DataFrame(),
        "erros": erros,
    }
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        abas = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=None, engine=engine)
    except Exception as e:
        erros.append(f"Erro ao abrir '{nome}': {e}")
        return resultado

    nomes_abas = list(abas.keys())

    aba = _achar_aba(nomes_abas, ["acordos realizados", "detalhados"])
    if aba:
        try:
            resultado["acordos"] = _agrupar_acordos(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Acordos detalhados: {e}")

    aba = _achar_aba(nomes_abas, ["acordo e quebra", "quebra", "ocorrenc"])
    if aba:
        try:
            resultado["ocorrencias"] = _processar_ocorrencias(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Ocorrências: {e}")

    aba = _achar_aba(nomes_abas, ["cobran", "baixa"])
    if aba:
        try:
            resultado["baixas"] = _ler_baixas(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Cobrança Baixada: {e}")

    return resultado


def _ler_baixas_arquivo(bytes_arq: bytes, nome: str) -> tuple[pd.DataFrame, list]:
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arq), engine=engine)
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao abrir '{nome}': {e}"]
    try:
        return _ler_baixas(df), []
    except Exception as e:
        return pd.DataFrame(), [f"Erro ao processar baixas em '{nome}': {e}"]


def _ler_baixas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    col_cob = _achar_col(df, ["cobrador"])
    if not col_cob:
        return pd.DataFrame()
    df = df.dropna(subset=[col_cob])
    df = df[df[col_cob].astype(str).str.strip().str.len() > 0].copy()

    FAIXAS = {
        "De 0 a 30": "0-30", "De 31 a 60": "31-60",
        "De 60 a 91": "60-91", "De 91 a  180": "91-180",
        "De 181 360": "181-360", "Maior que 360": "+360",
    }
    col_dias = _achar_col(df, ["dias de atraso"])
    col_desdob = _achar_col(df, ["vlr.desdob", "vlr desdob"])
    col_liq = _achar_col(df, ["vlr líquido", "vlr liquido"])
    col_jm = _achar_col(df, ["juros + multa", "juros+multa"])

    resultado = []
    for _, row in df.iterrows():
        cobrador = _normalizar_nome(str(row.get(col_cob, "") or ""))
        if not cobrador or cobrador.lower() == "nan":
            continue
        faixa = None
        for col_f, label in FAIXAS.items():
            col_real = _achar_col(df, [col_f.lower()])
            if col_real and pd.notna(row.get(col_real)) and float(row.get(col_real, 0) or 0) > 0:
                faixa = label
                break
        resultado.append({
            "cobrador": cobrador,
            "dias_atraso": _int(row.get(col_dias)),
            "vlr_desdobrado": _float(row.get(col_desdob)),
            "vlr_liquido": _float(row.get(col_liq)),
            "juros_multa": _float(row.get(col_jm)),
            "faixa_aging": faixa,
        })
    return pd.DataFrame(resultado)


# ============================================================
# HELPERS
# ============================================================

def _achar_aba(nomes: list[str], palavras: list[str]) -> Optional[str]:
    for nome in nomes:
        if any(p in nome.lower() for p in palavras):
            return nome
    return None


def _achar_col(df: pd.DataFrame, nomes: list[str]) -> Optional[str]:
    for col in df.columns:
        if any(n in str(col).lower() for n in nomes):
            return col
    return None


def _soma(grupo: pd.DataFrame, col: Optional[str]) -> float:
    if not col or col not in grupo.columns:
        return 0.0
    return float(pd.to_numeric(grupo[col], errors="coerce").fillna(0).sum())


def _normalizar_nome(nome: str) -> str:
    if not nome or nome.lower() in ("nan", "none", ""):
        return ""
    nome = nome.strip()
    if "." in nome and " " not in nome:
        nome = nome.replace(".", " ")
    return nome.title()


def _float(v) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except Exception:
        return None


def _int(v) -> Optional[int]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return int(float(v))
    except Exception:
        return None


def _parse_data(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        if isinstance(v, (datetime, date)):
            return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
        s = str(v).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(s[:10], fmt).date().isoformat()
            except ValueError:
                continue
        return None
    except Exception:
        return None
