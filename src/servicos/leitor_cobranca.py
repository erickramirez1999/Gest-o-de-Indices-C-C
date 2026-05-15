"""
Leitor dos arquivos mensais de Cobrança.

Estrutura real das abas do Dashboard:

'Acordos realizados detalhados':
  Cabeçalho linha 0, dados linha 1+
  Colunas: PROCESSO, CARTEIRA/CREDOR, CNPJ/CPF, COD EXTERNO, DEVEDOR,
           DATA ACORDO, HORA ACORDO, NEGOCIADOR PROCESSO, NEGOCIADOR ACORDO,
           PARCELA, FORMA PAGTO, DATA VENCTO, VALOR, STATUS, VALOR CAPITAL,
           VALOR JUROS, JUROS MORA, VALOR MULTA

'cobrança baixada por cobrador':
  Cabeçalho linha 0, dados linha 1+
  Colunas: Vencimento, Baixa, Dias de atraso, Cod.Parceiro, Parceiro,
           Vlr.Desdob., Vlr Calculado, Juros + multa, Vlr Líquido,
           De 0 a 30, De 31 a 60, De 60 a 91, De 91 a 180, De 181 360,
           Maior que 360, Tipo de Título, Cobrador, ...

'Relatório de produtividade':
  Linha 0: título
  Linha 1: cabeçalho (Cobrador, Tempo médio diário (h), Meta diária (h), %)
  Linha 2+: dados por cobrador

Arquivo TTO bruto (rel_produtividade_*.xlsx):
  Linha 0: metadado
  Linha 1: cabeçalho (Negociador, Qtde. Ocorrências, TTO, ...)
  Linha 2+: dados diários
"""
from __future__ import annotations
import io
import pandas as pd
from datetime import date, datetime
from typing import Optional


def ler_multiplos_arquivos_cobranca(arquivos: list[tuple[bytes, str]]) -> dict:
    resultado = {
        "acordos": pd.DataFrame(),
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
            for chave in ["acordos", "baixas", "performance"]:
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
                resultado["performance"] = r["performance"]
        else:
            resultado["erros"].append(f"'{nome}': formato não reconhecido.")

    return resultado


# ============================================================
# DETECÇÃO
# ============================================================

def _detectar_tipo(bytes_arq: bytes, nome: str) -> str:
    nome_lower = nome.lower()
    try:
        engine = "xlrd" if nome_lower.endswith(".xls") else "openpyxl"
        abas = pd.read_excel(io.BytesIO(bytes_arq), sheet_name=None, nrows=2, engine=engine)
        nomes = [a.lower() for a in abas.keys()]

        # Dashboard tem múltiplas abas conhecidas — verifica primeiro
        keywords_dashboard = ["cobrança baixada", "cobran", "baixada", "acordos realizados", "resumo acordo"]
        if any(any(k in n for k in keywords_dashboard) for n in nomes):
            return "DASHBOARD"

        # TTO bruto: única aba com 'relatorio' no nome
        if len(nomes) == 1 and any("relatorio" in n or "relatório" in n for n in nomes):
            return "TTO_BRUTO"

        # Dashboard genérico
        keywords_dash2 = ["acordo", "indicador"]
        if any(any(k in n for k in keywords_dash2) for n in nomes):
            return "DASHBOARD"
    except Exception:
        pass
    return "DESCONHECIDO"


# ============================================================
# DASHBOARD COMPLETO
# ============================================================

def _ler_dashboard(bytes_arq: bytes, nome: str) -> dict:
    erros = []
    resultado = {
        "acordos": pd.DataFrame(), 
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

    # Acordos: aba 'Acordos realizados detalhados'
    aba = _achar_aba(nomes_abas, ["acordos realizados", "detalhados"])
    if aba:
        try:
            resultado["acordos"] = _ler_acordos_detalhados(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Acordos detalhados: {e}")
    else:
        # Tenta Resumo Acordos como fallback
        aba = _achar_aba(nomes_abas, ["resumo acordo", "resumo"])
        if aba:
            try:
                resultado["acordos"] = _ler_resumo_acordos(abas[aba])
            except Exception as e:
                erros.append(f"Erro em Resumo Acordos: {e}")
        else:
            erros.append(f"Aba de acordos não encontrada em '{nome}'.")

    # Ocorrências: aba 'Acordo e quebra'
    aba = _achar_aba(nomes_abas, ["acordo e quebra", "quebra"])
    if aba:
        try:
            resultado["ocorrencias"] = _ler_ocorrencias(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Acordo e Quebra: {e}")

    # Baixas
    aba = _achar_aba(nomes_abas, ["cobran", "baixa"])
    if aba:
        try:
            resultado["baixas"] = _ler_baixas(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Cobrança Baixada: {e}")
    else:
        erros.append(f"Aba de baixas não encontrada em '{nome}'.")

    # Performance resumida
    aba = _achar_aba(nomes_abas, ["produtividade", "performance"])
    if aba:
        try:
            resultado["performance"] = _ler_performance_resumo(abas[aba])
        except Exception as e:
            erros.append(f"Erro em Produtividade: {e}")

    return resultado


# ============================================================
# ACORDOS DETALHADOS (aba 'Acordos realizados detalhados')
# ============================================================

def _ler_acordos_detalhados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cabeçalho na linha 0, dados linha 1+
    1 linha por parcela — precisamos agrupar por processo para 1 linha por acordo
    """
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    # Filtra linhas com PROCESSO válido (formato X/NNNNN)
    col_proc = _achar_col(df, ["processo"])
    if col_proc:
        df = df[df[col_proc].astype(str).str.match(r"^\d+/\d+")].copy()
    else:
        return pd.DataFrame()

    col_neg = _achar_col(df, ["negociador acordo", "negociador processo"])
    col_dev = _achar_col(df, ["devedor"])
    col_cnpj = _achar_col(df, ["cnpj"])
    col_data = _achar_col(df, ["data acordo"])
    col_forma = _achar_col(df, ["forma pagto"])
    col_qtd = _achar_col(df, ["parcela"])
    col_vlr = _achar_col(df, ["valor"])
    col_status = _achar_col(df, ["status"])
    col_cap = _achar_col(df, ["valor capital"])
    col_jur = _achar_col(df, ["valor juros"])
    col_mul = _achar_col(df, ["valor multa"])

    # Agrupa por processo — pega a primeira ocorrência de cada campo
    agrupado = df.groupby(col_proc, sort=False)

    resultado = []
    for processo, grupo in agrupado:
        primeira = grupo.iloc[0]
        qtd_parcelas = len(grupo)

        # Valor total = soma dos valores das parcelas
        vlr_parcela = _float(primeira.get(col_vlr)) if col_vlr else None
        valor_total = (vlr_parcela or 0) * qtd_parcelas

        neg = str(primeira.get(col_neg or "") or "").strip()
        if "." in neg and " " not in neg:
            neg = neg.replace(".", " ").title()
        else:
            neg = neg.title()

        resultado.append({
            "negociador": neg,
            "devedor": str(primeira.get(col_dev or "") or ""),
            "data_acordo": _parse_data(primeira.get(col_data)),
            "forma_pagto": str(primeira.get(col_forma or "") or ""),
            "qtd_parcelas": qtd_parcelas,
            "valor_parcela": vlr_parcela,
            "valor_total": valor_total,
            "status": str(primeira.get(col_status or "") or ""),
            "cancelado": "CANCEL" in str(primeira.get(col_status or "") or "").upper(),
        })
    return pd.DataFrame(resultado)


def _ler_resumo_acordos(df: pd.DataFrame) -> pd.DataFrame:
    """Aba Resumo Acordos — cabeçalho pode estar em linha 2."""
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


# ============================================================
# OCORRÊNCIAS (aba 'Acordo e quebra de acordo')
# ============================================================

def _ler_ocorrencias(df: pd.DataFrame) -> pd.DataFrame:
    """Cabeçalho na linha 0."""
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    col_proc = _achar_col(df, ["processo"])
    if col_proc:
        df = df[df[col_proc].astype(str).str.match(r"^\d+/\d+")].copy()

    col_cad = _achar_col(df, ["cadastrado por"])
    col_dev = _achar_col(df, ["devedor"])
    col_data = _achar_col(df, ["data ocorrência", "data ocorrencia"])
    col_seg = _achar_col(df, ["segundos total"])
    col_status = _achar_col(df, ["status"])

    resultado = []
    for _, row in df.iterrows():
        neg = str(row.get(col_cad or "") or "").strip()
        if "." in neg and " " not in neg:
            neg = neg.replace(".", " ").title()
        else:
            neg = neg.title()

        segundos = _int(row.get(col_seg or 0)) or 0
        resultado.append({
            "negociador": neg,
            "processo": str(row.get(col_proc or "", "")),
            "devedor": str(row.get(col_dev or "", "")),
            "data_ocorrencia": _parse_data(row.get(col_data)),
            "segundos_total": segundos,
            "minutos_total": round(segundos / 60, 2),
            "status": str(row.get(col_status or "", "")),
        })
    return pd.DataFrame(resultado)


# ============================================================
# BAIXAS (aba 'cobrança baixada por cobrador')
# ============================================================

def _ler_baixas(df: pd.DataFrame) -> pd.DataFrame:
    """Cabeçalho na linha 0."""
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

    col_parc = _achar_col(df, ["parceiro"])
    col_venc = _achar_col(df, ["vencimento"])
    col_baixa = _achar_col(df, ["baixa"])
    col_dias = _achar_col(df, ["dias de atraso"])
    col_desdob = _achar_col(df, ["vlr.desdob", "vlr desdob"])
    col_liq = _achar_col(df, ["vlr líquido", "vlr liquido"])
    col_jm = _achar_col(df, ["juros + multa", "juros+multa"])
    col_tipo = _achar_col(df, ["tipo de título", "tipo de titulo"])
    col_cat = _achar_col(df, ["categoria"])

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
# PERFORMANCE RESUMIDA (aba 'Relatório de produtividade')
# ============================================================

def _ler_performance_resumo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Linha 0: título
    Linha 1: cabeçalho (Cobrador, Tempo médio diário (h), Meta diária (h), ...)
    Linha 2+: dados por cobrador
    """
    # Acha linha do cabeçalho
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).lower() for v in row.values if pd.notna(v)]
        if any("cobrador" in v or "negociador" in v for v in vals):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    colunas = [str(c).strip() for c in df.iloc[header_idx].values]
    df2 = df.iloc[header_idx + 1:].copy()
    df2.columns = colunas
    df2 = df2.reset_index(drop=True)

    # Remove linhas vazias e linha de equipe total
    col_cob = colunas[0]
    df2 = df2.dropna(subset=[col_cob])
    df2 = df2[~df2[col_cob].astype(str).str.upper().str.contains("EQUIPE|TOTAL|NAN")]

    resultado = []
    for _, row in df2.iterrows():
        nome = str(row.iloc[0]).strip()
        if not nome or nome.lower() == "nan":
            continue
        resultado.append({
            "cobrador": _normalizar_nome(nome),
            "tempo_medio_diario_h": _float(row.iloc[1] if len(row) > 1 else None),
            "meta_diaria_h": _float(row.iloc[2] if len(row) > 2 else None),
            "pct_aderencia": _float(row.iloc[3] if len(row) > 3 else None),
            "ocorrencias_media_dia": _float(row.iloc[4] if len(row) > 4 else None),
            "acordos_media_dia": _float(row.iloc[5] if len(row) > 5 else None),
            "valor_medio_diario": _float(row.iloc[6] if len(row) > 6 else None),
            "total_acordos_valor": _float(row.iloc[7] if len(row) > 7 else None),
        })
    return pd.DataFrame(resultado)


# ============================================================
# TTO BRUTO (rel_produtividade_*.xlsx)
# ============================================================

def _ler_tto_bruto(bytes_arq: bytes, nome: str) -> dict:
    """
    Estrutura real:
    Linha 0: ACORDOS REALIZADOS | ACORDOS PROVISIONADOS (cabeçalho duplo)
    Linha 1: Negociador | Qtde. Ocorrências | TTO | Qtde. Processos | Quantidade | Total | Quantidade | Total | Data
    Linha 2+: dados diários (1 linha por cobrador por dia)
    """
    erros = []
    try:
        engine = "xlrd" if nome.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arq), header=None, engine=engine)

        # Acha linha do cabeçalho (contém 'Negociador' e 'TTO')
        header_idx = None
        for i, row in df.iterrows():
            vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
            if any("negociador" in v for v in vals) and any("tto" in v for v in vals):
                header_idx = i
                break

        if header_idx is None:
            return {"performance": pd.DataFrame(), "erros": [f"Cabeçalho TTO não encontrado em '{nome}'."]}

        # Renomeia colunas duplicadas
        colunas_raw = [str(c).strip() for c in df.iloc[header_idx].values]
        colunas = []
        contadores = {}
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
        # Acordos realizados: primeira coluna 'Total'
        col_ac_val = "Total" if "Total" in df.columns else _achar_col(df, ["total"])

        if not col_neg or not col_tto:
            return {"performance": pd.DataFrame(), "erros": [f"Colunas Negociador/TTO não encontradas em '{nome}'."]}

        df = df.dropna(subset=[col_neg])
        df = df[df[col_neg].astype(str).str.strip().str.len() > 0].copy()
        df["_tto_h"] = df[col_tto].apply(_tto_para_horas)

        # Normaliza nome — ERICKRAMIREZ → Erick Ramirez não é possível sem dicionário
        # Mas preservamos o nome original limpo
        df["_cobrador"] = df[col_neg].apply(lambda x: str(x).strip().title())

        total_dias = df[col_data].nunique() if col_data else df["_cobrador"].value_counts().max() or 1
        META_HORAS = 2.0
        resultado = []

        for cobrador, grupo in df.groupby("_cobrador"):
            if not cobrador or cobrador.lower() in ("nan", "none"):
                continue
            tempo_total_h = grupo["_tto_h"].sum()
            tempo_medio_h = tempo_total_h / total_dias
            total_ocorr = _safe_sum(grupo, col_occ)
            total_ac_val = _safe_sum(grupo, col_ac_val)

            resultado.append({
                "cobrador": cobrador,
                "tempo_medio_diario_h": round(tempo_medio_h, 4),
                "meta_diaria_h": META_HORAS,
                "pct_aderencia": round(tempo_medio_h / META_HORAS, 4),
                "ocorrencias_media_dia": round(total_ocorr / total_dias, 2),
                "acordos_media_dia": 0,
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
