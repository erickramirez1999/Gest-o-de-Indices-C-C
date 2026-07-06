-- ============================================================
-- MIGRATION_INADIMPLENCIA.sql
-- LLE Índices — módulo de Inadimplência (Top por empresa)
--
-- 1 linha por cliente+grupo, por mês. Valor "Em Aberto" + situação
-- (Acordo / Ação Judicial / Terceirizada / Quebra de Acordo /
--  Devolvido pela Terceirizada / Sem Registro) + flags (quebra, protesto).
--
-- Desabilita RLS e recarrega o cache do PostgREST. Seguro rodar de novo.
-- ============================================================

CREATE TABLE IF NOT EXISTS dados_inadimplencia (
    id BIGSERIAL PRIMARY KEY,
    upload_id BIGINT REFERENCES upload_mes(id) ON DELETE CASCADE,
    mes_ano TEXT NOT NULL,
    data_referencia DATE,
    grupo TEXT NOT NULL,               -- 'PISA' | 'KING_TRIO'
    posicao INTEGER,
    cod_cliente TEXT,
    nome_cliente TEXT,
    valor_em_aberto NUMERIC,
    situacao TEXT,
    tem_quebra BOOLEAN DEFAULT FALSE,
    tem_protesto BOOLEAN DEFAULT FALSE,
    terceirizada TEXT,
    acordo_parcelas INTEGER,
    acordo_periodicidade TEXT,
    acordo_valor_parcela NUMERIC,
    acordo_responsavel TEXT,
    acordo_data TEXT
);

CREATE INDEX IF NOT EXISTS idx_inad_mes ON dados_inadimplencia(mes_ano);
CREATE INDEX IF NOT EXISTS idx_inad_grupo ON dados_inadimplencia(grupo);
CREATE INDEX IF NOT EXISTS idx_inad_valor ON dados_inadimplencia(valor_em_aberto);
CREATE INDEX IF NOT EXISTS idx_inad_situacao ON dados_inadimplencia(situacao);

-- Padrão do projeto
ALTER TABLE dados_inadimplencia DISABLE ROW LEVEL SECURITY;

-- Evita PGRST205 no primeiro insert
NOTIFY pgrst, 'reload schema';
