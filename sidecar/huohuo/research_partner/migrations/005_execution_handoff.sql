-- V1.4：核心与唯一执行台账的持久映射、结果交接及命令回执。
CREATE TABLE IF NOT EXISTS mandate_generation (mandate_id TEXT PRIMARY KEY REFERENCES mandates(mandate_id), generation INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS execution_jobs (execution_id TEXT PRIMARY KEY REFERENCES executions(id), job_id TEXT UNIQUE NOT NULL REFERENCES research_jobs(job_id), mandate_id TEXT NOT NULL, revision INTEGER NOT NULL, generation INTEGER NOT NULL, fact_version TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS result_outbox (attempt_id TEXT PRIMARY KEY REFERENCES attempts(id), result_hash TEXT NOT NULL, result TEXT NOT NULL, received INTEGER NOT NULL DEFAULT 0, receipt TEXT);
CREATE TABLE IF NOT EXISTS mandate_controls (principal TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(principal,key));
