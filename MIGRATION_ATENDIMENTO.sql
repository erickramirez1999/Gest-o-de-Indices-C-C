-- MIGRATION_ATENDIMENTO.sql — módulo Atendimento (Cobrança) no LLE Índices (Supabase)
CREATE TABLE IF NOT EXISTS atendimento (
    id BIGSERIAL PRIMARY KEY,
    data DATE NOT NULL,
    mes_ano TEXT NOT NULL,
    ano INTEGER NOT NULL,
    motivo TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    criado_por_id BIGINT REFERENCES usuario(id),
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_atend_ano ON atendimento(ano);
CREATE INDEX IF NOT EXISTS idx_atend_mes ON atendimento(mes_ano);

ALTER TABLE atendimento DISABLE ROW LEVEL SECURITY;
NOTIFY pgrst, 'reload schema';
