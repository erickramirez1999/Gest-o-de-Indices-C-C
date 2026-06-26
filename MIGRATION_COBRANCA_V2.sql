-- ============================================================
-- MIGRATION_COBRANCA_V2.sql
-- LLE Índices — Upload mensal de Cobrança (novo formato de arquivos)
--
-- O que faz:
--   1) Adiciona colunas em dados_cobranca_acordo:
--        qtd_parcelas_quitadas, valor_pago, valor_atualizado
--   2) Cria a tabela dados_cobranca_ocorrencia (fonte das QUEBRAS)
--
-- Seguro de rodar mais de uma vez (IF NOT EXISTS em tudo).
-- ============================================================

-- 1) Novas colunas em ACORDOS
ALTER TABLE dados_cobranca_acordo
    ADD COLUMN IF NOT EXISTS qtd_parcelas_quitadas INTEGER;
ALTER TABLE dados_cobranca_acordo
    ADD COLUMN IF NOT EXISTS valor_pago NUMERIC;
ALTER TABLE dados_cobranca_acordo
    ADD COLUMN IF NOT EXISTS valor_atualizado NUMERIC;

-- 2) Tabela de OCORRÊNCIAS (acordos e quebras de acordo)
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

-- Padrão do projeto: RLS desabilitado
ALTER TABLE dados_cobranca_ocorrencia DISABLE ROW LEVEL SECURITY;
