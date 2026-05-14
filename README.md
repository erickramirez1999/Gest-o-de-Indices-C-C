# LLE Índices — Gestão de Índices Financeiros

Sistema interno de gestão de indicadores do Setor Financeiro do Grupo LLE.

## Áreas

**Cobrança**
- Índices de Acordo (acordos realizados, cancelamentos, ticket médio)
- Índices de Cobrança (baixas, aging, recebimento por cobrador)
- Performance (tempo de tela, aderência à meta, acordos/dia)
- Geral (histórico mês a mês)

**Crédito**
- Indicadores de Análise (pedidos: direto, liberados, negados)
- Reanálises de Limite (aumento de limite consolidado)
- Geral (histórico mês a mês)

## Stack

Claude → ZIP no GitHub → Streamlit Cloud → Supabase

## Setup

### 1. Supabase
1. Crie um projeto em supabase.com
2. Vá em SQL Editor e execute o conteúdo de `src/banco/schema.py` (variável `SCHEMA_SQL`)

### 2. Secrets
Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` e preencha:
```toml
[supabase]
url = "https://SEU_PROJETO.supabase.co"
key = "SUA_CHAVE_ANON"
```

### 3. Streamlit Cloud
- Repositório: este projeto
- Main file: `app.py`
- Secrets: configure no painel do Streamlit Cloud

## Perfis de Acesso

| Perfil | Cobrança | Crédito | Upload | Admin |
|--------|----------|---------|--------|-------|
| Administrador | ✓ | ✓ | ✓ | ✓ |
| Gestor Cobrança | ✓ | — | ✓ | — |
| Gestor Crédito | — | ✓ | ✓ | — |
| Diretoria | ✓ | ✓ | — | — |

## Upload Mensal

**Cobrança:** 1 arquivo `.xlsx` com as abas:
- `Resumo Acordos`
- `cobrança baixada por cobrador`
- `Relatório de produtividade`

**Crédito:** 2 arquivos:
1. `FIN - Liberações por pedido` (.xlsx ou .xls)
2. `FIN - Aumento de Limite` (.xls)
