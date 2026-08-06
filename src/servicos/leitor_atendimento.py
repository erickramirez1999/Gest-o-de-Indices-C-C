"""
Leitor de Atendimentos encerrados por finalização — LLE Índices (Cobrança).
CSV com colunas: Dia (DD/MM/YYYY); Motivo; Total de Finalizações.
Lê em UTF-8 (corrige acentuação) e normaliza os motivos (case/espaços/variações).
"""
from __future__ import annotations
import io
import re
from typing import Optional

import pandas as pd

# mapa de canonização de motivos (variações -> nome oficial)
_CANON = {
    "unknown": "Não informado",
}


def ler_atendimentos(arquivos: list[tuple[bytes, str]]) -> dict:
    res = {"registros": [], "erros": [], "arquivos": [], "anos": []}
    frames = []
    for bytes_arq, nome in arquivos:
        try:
            df = _ler_csv(bytes_arq)
        except Exception as e:
            res["erros"].append(f"'{nome}': {e}")
            continue
        if df is None or df.empty:
            res["erros"].append(f"'{nome}': vazio ou colunas não reconhecidas.")
            continue
        frames.append(df)
        res["arquivos"].append(f"{nome} → {len(df)} linhas")

    if not frames:
        return res
    full = pd.concat(frames, ignore_index=True)

    # canoniza motivos por case-insensitive (mantém a grafia mais frequente)
    full["motivo_limpo"] = full["motivo"].apply(_limpar_motivo)
    canon = _mapa_canonico(full["motivo_limpo"])
    full["motivo_final"] = full["motivo_limpo"].str.lower().map(canon).fillna(full["motivo_limpo"])

    registros = []
    for _, r in full.iterrows():
        if pd.isna(r["data"]):
            continue
        registros.append({
            "data": r["data"].date().isoformat(),
            "mes_ano": r["data"].strftime("%Y-%m"),
            "ano": int(r["data"].year),
            "motivo": r["motivo_final"],
            "total": int(r["total"]),
        })
    res["registros"] = registros
    res["anos"] = sorted({x["ano"] for x in registros})
    return res


def _ler_csv(bytes_arq: bytes) -> Optional[pd.DataFrame]:
    texto = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = bytes_arq.decode(enc)
            break
        except Exception:
            continue
    if texto is None:
        return None
    sep = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=sep)
    df.columns = [str(c).strip() for c in df.columns]
    c_dia = _col(df, ["dia", "data"])
    c_mot = _col(df, ["motivo"])
    c_tot = _col(df, ["total de finaliza", "total", "finaliza", "quantidade"])
    if not (c_dia and c_mot and c_tot):
        return None
    out = pd.DataFrame({
        "data": pd.to_datetime(df[c_dia], format="%d/%m/%Y", errors="coerce"),
        "motivo": df[c_mot].astype(str),
        "total": pd.to_numeric(df[c_tot], errors="coerce").fillna(0).astype(int),
    })
    return out[out["data"].notna()].copy()


def _limpar_motivo(m: str) -> str:
    s = str(m).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\bRC\s*-\s*", "RC - ", s)          # "RC-" / "RC -" -> "RC - "
    s = re.sub(r"\s+", " ", s).strip()
    if s.lower() in _CANON:
        return _CANON[s.lower()]
    return s


def _mapa_canonico(motivos: pd.Series) -> dict:
    """Para cada motivo (case-insensitive), escolhe a grafia mais frequente."""
    cont = {}
    for m in motivos:
        k = str(m).lower()
        cont.setdefault(k, {}).setdefault(m, 0)
        cont[k][m] += 1
    return {k: max(v.items(), key=lambda x: x[1])[0] for k, v in cont.items()}


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
