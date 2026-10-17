-- 0001 知识库切片：向量维度 1024 -> 512，重建 HNSW，补向量化状态与身份等级
-- 幂等：改列前按 format_type 判断；索引与约束先 DROP IF EXISTS 再建。
-- 回滚：ALTER TABLE knowledge.chunk ALTER COLUMN embedding TYPE vector(1024);（须先清空 chunk 并重建索引）

DO $$
BEGIN
  IF (SELECT format_type(atttypid, atttypmod)
        FROM pg_attribute
       WHERE attrelid = 'knowledge.chunk'::regclass AND attname = 'embedding') <> 'vector(512)' THEN
    DROP INDEX IF EXISTS knowledge_chunk_hnsw_idx;
    ALTER TABLE knowledge.chunk ALTER COLUMN embedding TYPE vector(512);
    RAISE NOTICE 'knowledge.chunk.embedding 已调整为 vector(512)';
  END IF;
END $$;

DROP INDEX IF EXISTS knowledge_chunk_hnsw_idx;
CREATE INDEX IF NOT EXISTS knowledge_chunk_hnsw_idx
  ON knowledge.chunk USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

ALTER TABLE knowledge.chunk ADD COLUMN IF NOT EXISTS embedding_status text NOT NULL DEFAULT 'PENDING';
ALTER TABLE knowledge.chunk ADD COLUMN IF NOT EXISTS identity_level    text NOT NULL DEFAULT 'public';

ALTER TABLE knowledge.chunk DROP CONSTRAINT IF EXISTS knowledge_chunk_embedding_status_ck;
ALTER TABLE knowledge.chunk ADD  CONSTRAINT knowledge_chunk_embedding_status_ck
  CHECK (embedding_status IN ('PENDING','READY','FAILED'));

ALTER TABLE knowledge.chunk DROP CONSTRAINT IF EXISTS knowledge_chunk_identity_ck;
ALTER TABLE knowledge.chunk ADD  CONSTRAINT knowledge_chunk_identity_ck
  CHECK (identity_level IN ('public','customer','agent'));

CREATE INDEX IF NOT EXISTS knowledge_chunk_embedding_status_idx
  ON knowledge.chunk (embedding_status, id);

COMMENT ON TABLE knowledge.chunk IS '切片 + 向量(512维, BAAI/bge-small-zh-v1.5) + 全文检索；二期启用';
