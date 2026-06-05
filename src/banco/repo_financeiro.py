"""
Repositório do módulo Financeiro.

Operações:
  - Fornecedores (cadastro automático a partir das NFs)
  - Lançamentos de gasto (1 por NF)
  - Listagem por mês
  - Helpers de categoria sugerida
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.banco.conexao import obter_conexao


# ============================================================
# CATEGORIAS PADRÃO (sugeridas a partir da descrição da NF)
# ============================================================

# Mapeamento de palavras-chave → categoria sugerida.
# Aplicado SÓ na primeira vez que o CNPJ é cadastrado (auto-sugestão).
# Depois o usuário pode mudar pelo cadastro do fornecedor.
_HEURISTICAS_CATEGORIA = [
    ("PROTESTO", ["PROTESTO", "CARTORIO", "CARTÓRIO", "TÍTULOS"]),
    ("SOFTWARE", ["SOFTWARE", "SISTEMA", "TECNOLOGIA", "INTEGRAÇÃO",
                  "INTEGRACAO", "INFORMÁTICA", "INFORMATICA", "TI",
                  "MANUTENÇÃO DO SISTEMA", "LICENCIAMENTO"]),
    ("HOSPEDAGEM", ["HOSPEDAGEM", "CLOUD", "ARMAZENAMENTO", "HOSTING"]),
    ("CONTABIL", ["CONTÁBIL", "CONTABIL", "CONTABILIDADE", "CONTADOR"]),
    ("JURÍDICO", ["ADVOGADO", "JURÍDICO", "JURIDICO", "ADVOCACIA"]),
    ("MARKETING", ["MARKETING", "PUBLICIDADE", "ANÚNCIOS", "ADS"]),
    ("CONSULTORIA", ["CONSULTORIA", "ASSESSORIA"]),
    ("TRANSPORTE", ["TRANSPORTE", "FRETE", "ENTREGA", "LOGÍSTICA"]),
    ("TELECOM", ["TELEFONE", "INTERNET", "TELECOM", "BANDA"]),
    ("ALUGUEL", ["ALUGUEL", "LOCAÇÃO", "LOCACAO"]),
    ("ENERGIA", ["ENERGIA", "LIGHT", "ENEL", "CEMIG"]),
    ("ÁGUA", ["ÁGUA", "AGUA", "CEDAE"]),
    ("LIMPEZA", ["LIMPEZA", "CONSERVAÇÃO"]),
    ("MATERIAL", ["MATERIAL DE", "PAPELARIA", "SUPRIMENTOS"]),
    ("BANCO", ["TARIFA", "BANCÁRIA", "BANCARIA"]),
]


def sugerir_categoria(descricao_servico: Optional[str], nome_fornecedor: Optional[str] = None) -> Optional[str]:
    """
    A partir da descrição do serviço (ou nome do fornecedor), sugere uma
    categoria. Retorna None se não bater com nenhuma heurística.
    """
    base = " ".join(filter(None, [descricao_servico, nome_fornecedor])).upper()
    if not base.strip():
        return None
    for categoria, palavras_chave in _HEURISTICAS_CATEGORIA:
        for kw in palavras_chave:
            if kw.upper() in base:
                return categoria
    return None


# ============================================================
# FORNECEDORES
# ============================================================

def buscar_fornecedor_por_cnpj(cnpj: str) -> Optional[dict]:
    """Retorna o fornecedor cadastrado pelo CNPJ, ou None."""
    if not cnpj:
        return None
    sb = obter_conexao()
    res = sb.table("fornecedor_financeiro").select("*").eq("cnpj", cnpj).limit(1).execute()
    return res.data[0] if res.data else None


def criar_fornecedor_automatico(
    cnpj: str,
    nome: str,
    categoria: Optional[str] = None,
    descricao_servico: Optional[str] = None,
    municipio: Optional[str] = None,
    uf: Optional[str] = None,
    criado_por_id: Optional[int] = None,
) -> dict:
    """
    Cadastra um novo fornecedor automaticamente (chamado durante o upload).
    Se categoria não for fornecida, tenta sugerir a partir da descrição.
    """
    cat = categoria or sugerir_categoria(descricao_servico, nome) or "OUTROS"
    sb = obter_conexao()
    payload = {
        "cnpj": cnpj,
        "nome": nome,
        "categoria": cat,
        "descricao_servico_padrao": descricao_servico,
        "municipio": municipio,
        "uf": uf,
        "criado_por_id": criado_por_id,
        "ativo": True,
    }
    res = sb.table("fornecedor_financeiro").insert(payload).execute()
    return res.data[0]


def obter_ou_criar_fornecedor(
    cnpj: str,
    nome: str,
    descricao_servico: Optional[str] = None,
    municipio: Optional[str] = None,
    uf: Optional[str] = None,
    criado_por_id: Optional[int] = None,
) -> dict:
    """
    Se CNPJ já cadastrado → retorna ele.
    Se não → cria automaticamente com a categoria sugerida.
    """
    existe = buscar_fornecedor_por_cnpj(cnpj)
    if existe:
        return existe
    return criar_fornecedor_automatico(
        cnpj=cnpj, nome=nome,
        descricao_servico=descricao_servico,
        municipio=municipio, uf=uf,
        criado_por_id=criado_por_id,
    )


def listar_fornecedores(apenas_ativos: bool = True) -> list[dict]:
    """Lista todos os fornecedores cadastrados."""
    sb = obter_conexao()
    q = sb.table("fornecedor_financeiro").select("*").order("nome")
    if apenas_ativos:
        q = q.eq("ativo", True)
    return q.execute().data


def atualizar_categoria_fornecedor(fornecedor_id: int, nova_categoria: str) -> None:
    """Permite ao usuário alterar a categoria depois (ex: ajustar a sugerida)."""
    sb = obter_conexao()
    sb.table("fornecedor_financeiro").update({"categoria": nova_categoria}).eq("id", fornecedor_id).execute()


# ============================================================
# LANÇAMENTOS DE GASTO
# ============================================================

def gasto_ja_lancado(cnpj_fornecedor: str, numero_nf: Optional[str], valor: float) -> bool:
    """
    Verifica se a mesma NF já foi lançada (anti-duplicação).
    Critério: mesma combinação (CNPJ + nº NF + valor).
    """
    if not numero_nf:
        return False
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .select("id")
           .eq("cnpj_fornecedor", cnpj_fornecedor)
           .eq("numero_nf", numero_nf)
           .eq("valor", valor)
           .limit(1).execute())
    return bool(res.data)


def avaliar_lancamento(
    cnpj_fornecedor: str,
    numero_nf: Optional[str],
    valor: float,
) -> dict:
    """
    Decide o que fazer com um novo lançamento que tem (CNPJ + nº NF):

    Resultados possíveis:
      - {"acao": "criar"}                          → não existe igual, pode criar normal
      - {"acao": "duplicado_exato", "gasto_existente": {...}}  → MESMA NF (bloqueia)
      - {"acao": "atualizar_valor", "gasto_existente": {...}}  → mesmo nº mas valor diferente

    Se não tiver numero_nf, sempre retorna "criar" (não há como detectar duplicação).
    """
    if not numero_nf:
        return {"acao": "criar"}

    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .select("*")
           .eq("cnpj_fornecedor", cnpj_fornecedor)
           .eq("numero_nf", numero_nf)
           .execute())

    if not res.data:
        return {"acao": "criar"}

    # Tem registro com mesmo (CNPJ + numero_nf). Compara o valor.
    for g in res.data:
        valor_existente = float(g.get("valor", 0))
        if abs(valor_existente - float(valor)) < 0.01:
            # Mesma NF + mesmo valor → duplicado exato
            return {"acao": "duplicado_exato", "gasto_existente": g}

    # Tem mesma NF mas com valor diferente → atualiza o primeiro
    return {"acao": "atualizar_valor", "gasto_existente": res.data[0]}


def criar_gasto(
    mes_ano: str,
    fornecedor_id: int,
    cnpj_fornecedor: str,
    nome_fornecedor: str,
    categoria: Optional[str],
    cnpj_pagador: Optional[str],
    empresa_lle: Optional[str],
    numero_nf: Optional[str],
    data_emissao: Optional[date],
    valor: float,
    descricao_servico: Optional[str],
    nome_arquivo_pdf: Optional[str],
    criado_por_id: Optional[int],
    upload_id: Optional[int] = None,
) -> dict:
    """Cria um lançamento de gasto. Não checa duplicidade aqui."""
    sb = obter_conexao()
    payload = {
        "upload_id": upload_id,
        "mes_ano": mes_ano,
        "fornecedor_id": fornecedor_id,
        "cnpj_fornecedor": cnpj_fornecedor,
        "nome_fornecedor": nome_fornecedor,
        "categoria": categoria,
        "cnpj_pagador": cnpj_pagador,
        "empresa_lle": empresa_lle,
        "numero_nf": numero_nf,
        "data_emissao": data_emissao.isoformat() if data_emissao else None,
        "valor": valor,
        "descricao_servico": descricao_servico,
        "nome_arquivo_pdf": nome_arquivo_pdf,
        "criado_por_id": criado_por_id,
    }
    res = sb.table("dados_financeiro_gasto").insert(payload).execute()
    return res.data[0]


def listar_gastos_do_mes(mes_ano: str) -> list[dict]:
    """Lista todos os gastos lançados num determinado mês."""
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .select("*")
           .eq("mes_ano", mes_ano)
           .order("data_emissao", desc=False)
           .execute())
    return res.data


def excluir_gasto(gasto_id: int) -> None:
    """Remove um lançamento de gasto."""
    sb = obter_conexao()
    sb.table("dados_financeiro_gasto").delete().eq("id", gasto_id).execute()


def atualizar_gasto(gasto_id: int, campos: dict) -> None:
    """Atualiza campos arbitrários de um lançamento (categoria, valor, etc)."""
    sb = obter_conexao()
    sb.table("dados_financeiro_gasto").update(campos).eq("id", gasto_id).execute()


# ============================================================
# CONSULTAS PRA DASHBOARD/COMPARATIVOS (Entrega 2)
# ============================================================

def total_gastos_mes(mes_ano: str) -> float:
    """Soma total de gastos do mês."""
    gastos = listar_gastos_do_mes(mes_ano)
    return sum(float(g.get("valor", 0)) for g in gastos)


def total_gastos_ano(ano: int) -> float:
    """Soma total de gastos do ano."""
    sb = obter_conexao()
    res = (sb.table("dados_financeiro_gasto")
           .select("valor")
           .like("mes_ano", f"{ano}-%")
           .execute())
    return sum(float(r.get("valor", 0)) for r in res.data)


def meses_com_gasto() -> list[str]:
    """Retorna meses (YYYY-MM) que têm lançamentos, ordenados desc."""
    sb = obter_conexao()
    res = sb.table("dados_financeiro_gasto").select("mes_ano").execute()
    meses = sorted({r["mes_ano"] for r in res.data if r.get("mes_ano")}, reverse=True)
    return meses
