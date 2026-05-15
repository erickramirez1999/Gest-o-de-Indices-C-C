"""
Leitor dos arquivos mensais de Crédito.

Aceita MÚLTIPLOS arquivos — o sistema identifica automaticamente:

  - Arquivo com blocos Passaram Direto / Liberados / Negados → Liberações
  - Arquivo com colunas Cód.Parc. / Limite anterior / Novo limite → Aumento de Limite
  - Arquivo com coluna Tempo (minutos) + Desc Evento → Tempo Médio de Liberação
"""
from __future__ import annotations
import re
import io
import pandas as pd
from datetime import date, datetime
from typing import Optional


def ler_multiplos_arquivos_credito(arquivos: list[tuple[bytes, str]]) -> dict:
    """
    Lê múltiplos arquivos de crédito e consolida os resultados.

    Args:
        arquivos: lista de (bytes, nome_arquivo)

    Retorna: {
        'passaram_direto': DataFrame,
        'liberados': DataFrame,
        'negados': DataFrame,
        'limites': DataFrame,
        'erros': list[str],
        'arquivos_processados': list[str]
    }
    """
    resultado = {
        "passaram_direto": pd.DataFrame(),
        "liberados": pd.DataFrame(),
        "negados": pd.DataFrame(),
        "limites": pd.DataFrame(),
        "tempo_tela": pd.DataFrame(),
        "erros": [],
        "arquivos_processados": [],
    }

    for bytes_arq, nome in arquivos:
        tipo = _detectar_tipo_credito(bytes_arq, nome)
        resultado["arquivos_processados"].append(f"{nome} → {tipo}")

        if tipo == "LIBERACOES":
            r = ler_liberacoes(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            for chave in ["passaram_direto", "liberados", "negados"]:
                if not r[chave].empty:
                    if resultado[chave].empty:
                        resultado[chave] = r[chave]
                    else:
                        resultado[chave] = pd.concat(
                            [resultado[chave], r[chave]], ignore_index=True
                        )

        elif tipo == "LIMITE":
            r = ler_aumento_limite(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            if not r["dados"].empty:
                if resultado["limites"].empty:
                    resultado["limites"] = r["dados"]
                else:
                    resultado["limites"] = pd.concat(
                        [resultado["limites"], r["dados"]], ignore_index=True
                    )

        elif tipo == "TEMPO_TELA":
            r = ler_tempo_tela(bytes_arq, nome)
            resultado["erros"] += r["erros"]
            if not r["dados"].empty:
                if resultado["tempo_tela"].empty:
                    resultado["tempo_tela"] = r["dados"]
                else:
                    resultado["tempo_tela"] = pd.concat(
                        [resultado["tempo_tela"], r["dados"]], ignore_index=True
                    )

        else:
            resultado["erros"].append(f"'{nome}': formato não reconhecido, ignorado.")

    return resultado


# ============================================================
# DETECÇÃO DE TIPO
# ============================================================

def _detectar_tipo_credito(bytes_arq: bytes, nome: str) -> str:
    """Detecta se é arquivo de Liberações, Aumento de Limite ou Tempo de Tela."""
    nome_lower = nome.lower()

    # Por nome do arquivo — mais específico primeiro
    if any(p in nome_lower for p in ["tempo_de_tela", "tempo de tela", "tto"]):
        return "TEMPO_TELA"
    if any(p in nome_lower for p in ["liberado", "negado", "passaram", "pedido", "fin_lib", "liberac"]):
        return "LIBERACOES"
    if any(p in nome_lower for p in ["limite", "aumento", "limit"]):
        return "LIMITE"
    if "tempo" in nome_lower and "tela" in nome_lower:
        return "TEMPO_TELA"

    # Por conteúdo da primeira célula (linha 0 do arquivo)
    try:
        engine = "xlrd" if nome_lower.endswith(".xls") else "openpyxl"
        df_peek = pd.read_excel(io.BytesIO(bytes_arq), nrows=3, header=None, engine=engine)
        # Primeira célula geralmente identifica o bloco
        primeira_celula = str(df_peek.iloc[0, 0]).lower().strip() if len(df_peek) > 0 else ""
        texto_tudo = " ".join(str(v).lower() for v in df_peek.values.flatten() if pd.notna(v))

        if primeira_celula in ("liberados", "negados", "passaram direto", "passaram_direto"):
            return "LIBERACOES"
        if any(p in texto_tudo for p in ["limite anterior", "novo limite", "variação", "variacao"]):
            return "LIMITE"
        # Tempo de tela: tem "desc evento" E "tempo" mas NÃO tem "vlr pedido"
        if "desc evento" in texto_tudo and "tempo" in texto_tudo and "vlr pedido" not in texto_tudo:
            return "TEMPO_TELA"
        if any(p in texto_tudo for p in ["vlr pedido", "passaram direto", "liberados", "negados"]):
            return "LIBERACOES"
        if "nro único" in texto_tudo or "nro unico" in texto_tudo:
            if "desc evento" in texto_tudo and "vlr pedido" not in texto_tudo:
                return "TEMPO_TELA"
            return "LIBERACOES"
    except Exception:
        pass

    return "DESCONHECIDO"


# ============================================================
# LEITURA DE TEMPO DE TELA (FIN - Tempo Médio de Liberação)
# ============================================================

def ler_tempo_tela(bytes_arquivo: bytes, nome_arquivo: str) -> dict:
    """
    Lê o arquivo de Tempo Médio de Liberação.
    Colunas: Nro Único, Cód Usuário Liberação, Nome, Evento, Desc Evento, Tempo
    Agrupa por analista e calcula tempo médio total.
    """
    erros = []
    try:
        engine = "xlrd" if nome_arquivo.lower().endswith(".xls") else "openpyxl"
        # Linha 0: metadado (Emissão, Total de registros...)
        # Linha 1: cabeçalho real (Nro Único, Nome, Evento, Tempo...)
        df = pd.read_excel(io.BytesIO(bytes_arquivo), header=None, engine=engine)
        # Acha linha do cabeçalho real (contém "Nome" e "Tempo")
        header_idx = None
        for i, row in df.iterrows():
            vals = [str(v).lower() for v in row.values if pd.notna(v)]
            if any("nome" in v for v in vals) and any("tempo" in v for v in vals):
                header_idx = i
                break
        if header_idx is None:
            return {"dados": pd.DataFrame(), "erros": [f"Cabeçalho não encontrado em '{nome_arquivo}'."]}
        df.columns = [str(c).strip() for c in df.iloc[header_idx]]
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
    except Exception as e:
        return {"dados": pd.DataFrame(), "erros": [f"Erro ao abrir '{nome_arquivo}': {e}"]}

    # Acha coluna de nome do analista e tempo
    col_nome = _achar_col(df, ["nome"])
    col_tempo = _achar_col(df, ["tempo"])
    col_evento = _achar_col(df, ["desc evento", "descevento"])
    col_nro = _achar_col(df, ["nro único", "nro unico"])

    if not col_nome or not col_tempo:
        return {"dados": pd.DataFrame(), "erros": [f"Colunas Nome/Tempo não encontradas em '{nome_arquivo}'."]}

    df = df.dropna(subset=[col_nome])
    df = df[df[col_nome].astype(str).str.strip().str.len() > 0]

    # Converte tempo (ex: "3 minutos", "2 horas 5 minutos") para minutos
    df["_minutos"] = df[col_tempo].apply(_tempo_para_minutos)
    df["_analista"] = df[col_nome].apply(lambda x: _normalizar_nome(str(x)))

    total_registros = len(df)
    resultado = []

    for analista, grupo in df.groupby("_analista"):
        if not analista or analista.lower() in ("nan", "none"):
            continue
        total_min = grupo["_minutos"].sum()
        qtd = len(grupo)
        resultado.append({
            "analista": analista,
            "qtd_pedidos": qtd,
            "tempo_total_min": round(total_min, 1),
            "tempo_medio_min": round(total_min / qtd, 1) if qtd else 0,
        })

    return {"dados": pd.DataFrame(resultado), "erros": erros}


def _tempo_para_minutos(v) -> float:
    """Converte strings como '3 minutos', '2 horas 5 minutos', '1 horas 1 minutos' para minutos."""
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return 0.0
        s = str(v).lower().strip()
        horas = 0
        minutos = 0
        import re
        h_match = re.search(r"(\d+)\s*hora", s)
        m_match = re.search(r"(\d+)\s*minuto", s)
        if h_match:
            horas = int(h_match.group(1))
        if m_match:
            minutos = int(m_match.group(1))
        return horas * 60 + minutos
    except Exception:
        return 0.0


# ============================================================
# LEITURA DE LIBERAÇÕES
# ============================================================

def ler_liberacoes(bytes_arquivo: bytes, nome_arquivo: str) -> dict:
    erros = []
    resultado = {
        "passaram_direto": pd.DataFrame(),
        "liberados": pd.DataFrame(),
        "negados": pd.DataFrame(),
        "erros": erros,
    }

    try:
        engine = "xlrd" if nome_arquivo.lower().endswith(".xls") else "openpyxl"
        abas = pd.read_excel(
            io.BytesIO(bytes_arquivo), sheet_name=None,
            header=None, engine=engine,
        )
    except Exception as e:
        erros.append(f"Erro ao abrir '{nome_arquivo}': {e}")
        return resultado

    nomes = list(abas.keys())

    # Estratégia 1: abas separadas
    mapa = {
        "passaram_direto": _achar_aba(nomes, ["direto", "passaram"]),
        "liberados": _achar_aba(nomes, ["liberado"]),
        "negados": _achar_aba(nomes, ["negado", "reprovad"]),
    }
    if all(mapa.values()):
        for chave, nome_aba in mapa.items():
            try:
                resultado[chave] = _limpar_bloco(abas[nome_aba], chave)
            except Exception as e:
                erros.append(f"Erro bloco {chave} em '{nome_arquivo}': {e}")
        return resultado

    # Estratégia 2: única aba com separadores
    try:
        primeira = list(abas.values())[0]
        blocos = _separar_blocos(primeira)
        resultado.update(blocos)
    except Exception as e:
        erros.append(f"Erro ao separar blocos em '{nome_arquivo}': {e}")

    return resultado


def _limpar_bloco(df: pd.DataFrame, tipo: str) -> pd.DataFrame:
    """
    Estrutura real dos arquivos:
    Linha 0: nome do bloco (Liberados / Negados / Passaram direto)
    Linha 1: metadado (Emissão, Total de registros, Usuário)
    Linha 2: cabeçalho real (Nro Único, Cód.Parceiro, Parceiro, TOP, Vlr Pedido...)
    Linha 3+: dados reais
    Última linha: total (soma dos valores — deve ser ignorada)
    """
    df = df.reset_index(drop=True)

    # Acha linha do cabeçalho real (contém 'nro')
    header_idx = None
    for i, row in df.iterrows():
        vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if any(v.startswith("nro") for v in vals):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    colunas = [str(c).strip() for c in df.iloc[header_idx].values]
    df_dados = df.iloc[header_idx + 1:].copy()
    df_dados.columns = colunas
    df_dados = df_dados.reset_index(drop=True)

    # Remove linhas sem Nro Único numérico válido (exclui totais e linhas vazias)
    col_nro = _achar_col(df_dados, ["nro único", "nro unico"])
    if col_nro:
        df_dados = df_dados[pd.to_numeric(df_dados[col_nro], errors="coerce").notna()].copy()

    # Remove linha de total (última linha onde Vlr Pedido é soma — geralmente muito maior)
    col_vlr = _achar_col(df_dados, ["vlr pedido", "vlr. pedido"])
    if col_vlr:
        df_dados = df_dados[pd.to_numeric(df_dados[col_vlr], errors="coerce").notna()].copy()

    # Extrai analista do campo Eventos
    col_ev = _achar_col(df_dados, ["evento"])
    if col_ev:
        df_dados["analista"] = df_dados[col_ev].apply(_extrair_analista)
    else:
        df_dados["analista"] = ""

    tipo_map = {
        "passaram_direto": "DIRETO",
        "liberados": "LIBERADO",
        "negados": "NEGADO",
    }

    resultado = []
    for _, row in df_dados.iterrows():
        resultado.append({
            "vlr_pedido": _float(_get(row, ["vlr pedido", "vlr. pedido"])),
            "cod_empresa": _int(_get(row, ["cód. empresa", "cód.empresa", "cod empresa"])),
            "tipo": tipo_map.get(tipo, "DIRETO"),
            "analista": str(row.get("analista", "") or ""),
        })
    return pd.DataFrame(resultado)


def _separar_blocos(df: pd.DataFrame) -> dict:
    CHAVES = [
        ("passaram_direto", ["passaram direto"]),
        ("liberados", ["liberados"]),
        ("negados", ["negados"]),
    ]
    indices = {}
    for i, row in df.iterrows():
        texto = " ".join(str(v).lower() for v in row.values if pd.notna(v))
        for chave, palavras in CHAVES:
            if chave not in indices and any(p in texto for p in palavras):
                indices[chave] = i
                break

    ordenadas = sorted(indices.items(), key=lambda x: x[1])
    resultado = {}
    for idx, (chave, inicio) in enumerate(ordenadas):
        fim = ordenadas[idx + 1][1] if idx + 1 < len(ordenadas) else len(df)
        bloco = df.iloc[inicio:fim].copy()
        resultado[chave] = _limpar_bloco(bloco, chave)
    return resultado


# ============================================================
# LEITURA DE AUMENTO DE LIMITE
# ============================================================

def ler_aumento_limite(bytes_arquivo: bytes, nome_arquivo: str) -> dict:
    """
    Estrutura real:
    Linha 0: 'arquivo'
    Linha 1: metadado (Emissão, Total registros, Usuário)
    Linha 2: cabeçalho (Cód.Parc., Nome, Dh. Incluão, Limite anterior, Novo limite, Variação, Dt revisão)
    Linha 3+: dados — Dt revisão às vezes tem nome do analista em vez de data
    """
    erros = []
    try:
        engine = "xlrd" if nome_arquivo.lower().endswith(".xls") else "openpyxl"
        df = pd.read_excel(io.BytesIO(bytes_arquivo), header=None, engine=engine)

        # Acha linha do cabeçalho (contém 'Cód' ou 'Nome')
        header_idx = None
        for i, row in df.iterrows():
            vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
            if any("cód" in v or "cod" in v for v in vals) and any("nome" in v for v in vals):
                header_idx = i
                break

        if header_idx is None:
            return {"dados": pd.DataFrame(), "erros": [f"Cabeçalho não encontrado em '{nome_arquivo}'."]}

        colunas = [str(c).strip() for c in df.iloc[header_idx].values]
        df_dados = df.iloc[header_idx + 1:].copy()
        df_dados.columns = colunas
        df_dados = df_dados.reset_index(drop=True)

        # Remove linhas sem código de parceiro numérico
        col0 = colunas[0]
        df_dados = df_dados.dropna(subset=[col0])
        df_dados = df_dados[pd.to_numeric(df_dados[col0], errors="coerce").notna()]

        resultado = []
        for _, row in df_dados.iterrows():
            # Dt revisão às vezes tem nome do analista
            dt_revisao_raw = row.get("Dt revisão", row.get("Dt.revisão", ""))
            analista = ""
            data_revisao = None
            if isinstance(dt_revisao_raw, str) and not dt_revisao_raw.replace("/", "").replace("-", "").isdigit():
                analista = _normalizar_nome(dt_revisao_raw)
            else:
                data_revisao = _parse_data(dt_revisao_raw)

            resultado.append({
                "cod_parceiro": _int(row.get("Cód.Parc.", row.get("Cód. Parc."))),
                "nome": str(row.get("Nome", "") or ""),
                "data_inclusao": _parse_data(row.get("Dh. Incluão", row.get("Dh. Inclusão"))),
                "limite_anterior": _float(row.get("Limite anterior")),
                "novo_limite": _float(row.get("Novo limite")),
                "variacao": _float(row.get("Variação")),
                "data_revisao": data_revisao,
                "analista": analista,
            })

        return {"dados": pd.DataFrame(resultado), "erros": erros}
    except Exception as e:
        return {"dados": pd.DataFrame(), "erros": [f"Erro ao ler limite '{nome_arquivo}': {e}"]}


# ============================================================
# HELPERS
# ============================================================

_REGEX_ANALISTA = re.compile(r"-\s*([A-Z][A-Z]+\.?[A-Z]+)\s+\d{2}/\d{2}/\d{4}")


def _extrair_analista(texto) -> str:
    if not isinstance(texto, str):
        return ""
    m = _REGEX_ANALISTA.search(texto)
    return _normalizar_nome(m.group(1)) if m else ""


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


def _get(row, nomes: list[str]):
    for n in nomes:
        for k in row.index:
            if n in str(k).lower():
                return row[k]
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
        s = str(v).strip()[:10]
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                continue
        return None
    except Exception:
        return None
