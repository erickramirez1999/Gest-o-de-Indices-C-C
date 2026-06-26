"""
Schema SQL para executar no Supabase (Dashboard > SQL Editor).

Tabelas:
  - usuario
  - upload_mes (registro de cada upload mensal)
  - dados_cobranca_acordo
  - dados_cobranca_baixa
  - dados_cobranca_performance
  - dados_cobranca_ocorrencia
  - dados_credito_liberacoes
  - dados_credito_limite
"""

SCHEMA_SQL = """
-- USUÁRIOS
CREATE TABLE IF NOT EXISTS usuario (
    id BIGSERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK(perfil IN ('ADMIN', 'GESTOR_COBRANCA', 'GESTOR_CREDITO', 'GESTOR_FINANCEIRO', 'DIRETORIA')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    deve_trocar_senha BOOLEAN NOT NULL DEFAULT FALSE,
    chave_aprovacao TEXT,
    aprovado BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ultimo_login TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_usuario_email ON usuario(email);

-- UPLOAD MENSAL (controle de uploads)
CREATE TABLE IF NOT EXISTS upload_mes (
    id BIGSERIAL PRIMARY KEY,
    area TEXT NOT NULL CHECK(area IN ('COBRANCA', 'CREDITO')),
    mes_ano TEXT NOT NULL,           -- formato 'YYYY-MM', ex: '2026-04'
    nome_arquivo TEXT NOT NULL,
    enviado_por_id BIGINT REFERENCES usuario(id),
    enviado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'OK',
    UNIQUE(area, mes_ano)
);

CREATE INDEX IF NOT EXISTS idx_upload_mes_area ON upload_mes(area, mes_ano);

-- COBRANÇA: ACORDOS (origem: aba "Acordos realizados detalhados")
CREATE TABLE IF NOT EXISTS dados_cobranca_acordo (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    negociador TEXT,
    devedor TEXT,
    data_acordo DATE,
    forma_pagto TEXT,
    qtd_parcelas INTEGER,
    qtd_parcelas_quitadas INTEGER,
    valor_parcela NUMERIC,
    valor_total NUMERIC,
    valor_pago NUMERIC,
    valor_atualizado NUMERIC,
    status TEXT,
    cancelado BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_acord_mes ON dados_cobranca_acordo(mes_ano);
CREATE INDEX IF NOT EXISTS idx_acord_negociador ON dados_cobranca_acordo(negociador);

-- COBRANÇA: OCORRÊNCIAS (origem: arquivo "ocorrencias_ACORDO_*.xlsx")
-- Fonte das QUEBRAS de acordo (STATUS "98 - QUEBRA DE ACORDO").
CREATE TABLE IF NOT EXISTS dados_cobranca_ocorrencia (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    negociador TEXT,
    processo TEXT,
    devedor TEXT,
    cnpj TEXT,
    cidade TEXT,
    uf TEXT,
    data_ocorrencia DATE,
    status TEXT,
    eh_quebra BOOLEAN DEFAULT FALSE,
    eh_acordo BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_ocor_mes ON dados_cobranca_ocorrencia(mes_ano);
CREATE INDEX IF NOT EXISTS idx_ocor_negociador ON dados_cobranca_ocorrencia(negociador);
CREATE INDEX IF NOT EXISTS idx_ocor_quebra ON dados_cobranca_ocorrencia(eh_quebra);

-- COBRANÇA: BAIXAS (origem: aba "cobrança baixada por cobrador")
CREATE TABLE IF NOT EXISTS dados_cobranca_baixa (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    cobrador TEXT,
    dias_atraso INTEGER,
    vlr_desdobrado NUMERIC,
    vlr_liquido NUMERIC,
    juros_multa NUMERIC,
    faixa_aging TEXT
);

CREATE INDEX IF NOT EXISTS idx_baixa_mes ON dados_cobranca_baixa(mes_ano);
CREATE INDEX IF NOT EXISTS idx_baixa_cobrador ON dados_cobranca_baixa(cobrador);

-- COBRANÇA: PERFORMANCE (origem: aba "Relatório de produtividade")
CREATE TABLE IF NOT EXISTS dados_cobranca_performance (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    cobrador TEXT NOT NULL,
    tempo_medio_diario_h NUMERIC,
    meta_diaria_h NUMERIC,
    pct_aderencia NUMERIC,
    ocorrencias_media_dia NUMERIC,
    acordos_media_dia NUMERIC,
    valor_medio_diario NUMERIC,
    total_acordos_valor NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_perf_mes ON dados_cobranca_performance(mes_ano);

-- CRÉDITO: LIBERAÇÕES (origem: FIN_liberacoes)
CREATE TABLE IF NOT EXISTS dados_credito_liberacao (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    vlr_pedido NUMERIC,
    cod_empresa INTEGER,
    tipo TEXT NOT NULL CHECK(tipo IN ('DIRETO', 'LIBERADO', 'NEGADO')),
    analista TEXT
);

CREATE INDEX IF NOT EXISTS idx_lib_mes ON dados_credito_liberacao(mes_ano);
CREATE INDEX IF NOT EXISTS idx_lib_tipo ON dados_credito_liberacao(tipo);
CREATE INDEX IF NOT EXISTS idx_lib_analista ON dados_credito_liberacao(analista);

-- CRÉDITO: AUMENTO DE LIMITE (origem: FIN_aumento_limite)
CREATE TABLE IF NOT EXISTS dados_credito_limite (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    cod_parceiro BIGINT,
    nome TEXT,
    data_inclusao DATE,
    limite_anterior NUMERIC,
    novo_limite NUMERIC,
    variacao NUMERIC,
    data_revisao DATE,
    analista TEXT
);

CREATE INDEX IF NOT EXISTS idx_limite_mes ON dados_credito_limite(mes_ano);
CREATE INDEX IF NOT EXISTS idx_limite_analista ON dados_credito_limite(analista);

-- CRÉDITO: TEMPO DE TELA (origem: FIN_tempo_liberacao)
CREATE TABLE IF NOT EXISTS dados_credito_tempo_tela (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT NOT NULL REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    analista TEXT NOT NULL,
    qtd_pedidos INTEGER,
    tempo_total_min NUMERIC,
    tempo_medio_min NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_tempo_tela_mes ON dados_credito_tempo_tela(mes_ano);
CREATE INDEX IF NOT EXISTS idx_tempo_tela_analista ON dados_credito_tempo_tela(analista);

-- AUDITORIA
CREATE TABLE IF NOT EXISTS auditoria (
    id BIGSERIAL PRIMARY KEY,
    usuario_id BIGINT REFERENCES usuario(id),
    usuario_nome TEXT NOT NULL,
    acao TEXT NOT NULL,
    area TEXT,
    detalhe TEXT,
    ip TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON auditoria(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_acao ON auditoria(acao);

-- ============================================================
-- FINANCEIRO — Controle de Custos Orçamentários
-- ============================================================

-- Atualiza enum de áreas (Postgres não permite ALTER em CHECK, mas a regra
-- aqui é só guia — a app valida no INSERT). Se a tabela upload_mes já existe,
-- precisa rodar manualmente:
--   ALTER TABLE upload_mes DROP CONSTRAINT upload_mes_area_check;
--   ALTER TABLE upload_mes ADD CONSTRAINT upload_mes_area_check
--     CHECK(area IN ('COBRANCA', 'CREDITO', 'FINANCEIRO'));

-- FORNECEDORES (cadastrados automaticamente ao ler 1ª NF do CNPJ)
CREATE TABLE IF NOT EXISTS fornecedor_financeiro (
    id BIGSERIAL PRIMARY KEY,
    cnpj TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    categoria TEXT,                  -- ex: SOFTWARE, PROTESTO, CONTABIL
    area_negocio TEXT,               -- macro: COBRANÇA, NEGATIVAÇÃO, CRÉDITO, INFRAESTRUTURA
    subcategoria TEXT,               -- ex: Terceirizada de Cobrança, Software de Cobrança
    descricao_servico_padrao TEXT,   -- preenchida da 1ª NF como sugestão
    municipio TEXT,
    uf TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    criado_por_id BIGINT REFERENCES usuario(id),
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_forn_cnpj ON fornecedor_financeiro(cnpj);
CREATE INDEX IF NOT EXISTS idx_forn_categoria ON fornecedor_financeiro(categoria);
CREATE INDEX IF NOT EXISTS idx_forn_area ON fornecedor_financeiro(area_negocio);

-- LANÇAMENTO DE GASTO (1 linha por NF processada)
CREATE TABLE IF NOT EXISTS dados_financeiro_gasto (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT REFERENCES upload_mes(id) ON DELETE SET NULL,
    mes_ano TEXT NOT NULL,                                -- 'YYYY-MM' competência
    fornecedor_id BIGINT NOT NULL REFERENCES fornecedor_financeiro(id),
    cnpj_fornecedor TEXT NOT NULL,                        -- redundante p/ histórico
    nome_fornecedor TEXT NOT NULL,                        -- snapshot
    categoria TEXT,                                       -- snapshot da categoria
    area_negocio TEXT,                                    -- snapshot macro área
    subcategoria TEXT,                                    -- snapshot subcategoria
    cnpj_pagador TEXT,                                    -- CNPJ tomador (qual LLE)
    empresa_lle TEXT,                                     -- PISA / KING / TRIO / OUTRO
    numero_nf TEXT,                                       -- identificador NF
    data_emissao DATE,
    valor NUMERIC NOT NULL,
    descricao_servico TEXT,
    nome_arquivo_pdf TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    criado_por_id BIGINT REFERENCES usuario(id),
    UNIQUE(cnpj_fornecedor, numero_nf, valor)             -- evita duplicar a mesma NF
);

CREATE INDEX IF NOT EXISTS idx_fin_gasto_mes ON dados_financeiro_gasto(mes_ano);
CREATE INDEX IF NOT EXISTS idx_fin_gasto_forn ON dados_financeiro_gasto(fornecedor_id);
CREATE INDEX IF NOT EXISTS idx_fin_gasto_cat ON dados_financeiro_gasto(categoria);
CREATE INDEX IF NOT EXISTS idx_fin_gasto_emp ON dados_financeiro_gasto(empresa_lle);
CREATE INDEX IF NOT EXISTS idx_fin_gasto_area ON dados_financeiro_gasto(area_negocio);
"""
