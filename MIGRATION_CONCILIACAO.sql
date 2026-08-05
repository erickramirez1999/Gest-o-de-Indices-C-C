-- ============================================================
-- MIGRATION_CONCILIACAO.sql — módulo de Conciliação (LLE Índices)
-- Cria tabelas, desabilita RLS e recarrega o schema. Seguro repetir.
-- ============================================================
CREATE TABLE IF NOT EXISTS conciliacao (
    id BIGSERIAL PRIMARY KEY,
    data_conciliacao DATE NOT NULL,
    qtd_qrboleto INTEGER, valor_qrboleto NUMERIC,
    qtd_pdv INTEGER, valor_pdv NUMERIC,
    qtd_cobcloud INTEGER, valor_cobcloud NUMERIC,
    qtd_sobra INTEGER, valor_sobra NUMERIC,
    criado_por_id BIGINT REFERENCES usuario(id),
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (data_conciliacao)
);
CREATE TABLE IF NOT EXISTS conciliacao_sobra (
    id BIGSERIAL PRIMARY KEY,
    conciliacao_id BIGINT NOT NULL REFERENCES conciliacao(id) ON DELETE CASCADE,
    data TEXT, historico TEXT, valor NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_conc_data ON conciliacao(data_conciliacao);
CREATE INDEX IF NOT EXISTS idx_conc_sobra_fk ON conciliacao_sobra(conciliacao_id);

ALTER TABLE conciliacao DISABLE ROW LEVEL SECURITY;
ALTER TABLE conciliacao_sobra DISABLE ROW LEVEL SECURITY;
NOTIFY pgrst, 'reload schema';

-- Despesas (saídas do extrato) no Processo 1
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS qtd_despesa INTEGER;
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS valor_despesa NUMERIC;
ALTER TABLE conciliacao_sobra ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'SOBRA';
NOTIFY pgrst, 'reload schema';

-- Aplicações separadas das despesas
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS qtd_aplicacao INTEGER;
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS valor_aplicacao NUMERIC;
NOTIFY pgrst, 'reload schema';

-- Boleto Código de Barras separado do CobCloud
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS qtd_boletocb INTEGER;
ALTER TABLE conciliacao ADD COLUMN IF NOT EXISTS valor_boletocb NUMERIC;
NOTIFY pgrst, 'reload schema';

-- PIX ambíguos (mesmo valor de QR/PIX) — guarda quantos realmente sobram
ALTER TABLE conciliacao_sobra ADD COLUMN IF NOT EXISTS conta INTEGER;
NOTIFY pgrst, 'reload schema';
