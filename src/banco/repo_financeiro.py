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
# ÁREAS DE NEGÓCIO E SUBCATEGORIAS (taxonomia LLE)
# ============================================================

AREAS_NEGOCIO = {
    "COBRANÇA": {
        "cor": "#D32F2F",  # vermelho
        "emoji": "📞",
        "subcategorias": [
            "Terceirizada de Cobrança",
            "Software de Cobrança",
        ],
    },
    "NEGATIVAÇÃO": {
        "cor": "#F57C00",  # laranja
        "emoji": "⚠️",
        "subcategorias": [
            "Serasa / Negativação",
            "Cartório / IEPTB",
        ],
    },
    "CRÉDITO": {
        "cor": "#388E3C",  # verde
        "emoji": "💳",
        "subcategorias": [
            "Software de Crédito e Cadastro",
            "Análise de Crédito",
        ],
    },
    "INFRAESTRUTURA": {
        "cor": "#1976D2",  # azul
        "emoji": "🛠️",
        "subcategorias": [
            "Telefonia / Software de Ligação",
            "Licença TEF / Meios de Pagamento",
            "Hospedagem / Cloud",
            "Software Geral",
        ],
    },
    "ADMINISTRATIVO": {
        "cor": "#7B1FA2",  # roxo
        "emoji": "📋",
        "subcategorias": [
            "Contábil",
            "Jurídico",
            "Consultoria",
            "Aluguel / Condomínio",
            "Energia / Água",
            "Material de Escritório",
            "Outros",
        ],
    },
    "OUTROS": {
        "cor": "#616161",  # cinza
        "emoji": "❓",
        "subcategorias": ["Não classificado"],
    },
}


def listar_areas_negocio() -> list:
    return list(AREAS_NEGOCIO.keys())


def listar_subcategorias(area: str) -> list:
    return AREAS_NEGOCIO.get(area, {}).get("subcategorias", [])


def cor_da_area(area: Optional[str]) -> str:
    if not area or area not in AREAS_NEGOCIO:
        return "#616161"
    return AREAS_NEGOCIO[area]["cor"]


def emoji_da_area(area: Optional[str]) -> str:
    if not area or area not in AREAS_NEGOCIO:
        return "❓"
    return AREAS_NEGOCIO[area]["emoji"]


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


def sugerir_area_e_subcategoria(nome_fornecedor: Optional[str], descricao: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Sugere área + subcategoria com base em palavras-chave conhecidas."""
    base = " ".join(filter(None, [nome_fornecedor, descricao])).upper()
    if not base.strip():
        return None, None

    # Terceirizadas de Cobrança (lista de empresas conhecidas)
    if any(p in base for p in ["RENNOVARE", "KNOWHOW", "KNOW HOW", "SOLUTE"]):
        return "COBRANÇA", "Terceirizada de Cobrança"

    # Software de Cobrança
    if "CUBO" in base:
        return "COBRANÇA", "Software de Cobrança"

    # Serasa/ClearSale
    if any(p in base for p in ["SERASA", "CLEARSALE", "CLEAR SALE"]):
        return "NEGATIVAÇÃO", "Serasa / Negativação"

    # IEPTB / Instituto de Protesto
    if "INSTITUTO" in base and "PROTESTO" in base:
        return "NEGATIVAÇÃO", "Cartório / IEPTB"
    if "IEPTB" in base:
        return "NEGATIVAÇÃO", "Cartório / IEPTB"

    # CadoPay / CADO
    if "CADO" in base:
        return "CRÉDITO", "Software de Crédito e Cadastro"

    # Nines (software de ligação)
    if "NINES" in base:
        return "INFRAESTRUTURA", "Telefonia / Software de Ligação"

    # PayGo (TEF)
    if "PAYGO" in base or "PAY GO" in base:
        return "INFRAESTRUTURA", "Licença TEF / Meios de Pagamento"

    # Heurísticas genéricas pela descrição
    if any(p in base for p in ["PROTESTO", "NEGATIV"]):
        return "NEGATIVAÇÃO", "Cartório / IEPTB"
    if any(p in base for p in ["COBRANÇA", "COBRANCA", "RECUPERAÇÃO DE CRÉDITO", "RECUPERACAO DE CREDITO"]):
        return "COBRANÇA", "Terceirizada de Cobrança"
    if any(p in base for p in ["HOSPEDAGEM", "CLOUD"]):
        return "INFRAESTRUTURA", "Hospedagem / Cloud"
    if any(p in base for p in ["TELEFON", "INTERNET", "TELECOM"]):
        return "INFRAESTRUTURA", "Telefonia / Software de Ligação"
    if any(p in base for p in ["SOFTWARE", "SISTEMA", "TECNOLOGIA", "LICENCIAMENTO"]):
        return "INFRAESTRUTURA", "Software Geral"
    if any(p in base for p in ["CONTÁBIL", "CONTABIL"]):
        return "ADMINISTRATIVO", "Contábil"
    if any(p in base for p in ["JURÍDICO", "JURIDICO", "ADVOG"]):
        return "ADMINISTRATIVO", "Jurídico"
    if "CONSULTORIA" in base or "ASSESSORIA" in base:
        return "ADMINISTRATIVO", "Consultoria"
    if any(p in base for p in ["ALUGUEL", "LOCAÇÃO", "LOCACAO"]):
        return "ADMINISTRATIVO", "Aluguel / Condomínio"
    if any(p in base for p in ["ENERGIA", "LIGHT", "ENEL"]):
        return "ADMINISTRATIVO", "Energia / Água"

    return None, None


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
    area_negocio: Optional[str] = None,
    subcategoria: Optional[str] = None,
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
        "area_negocio": area_negocio,
        "subcategoria": subcategoria,
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


# ============================================================
# CLASSIFICAÇÃO POR ÁREA/SUBCATEGORIA
# ============================================================

def atualizar_area_fornecedor(
    fornecedor_id: int,
    area: Optional[str],
    subcategoria: Optional[str],
    propagar: bool = True,
) -> int:
    """
    Atualiza a área/subcategoria do fornecedor.
    Se propagar=True, também atualiza nos lançamentos existentes.
    Retorna o nº de lançamentos atualizados.
    """
    sb = obter_conexao()
    sb.table("fornecedor_financeiro").update({
        "area_negocio": area,
        "subcategoria": subcategoria,
    }).eq("id", fornecedor_id).execute()

    if propagar:
        res = (sb.table("dados_financeiro_gasto")
               .update({"area_negocio": area, "subcategoria": subcategoria})
               .eq("fornecedor_id", fornecedor_id)
               .execute())
        return len(res.data) if res.data else 0
    return 0


def fornecedor_com_classificacao(cnpj: str) -> Optional[dict]:
    """Igual a buscar_fornecedor_por_cnpj, mas explicita propósito."""
    return buscar_fornecedor_por_cnpj(cnpj)
