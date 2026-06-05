"""
Parser de Nota Fiscal de Serviços Eletrônica (NFS-e) em PDF.

Suporta os principais formatos brasileiros:
  - SP (Prefeitura de São Paulo)
  - RJ (Prefeitura do Rio de Janeiro - DANFSe v1.0)
  - SC e outras prefeituras municipais (modelo Tubarão, ACBr)

Estratégia:
  1. Extrai todo o texto do PDF
  2. Identifica os 2 CNPJs (prestador = fornecedor; tomador = empresa LLE pagadora)
  3. Extrai valor total, data, número, descrição
  4. Retorna um dataclass NotaFiscal pra ser persistido
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Optional

import pdfplumber


# CNPJs das empresas LLE (tomadores conhecidos)
# Usado pra identificar qual é o PAGADOR e qual é o FORNECEDOR
CNPJS_LLE = {
    "05.953.543/0001-47": "PISA",         # Matriz - L.L.E. FERRAGENS LTDA (RJ)
    "05.953.543/0002-28": "KING",         # Filial Duque de Caxias
    # Adicione novos aqui quando aparecerem (ex: TRIO)
}


@dataclass
class NotaFiscal:
    """Dados extraídos de uma NF eletrônica."""
    # Fornecedor (prestador)
    cnpj_prestador: str
    nome_prestador: str
    municipio_prestador: Optional[str] = None
    uf_prestador: Optional[str] = None

    # Tomador (pagador - LLE)
    cnpj_tomador: Optional[str] = None
    empresa_lle: Optional[str] = None  # PISA / KING / TRIO / OUTRO

    # Dados da nota
    numero_nf: Optional[str] = None
    data_emissao: Optional[date] = None
    competencia_mes_ano: Optional[str] = None  # 'YYYY-MM'
    valor_total: float = 0.0
    descricao_servico: Optional[str] = None

    # Diagnóstico
    aviso: Optional[str] = None        # se algum campo ficou faltando
    texto_bruto: Optional[str] = None  # pra debug


# ============================================================
# UTILITÁRIOS
# ============================================================

def _limpar_cnpj(s: str) -> str:
    """Retorna CNPJ no formato 00.000.000/0000-00 (mantém pontuação)."""
    return s.strip()


def _parse_valor_brl(s: str) -> Optional[float]:
    """'1.500,00' -> 1500.0"""
    if not s:
        return None
    s = s.strip().replace("R$", "").replace(" ", "")
    # Formato brasileiro: 1.500,00 -> 1500.00
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_data_brl(s: str) -> Optional[date]:
    """'03/06/2026' -> date(2026, 6, 3)"""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _extrair_texto(arquivo) -> str:
    """Lê PDF (path, bytes ou file-like) e retorna texto concatenado."""
    if isinstance(arquivo, bytes):
        arquivo = BytesIO(arquivo)
    with pdfplumber.open(arquivo) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def _detectar_formato_rj_sem_espaco(texto: str) -> bool:
    """
    Detecta o formato DANFSe v1.0 do Rio de Janeiro, que vem com palavras
    sem espaço (ex: 'ValordoServiço' em vez de 'Valor do Serviço').
    """
    return (
        "DANFSe" in texto
        and ("ValordoServiço" in texto or "NúmerodaNFS-e" in texto)
    )


# ============================================================
# PARSER PRINCIPAL
# ============================================================

def ler_nf_pdf(arquivo, nome_arquivo: str = "") -> NotaFiscal:
    """
    Lê uma NF eletrônica em PDF e extrai todos os campos relevantes.

    Args:
        arquivo: caminho, bytes, BytesIO ou UploadedFile do Streamlit
        nome_arquivo: pra log

    Returns:
        NotaFiscal preenchida (com aviso se algo ficou faltando)
    """
    # Streamlit UploadedFile tem .getvalue()
    if hasattr(arquivo, "getvalue"):
        arquivo = arquivo.getvalue()

    texto = _extrair_texto(arquivo)
    if not texto.strip():
        nf = NotaFiscal(cnpj_prestador="", nome_prestador="DESCONHECIDO")
        nf.aviso = "PDF não tem texto extraível (pode ser imagem/scan)."
        return nf

    # 1) CNPJs
    cnpjs = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    cnpjs_unicos = []
    for c in cnpjs:
        if c not in cnpjs_unicos:
            cnpjs_unicos.append(c)

    cnpj_tomador = None
    cnpj_prestador = None

    # Estratégia: o tomador é o que está na lista LLE; o prestador é o outro
    for c in cnpjs_unicos:
        if c in CNPJS_LLE:
            cnpj_tomador = c
        elif not cnpj_prestador:
            cnpj_prestador = c

    # Se não achou tomador LLE, usa o último; prestador = primeiro
    if not cnpj_prestador and cnpjs_unicos:
        cnpj_prestador = cnpjs_unicos[0]
    if not cnpj_tomador and len(cnpjs_unicos) > 1:
        cnpj_tomador = cnpjs_unicos[1]

    empresa_lle = CNPJS_LLE.get(cnpj_tomador) if cnpj_tomador else None

    # 2) Nome do prestador
    nome_prestador = _extrair_nome_prestador(texto, cnpj_prestador)

    # 3) Município/UF do prestador
    municipio, uf = _extrair_municipio_uf_prestador(texto)

    # 4) Valor total da nota
    valor = _extrair_valor_total(texto)

    # 5) Data de emissão
    data_emissao = _extrair_data_emissao(texto)

    # 6) Competência (YYYY-MM)
    competencia = _extrair_competencia(texto, data_emissao)

    # 7) Número da NF
    numero_nf = _extrair_numero_nf(texto)

    # 8) Descrição do serviço
    descricao = _extrair_descricao(texto)

    # Diagnóstico
    avisos = []
    if not cnpj_prestador:
        avisos.append("CNPJ do prestador não identificado")
    if not valor or valor <= 0:
        avisos.append("Valor total não identificado")
    if not nome_prestador or nome_prestador == "DESCONHECIDO":
        avisos.append("Nome do prestador não identificado")

    aviso = " · ".join(avisos) if avisos else None

    return NotaFiscal(
        cnpj_prestador=cnpj_prestador or "",
        nome_prestador=nome_prestador,
        municipio_prestador=municipio,
        uf_prestador=uf,
        cnpj_tomador=cnpj_tomador,
        empresa_lle=empresa_lle,
        numero_nf=numero_nf,
        data_emissao=data_emissao,
        competencia_mes_ano=competencia,
        valor_total=valor or 0.0,
        descricao_servico=descricao,
        aviso=aviso,
        texto_bruto=texto[:2000],
    )


# ============================================================
# EXTRATORES ESPECÍFICOS
# ============================================================

def _extrair_nome_prestador(texto: str, cnpj_prestador: Optional[str]) -> str:
    """Acha o nome/razão social do prestador."""
    if not cnpj_prestador:
        return "DESCONHECIDO"

    # FORMATO RJ DANFSe SEM ESPAÇO:
    # "Nome/NomeEmpresarial E-mail\nINSTITUTODEESTUDOSDEPROTESTODETITULOSDOBRASIL-\nSECCIONALRJ\nEndereço"
    # O label tem "E-mail" na MESMA linha ('Nome/NomeEmpresarial E-mail').
    m = re.search(
        r"Nome/NomeEmpresarial\s*E-?mail\s*\n([\s\S]+?)\nEndere[çc]o",
        texto, re.IGNORECASE,
    )
    if m:
        nome_bruto = m.group(1)
        # Limpa: tira hífens soltos, quebras de linha, espaços extras
        nome = re.sub(r"[\n\r]+", " ", nome_bruto)
        nome = re.sub(r"\s*-\s*-\s*", " ", nome)  # "- -" vira espaço
        nome = re.sub(r"\s+-\s+", " ", nome)
        nome = re.sub(r"\s+", " ", nome).strip(" -.")
        nome = _separar_palavras_coladas(nome)
        nome = re.sub(r"\s+", " ", nome).strip()
        if 3 < len(nome) < 200:
            return nome.upper()

    # FORMATO NORMAL (com espaços): SP, Tubarão, etc
    padroes = [
        r"Nome\s*/?\s*Raz[ãa]o\s*(?:Social|Empresarial)?\s*:?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ&\s\.\-]+?)(?:\n|CPF|CNPJ|Endereço|E-mail|Telefone|Inscri)",
        r"PRESTADOR\s*(?:DE\s*SERVI[ÇC]OS?)?\s*[\n:]+\s*(?:Nome[^:]*:)?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ&\s\.\-]+?)(?:\n|CPF|CNPJ)",
    ]

    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            nome = m.group(1).strip(" .-:")
            nome = re.sub(r"\s+", " ", nome)
            if 3 < len(nome) < 100 and not nome.isdigit():
                return nome.upper()

    # Padrão fallback: linhas próximas ao CNPJ do prestador
    linhas = texto.split("\n")
    for i, linha in enumerate(linhas):
        if cnpj_prestador in linha:
            for j in range(max(0, i - 5), i):
                cand = linhas[j].strip()
                if cand and not any(t in cand.lower() for t in [
                    "cpf", "cnpj", "inscri", "endere", "telefone",
                    "e-mail", "prestador", "tomador", "município",
                    "nº", "competência", "data",
                ]):
                    cand = re.sub(r"[^\w\s\.\-&áéíóúâêôãõç]", " ", cand, flags=re.I).strip()
                    if 3 < len(cand) < 100 and not cand.isdigit():
                        return cand.upper()
            break

    return "DESCONHECIDO"


def _separar_palavras_coladas(texto: str) -> str:
    """
    Tenta reseparar palavras grudadas (formato DANFSe RJ).
    Ex: 'INSTITUTODEESTUDOSDEPROTESTO' -> 'INSTITUTO DE ESTUDOS DE PROTESTO'

    Algoritmo:
      1. Lista palavras esperadas (em ordem de prioridade — longas primeiro)
      2. Marca as ocorrências DAS LONGAS com um delimitador especial
      3. Só DEPOIS aplica as curtas (DE/DO/DA), que poderiam quebrar as longas
    """
    if not texto or len(texto) < 8:
        return texto

    # Palavras longas (devem ser preservadas se aparecerem)
    longas = [
        "INSTITUTO", "ESTUDOS", "PROTESTO", "TÍTULOS", "TITULOS",
        "BRASIL", "SECCIONAL", "COMPLEMENTAR",
        "INFORMÁTICA", "INFORMATICA", "TECNOLOGIA", "ELETRÔNICA",
        "ELETRONICA", "DIGITAL", "EMPRESARIAL",
        "COMERCIO", "COMÉRCIO", "SERVIÇOS", "SERVICOS",
        "SERVIÇO", "SERVICO", "FERRAGENS", "PARCERIA",
        "CONSULTORIA", "ASSESSORIA",
        "LTDA", "EPP", "ME",
    ]

    # Curtas (só aplica em sobras)
    curtas = ["DOS", "DAS", "PARA", "POR", "COM",
              "DE", "DO", "DA", "EM", "OU",
              "RJ", "SP", "MG", "RS", "SC"]

    resultado = texto

    # Aplica palavras LONGAS — separa antes e depois
    for p in longas:
        # Garante que a palavra ficou separada (mas só nas ocorrências existentes)
        resultado = re.sub(
            rf"(?i)({re.escape(p)})",
            r" \1 ",
            resultado,
        )

    # Limpa espaços múltiplos antes de aplicar curtas
    resultado = re.sub(r"\s+", " ", resultado).strip()

    # Aplica CURTAS — mas só onde está colada entre 2 palavras já separadas
    # Ex: "INSTITUTODEESTUDOS" depois das longas vira "INSTITUTO DEESTUDOS"
    # Quero "INSTITUTO DE ESTUDOS"
    for p in curtas:
        # Padrão: palavra-curta colada NO INÍCIO de algo
        resultado = re.sub(
            rf"(?i)(?<=\s)({re.escape(p)})(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])",
            r"\1 ",
            resultado,
        )

    return re.sub(r"\s+", " ", resultado).strip()


def _extrair_municipio_uf_prestador(texto: str) -> tuple[Optional[str], Optional[str]]:
    """Acha município e UF do prestador (primeiro bloco de endereço)."""
    # SP: "Município: XXX UF: SP"
    m = re.search(r"Munic[íi]pio\s*:?\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç\s]+?)\s+UF\s*:?\s*([A-Z]{2})", texto)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, None


def _extrair_valor_total(texto: str) -> Optional[float]:
    """Acha o valor total da nota — tenta vários padrões."""
    padroes = [
        # SP: "VALOR TOTAL DO SERVIÇO = R$ 12.000,00"
        r"VALOR\s+TOTAL\s+DO\s+SERVI[ÇC]O\s*=?\s*R?\$?\s*([\d.,]+)",
        # Tubarão: "VALOR TOTAL DA NOTA = R$ 1.500,00"
        r"VALOR\s+TOTAL\s+DA\s+NOTA\s*=?\s*R?\$?\s*([\d.,]+)",
        # SP novo: "VALOR TOTAL COBRADO = R$ 12.000,00"
        r"VALOR\s+TOTAL\s+COBRADO\s*=?\s*R?\$?\s*([\d.,]+)",
        # RJ formato normal: "Valor Líquido da NFS-e\nR$ 578,97"
        r"Valor\s+L[íi]quido(?:\s+da\s+NFS-?e)?\s*[\n:]*\s*R?\$?\s*([\d.,]+)",
        # RJ DANFSe SEM ESPAÇO: "ValorLíquidodaNFS-e\nR$597,35" (label e valor podem ter texto entre eles)
        r"ValorL[íi]quidodaNFS-?e[\s\S]{0,80}?R\$\s*([\d.,]+)",
        # Fallback: "Valor do Serviço" (RJ normal)
        r"Valor\s+do\s+Servi[çc]o\s*[\n:]*\s*R?\$?\s*([\d.,]+)",
        # Fallback RJ SEM ESPAÇO
        r"ValordoServi[çc]o[\s\S]{0,80}?R\$\s*([\d.,]+)",
    ]
    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            v = _parse_valor_brl(m.group(1))
            if v and v > 0:
                return v
    return None


def _extrair_data_emissao(texto: str) -> Optional[date]:
    """Acha a data de emissão da NF."""
    padroes = [
        r"Data\s+(?:e\s+Hora\s+)?d[ae]\s+[Ee]miss[ãa]o\s*[\n:]*\s*(\d{2}/\d{2}/\d{4})",
        r"Data\s+de\s+Emiss[ãa]o\s+da?\s+NFS?-?e\s*[\n:]*\s*(\d{2}/\d{2}/\d{4})",
    ]
    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            d = _parse_data_brl(m.group(1))
            if d:
                return d
    # Fallback: primeira data DD/MM/YYYY do texto
    m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", texto)
    if m:
        return _parse_data_brl(m.group(1))
    return None


def _extrair_competencia(texto: str, data_emissao: Optional[date]) -> Optional[str]:
    """
    Acha a competência (mês de referência).
    Formato esperado: '2026-06'.
    Fallback: usa o mês da data_emissao.
    """
    # "Competência da NFS-e\n01/06/2026" ou "Competência\n06/2026"
    m = re.search(r"Compet[êe]ncia[^\n:]*[\n:]+\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    if m:
        d = _parse_data_brl(m.group(1))
        if d:
            return f"{d.year:04d}-{d.month:02d}"

    m = re.search(r"Compet[êe]ncia[^\n:]*[\n:]+\s*(\d{2})/(\d{4})", texto, re.IGNORECASE)
    if m:
        mes = int(m.group(1))
        ano = int(m.group(2))
        return f"{ano:04d}-{mes:02d}"

    if data_emissao:
        return f"{data_emissao.year:04d}-{data_emissao.month:02d}"
    return None


def _extrair_numero_nf(texto: str) -> Optional[str]:
    """Acha o número da NF."""
    padroes = [
        # SP/SC normal: "Número da Nota\nXXX"
        r"N[úu]mero\s+da\s+N(?:ota|FS-?e)\s*[\n:]*\s*([\d.]+)",
        # RJ DANFSe sem espaço: "NúmerodaNFS-e\nCompetência...\n1154"
        r"N[úu]merodaNFS-?e\s*[\s\S]{0,80}?\n(\d{3,8})\s",
        # SP novo: "Número da Nota\n00000419"
        r"00000\d{3,}",
    ]
    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            num = m.groups()[0] if m.groups() else m.group(0)
            num = num.strip(" .")
            if num and num != "0":
                return num
    return None


def _extrair_descricao(texto: str) -> Optional[str]:
    """Acha a descrição dos serviços (texto livre)."""
    padroes = [
        # SP: "DISCRIMINAÇÃO DE SERVIÇOS\nXXX\nVALOR TOTAL"
        r"DISCRIMINA[ÇC][ÃA]O\s+D[OE]S?\s+SERVI[ÇC]OS?\s*[\n:]+(.+?)(?:VALOR\s+TOTAL|Código|TRIBUTOS|C[óo]digo\s+d[ao]\s+Servi[çc]o)",
        # RJ normal: "Descrição do Serviço\nXXX"
        r"Descri[çc][ãa]o\s+do\s+Servi[çc]o\s*[\n:]+(.+?)(?:TRIBUTA[ÇC][ÃA]O|VALOR|Tributa)",
        # RJ DANFSe sem espaço: "DescriçãodoServiço\nSERVIÇOCOMPLEMENTAR.\nTRIBUTAÇÃOMUNICIPAL"
        r"Descri[çc][ãa]odoServi[çc]o\s*[\n]+(.+?)(?:TRIBUTA|VALOR)",
    ]
    for pat in padroes:
        m = re.search(pat, texto, re.IGNORECASE | re.DOTALL)
        if m:
            d = m.group(1).strip()
            # Pega só a primeira linha não-vazia
            for linha in d.split("\n"):
                linha = linha.strip()
                if 5 < len(linha) < 250 and not linha.isupper():
                    return linha
                if 5 < len(linha) < 250:
                    # Vale também se for tudo maiúsculo, último recurso
                    return _separar_palavras_coladas(linha) if " " not in linha else linha
            if 5 < len(d) < 500:
                return d.split("\n")[0].strip()
    return None
