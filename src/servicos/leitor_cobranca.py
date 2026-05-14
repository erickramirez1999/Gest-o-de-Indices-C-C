"""
Leitor dos arquivos mensais de Cobrança.

Aceita MÚLTIPLOS arquivos — o sistema identifica automaticamente o conteúdo:

Arquivo tipo DASHBOARD (abas nomeadas):
  - 'Resumo Acordos'                  → índices de acordo
  - 'Acordo e quebra de acordo'        → ocorrências
  - 'cobrança baixada por cobrador'    → índices de cobrança/baixas
  - 'Relatório de produtividade'       → performance (formato resumido)

Arquivo tipo RELATÓRIO BRUTO TTO (aba 'Relatorio'):
  - Colunas: Negociador, Qtde. Ocorrências, TTO, Qtde. Processos,
             Acordos Realizados (qtd+valor), Acordos Provisionados (qtd+valor), Data
  - 1 linha por cobrador por dia — sistema calcula as médias automaticamente

O sistema detecta automaticamente qual tipo é cada arquivo.
"""
from __future__ import annotations
import io
import pandas as pd
from datetime import date, datetime
from typing import Optional


def ler_multiplos_arquivos_cobranca(arquivos: list[tuple[bytes, str]]) -> dict:
    """
    Lê múltiplos arquivos de cobrança e consolida os resultados.

    Args:
        arquivos: lista de (bytes, nome_arquivo)

    Retorna: {
        'acordos': DataFrame,
        'ocorrencias': DataFrame,
        'baixas': DataFrame,
        'performance': DataFrame,
        'erros': list[str],
        'arquivos_processados': list[str]
    }
    """
    resultado = {
        "acordos": pd.DataFrame(),
        "ocorrencias": pd.DataFrame(),
        "baixas": pd.DataFrame(),
        "performance": pd.DataFrame(),
        "erros": [],
        "arquivos_processados": [],
    }

    for bytes_arq, nome in arquivos:
        tipo = _detectar_tipo(bytes_arq, nome)
        resultado["arquivos_processados"].append(f"{nome} → {tipo}")

        if tipo == "DASHBOARD":
            r = _ler_dashboard(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            for chave in ["acordos", "ocorrencias", "baixas", "performance"]:
                if not r[chave].empty:
                    if resultado[chave].empty:
                        resultado[chave] = r[chave]
                    else:
                        resultado[chave] = pd.concat(
                            [resultado[chave], r[chave]], ignore_index=True
                        )

        elif tipo == "TTO_BRUTO":
            r = _ler_tto_bruto(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            if not r["performance"].empty:
                if resultado["performance"].empty:
                    resultado["performance"] = r["performance"]
                else:
                    # Se já tinha performance do dashboard, substitui pelo bruto (mais preciso)
                    resultado["performance"] = r["performance"]

        else:
            resultado["erros"].append(f"'{nome}': formato não reconhecido, ignorado.")

    return resultado


# ============================================================
# DETECÇÃO DE TIPO
# ============================================================

def _detectar_tipo(bytes_arq: bytes, nome: str) -> str:
    """Detecta se o arquivo é Dashboard completo ou Relatório TTO bruto."""
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        abas = pd.read_excel(
            io.BytesIO(bytes_arq), sheet_name=None, nrows=3, engine=engine,
        )
        nomes = [a.lower() for a in abas.keys()]

        # TTO bruto: aba 'relatorio' ou 'relatório'
        if any("relatorio" in n or "relatório" in n for n in nomes):
            return "TTO_BRUTO"

        # Dashboard: tem abas conhecidas
        keywords = ["resumo", "cobran", "baixa", "produtividade", "acordo"]
        if any(any(k in n for k in keywords) for n in nomes):
            return "DASHBOARD"

        # Detecta pela estrutura da primeira aba
        primeira = list(abas.values())[0]
        colunas = [str(c).upper() for c in primeira.columns]
        if "TTO" in colunas or any("NEGOCIADOR" in c for c in colunas):
            return "TTO_BRUTO"

        return "DESCONHECIDO"
    except Exception:
        return "DESCONHECIDO"


# ============================================================
# LEITURA DASHBOARD COMPLETO
# ============================================================

def _ler_dashboard(bytes_arq: bytes, nome: str) -> dict:
    erros = []
    resultado = {
        "acordos": pd.DataFrame(), "ocorrencias": pd.DataFrame(),
        "baixas": pd.DataFrame(), "performance": pd.DataFrame(),
        "erros": erros,
    }

    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        abas = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=None, engine=engine)
    except Exception as e:
        erros.append(f"Erro ao abrir '{nome}': {e}")
        return resultado

    nomes_abas = list(abas.keys())

    aba = _achar_aba(nomes_abas, ["resumo acordo", "resumo"])
    if aba:
        try:
            resultado["acordos"] = _ler_resumo_acordos(abas[aba])
        except Exception as e:
            erros.append(f"Erro Resumo Acordos ({nome}): {e}")
    else:
        erros.append(f"Aba 'Resumo Acordos' não encontrada em '{nome}'.")

    aba = _achar_aba(nomes_abas, ["acordo e quebra", "quebra"])
    if aba:
        try:
            resultado["ocorrencias"] = _ler_ocorrencias(abas[aba])
        except Exception as e:
            erros.append(f"Erro Acordo e Quebra ({nome}): {e}")

    aba = _achar_aba(nomes_abas, ["cobran", "baixa", "baixad"])
    if aba:
        try:
            resultado["baixas"] = _ler_baixas(abas[aba])
        except Exception as e:
            erros.append(f"Erro Cobrança Baixada ({nome}): {e}")
    else:
        erros.append(f"Aba de cobrança baixada não encontrada em '{nome}'.")

    aba = _achar_aba(nomes_abas, ["produtividade", "performance"])
    if aba:
        try:
            resultado["performance"] = _ler_performance_resumo(abas[aba])
        except Exception as e:
            erros.append(f"Erro Produtividade ({nome}): {e}")

    return resultado


# ============================================================
# LEITURA TTO BRUTO
# ============================================================

def _ler_tto_bruto(bytes_arq: bytes, nome: str) -> dict:
    """
    Lê o relatório bruto de TTO (1 linha por cobrador por dia).
    Calcula automaticamente: tempo médio, aderência, ocorrências/dia, acordos/dia.
    """
    erros = []
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        # Linha 0: cabeçalho duplo (ACORDOS REALIZADOS / PROVISIONADOS)
        # Linha 1: nomes reais das colunas
        df_raw = pd.read_excel(io.BytesIO(bytes_arq), header=1, engine=engine)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
    except Exception as e:
        return {"performance": pd.DataFrame(), "erros": [f"Erro ao abrir TTO '{nome}': {e}"]}

    col_neg = _achar_col(df_raw, ["negociador"])
    col_occ = _achar_col(df_raw, ["qtde. ocorrência", "qtde. ocorrencias", "ocorrência", "ocorrencia"])
    col_tto = _achar_col(df_raw, ["tto"])
    col_ac_qtd = _achar_col(df_raw, ["quantidade"])
    col_ac_val = _achar_col(df_raw, ["total"])
    col_data = _achar_col(df_raw, ["data"])

    if not col_neg or not col_tto:
        return {
            "performance": pd.DataFrame(),
            "erros": [f"Colunas Negociador/TTO não encontradas em '{nome}'."],
        }

    df_raw = df_raw.dropna(subset=[col_neg])
    df_raw = df_raw[df_raw[col_neg].astype(str).str.strip().str.len() > 0]
    df_raw["_tto_h"] = df_raw[col_tto].apply(_tto_para_horas)
    df_raw["_cobrador"] = df_raw[col_neg].apply(lambda x: _normalizar_nome(str(x)))

    # Total de dias distintos no arquivo
    if col_data:
        df_raw["_data"] = df_raw[col_data].apply(_parse_data)
        total_dias = df_raw["_data"].nunique() or 1
    else:
        total_dias = df_raw["_cobrador"].value_counts().max() or 1

    META_HORAS = 2.0
    resultado = []

    for cobrador, grupo in df_raw.groupby("_cobrador"):
        if not cobrador or str(cobrador).upper() in ("NAN", "NONE", ""):
            continue

        tempo_total_h = grupo["_tto_h"].sum()
        tempo_medio_h = tempo_total_h / total_dias

        total_ocorr = _safe_sum(grupo, col_occ)
        total_ac_qtd = _safe_sum(grupo, col_ac_qtd)
        total_ac_val = _safe_sum(grupo, col_ac_val)

        resultado.append({
            "cobrador": cobrador,
            "tempo_medio_diario_h": round(tempo_medio_h, 4),
            "meta_diaria_h": META_HORAS,
            "pct_aderencia": round(tempo_medio_h / META_HORAS, 4),
            "ocorrencias_media_dia": round(total_ocorr / total_dias, 2),
            "acordos_media_dia": round(total_ac_qtd / total_dias, 4),
            "valor_medio_diario": round(total_ac_val / total_dias, 2),
            "total_acordos_valor": round(total_ac_val, 2),
        })

    return {"performance": pd.DataFrame(resultado), "erros": erros}


def _tto_para_horas(v) -> float:
    """Converte TTO (HH:MM:SS string ou datetime.time) para horas decimais."""
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
        if len(partes) == 2:
            return int(partes[0]) + int(partes[1]) / 60
        return float(s)
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
# LEITORES DAS ABAS DO DASHBOARD
# ============================================================

def _ler_resumo_acordos(df: pd.DataFrame) -> pd.DataFrame:
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).upper() for v in row.values if pd.notna(v)]
        if "PROCESSO" in vals and "DEVEDOR" in vals:
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()

    df2 = df.iloc[header_idx:].copy()
    df2.columns = [str(c).strip() for c in df2.iloc[0]]
    df2 = df2.iloc[1:].reset_index(drop=True)
    df2 = df2.dropna(subset=["PROCESSO"])
    df2 = df2[df2["PROCESSO"].astype(str).str.match(r"^\d+/\d+")]

    resultado = []
    for _, row in df2.iterrows():
        neg = str(row.get("NEGOCIADOR ACORDO", row.get("NEGOCIADOR PROCESSO", ""))).strip()
        resultado.append({
            "negociador": _normalizar_nome(neg),
            "processo": str(row.get("PROCESSO", "")),
            "devedor": str(row.get("DEVEDOR", "")),
            "cnpj": str(row.get("CNPJ/CPF", "")),
            "data_acordo": _parse_data(row.get("DATA ACORDO")),
            "forma_pagto": str(row.get("FORMA PAGTO", "")),
            "qtd_parcelas": _int(row.get("QTD PARCELAS")),
            "valor_parcela": _float(row.get("VALOR PARCELA")),
            "valor_total": _float(row.get("VALOR TOTAL ACORDO")),
            "status": str(row.get("STATUS", "")),
            "cancelado": "CANCEL" in str(row.get("STATUS", "")).upper(),
            "valor_capital": _float(row.get("VALOR CAPITAL")),
            "valor_juros": _float(row.get("VALOR JUROS")),
            "valor_multa": _float(row.get("VALOR MULTA")),
        })
    return pd.DataFrame(resultado)


def _ler_ocorrencias(df: pd.DataFrame) -> pd.DataFrame:
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).upper() for v in row.values if pd.notna(v)]
        if "PROCESSO" in vals and any("CADASTRADO" in v for v in vals):
            header_idx = i
            break
    if header_idx is not None:
        df2 = df.iloc[header_idx:].copy()
        df2.columns = [str(c).strip() for c in df2.iloc[0]]
        df = df2.iloc[1:].reset_index(drop=True)

    df = df.dropna(subset=[df.columns[0]])
    df = df[df[df.columns[0]].astype(str).str.match(r"^\d+/")]

    resultado = []
    for _, row in df.iterrows():
        segundos = _int(row.get("SEGUNDOS TOTAL", 0)) or 0
        resultado.append({
            "negociador": _normalizar_nome(str(row.get("CADASTRADO POR", ""))),
            "processo": str(row.get("PROCESSO", "")),
            "devedor": str(row.get("DEVEDOR", "")),
            "data_ocorrencia": _parse_data(row.get("DATA OCORRÊNCIA")),
            "segundos_total": segundos,
            "minutos_total": round(segundos / 60, 2),
            "status": str(row.get("STATUS", "")),
        })
    return pd.DataFrame(resultado)


def _ler_baixas(df: pd.DataFrame) -> pd.DataFrame:
    # Normaliza nomes de colunas para comparação case-insensitive
    col_map = {c.strip().lower(): c.strip() for c in df.columns}
    df.columns = [c.strip() for c in df.columns]

    # Acha coluna cobrador independente de capitalização
    col_cobrador = None
    for c in df.columns:
        if c.lower() == "cobrador":
            col_cobrador = c
            break
    if not col_cobrador:
        return pd.DataFrame()

    df = df.dropna(subset=[col_cobrador])

    FAIXAS = {
        "De 0 a 30": "0-30", "De 31 a 60": "31-60",
        "De 60 a 91": "60-91", "De 91 a  180": "91-180",
        "De 181 360": "181-360", "Maior que 360": "+360",
    }

    # Acha colunas de forma case-insensitive
    def _col(nomes):
        for n in nomes:
            for c in df.columns:
                if c.lower().strip() == n.lower():
                    return c
        return None

    col_parceiro = _col(["parceiro"])
    col_venc = _col(["vencimento"])
    col_baixa = _col(["baixa"])
    col_dias = _col(["dias de atraso"])
    col_desdob = _col(["vlr.desdob.", "vlr desdob"])
    col_liq = _col(["vlr líquido", "vlr liquido"])
    col_jm = _col(["juros + multa", "juros+multa"])
    col_tipo = _col(["tipo de título", "tipo de titulo"])
    col_cat = _col(["categoria"])

    resultado = []
    for _, row in df.iterrows():
        cobrador = _normalizar_nome(str(row.get(col_cobrador, "")))
        if not cobrador or cobrador.lower() == "nan":
            continue

        faixa = None
        for col_f, label in FAIXAS.items():
            col_real = _col([col_f])
            if col_real and pd.notna(row.get(col_real)) and float(row.get(col_real, 0) or 0) > 0:
                faixa = label
                break

        resultado.append({
            "cobrador": cobrador,
            "parceiro": str(row.get(col_parceiro, "") or ""),
            "vencimento": _parse_data(row.get(col_venc)),
            "data_baixa": _parse_data(row.get(col_baixa)),
            "dias_atraso": _int(row.get(col_dias)),
            "vlr_desdobrado": _float(row.get(col_desdob)),
            "vlr_liquido": _float(row.get(col_liq)),
            "juros_multa": _float(row.get(col_jm)),
            "faixa_aging": faixa,
            "tipo_titulo": str(row.get(col_tipo, "") or ""),
            "categoria": str(row.get(col_cat, "") or ""),
        })
    return pd.DataFrame(resultado)


def _ler_performance_resumo(df: pd.DataFrame) -> pd.DataFrame:
    resumo_idx = None
    for i, row in df.iterrows():
        vals = [str(v).upper() for v in row.values if pd.notna(v)]
        if "COBRADOR" in vals or "NEGOCIADOR" in vals:
            resumo_idx = i
            break
    if resumo_idx is None:
        return pd.DataFrame()

    df_res = df.iloc[resumo_idx:].copy()
    df_res.columns = [str(c).strip() for c in df_res.iloc[0]]
    df_res = df_res.iloc[1:].reset_index(drop=True)

    resultado = []
    for _, row in df_res.iterrows():
        nome = str(row.iloc[0]).strip()
        if not nome or nome.upper() in ("NAN", "EQUIPE (TOTAL)", "COBRADOR", "NEGOCIADOR"):
            continue
        if "EQUIPE" in nome.upper():
            continue
        if pd.notna(row.iloc[-1]) and isinstance(row.iloc[-1], (datetime, date)):
            break
        resultado.append({
            "cobrador": _normalizar_nome(nome),
            "tempo_medio_diario_h": _float(row.iloc[1]),
            "meta_diaria_h": _float(row.iloc[2]),
            "pct_aderencia": _float(row.iloc[3]),
            "ocorrencias_media_dia": _float(row.iloc[4]),
            "acordos_media_dia": _float(row.iloc[5]),
            "valor_medio_diario": _float(row.iloc[6]),
            "total_acordos_valor": _float(row.iloc[7]),
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


def _normalizar_nome(nome: str) -> str:
    if not nome or nome.lower() in ("nan", "none", ""):
        return ""
    nome = nome.strip()
    if "." in nome and " " not in nome:
        nome = nome.replace(".", " ")
    return nome.title()


def _float(v) -> Optional[float]:
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def _int(v) -> Optional[int]:
    try:
        if pd.isna(v):
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
