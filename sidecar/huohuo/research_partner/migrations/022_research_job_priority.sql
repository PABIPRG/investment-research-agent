ALTER TABLE research_jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 50;
ALTER TABLE research_jobs ADD COLUMN priority_version TEXT NOT NULL DEFAULT 'v1';
CREATE INDEX ix_research_jobs_priority ON research_jobs(status,priority DESC,next_run_at);
