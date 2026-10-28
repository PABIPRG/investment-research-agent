CREATE TABLE strategy_run_subjects (
 run_id TEXT NOT NULL REFERENCES strategy_runs(id), principal TEXT NOT NULL,
 strategy_id TEXT NOT NULL, PRIMARY KEY(run_id,principal,strategy_id)
);
INSERT OR IGNORE INTO strategy_run_subjects SELECT id,principal,strategy_id FROM strategy_runs WHERE strategy_id!='strategy_pool';
INSERT OR IGNORE INTO strategy_run_subjects SELECT r.id,r.principal,json_extract(a.value,'$.strategy_id') FROM strategy_runs r,json_each(r.result,'$.evolution.per_strategy') a WHERE json_extract(a.value,'$.strategy_id') IS NOT NULL;
INSERT OR IGNORE INTO strategy_run_subjects SELECT r.id,r.principal,json_extract(a.value,'$.sid') FROM strategy_runs r,json_each(r.result,'$.evolution.actions') a WHERE json_extract(a.value,'$.sid') IS NOT NULL;
