-- 旧候选计划与任务保留只读历史；新调度只写核心委托与统一执行台账。
ALTER TABLE strategy_schedules RENAME TO legacy_strategy_schedules;
ALTER TABLE strategy_background_jobs RENAME TO legacy_strategy_background_jobs;
ALTER TABLE strategy_planner_jobs RENAME TO legacy_strategy_planner_jobs;
CREATE TABLE mandate_workflows (
 principal TEXT NOT NULL, kind TEXT NOT NULL,
 mandate_id TEXT NOT NULL UNIQUE REFERENCES mandates(mandate_id),
 PRIMARY KEY(principal,kind)
);
ALTER TABLE strategy_runs ADD COLUMN execution_id TEXT REFERENCES executions(id);
CREATE UNIQUE INDEX strategy_run_execution ON strategy_runs(execution_id) WHERE execution_id IS NOT NULL;
