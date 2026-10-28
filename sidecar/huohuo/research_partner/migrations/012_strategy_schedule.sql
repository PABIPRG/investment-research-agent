CREATE TABLE strategy_schedules (
 principal TEXT PRIMARY KEY, revision INTEGER NOT NULL, enabled INTEGER NOT NULL,
 policy TEXT NOT NULL, next_at REAL, updated_at REAL NOT NULL
);
CREATE TABLE strategy_background_jobs (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, revision INTEGER NOT NULL,
 day TEXT NOT NULL, strategy_id TEXT NOT NULL, action TEXT NOT NULL,
 status TEXT NOT NULL, run_id TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
 result TEXT, error TEXT,
 UNIQUE(principal,revision,day,strategy_id,action)
);
CREATE INDEX strategy_background_due ON strategy_background_jobs(principal,status,created_at);
CREATE TABLE strategy_events (
 principal TEXT NOT NULL, id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 document TEXT NOT NULL, observed_at REAL NOT NULL, PRIMARY KEY(principal,id)
);
CREATE TABLE strategy_planner_jobs (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, revision INTEGER NOT NULL,
 event_id TEXT NOT NULL, status TEXT NOT NULL, worker_id TEXT, token_hash TEXT,
 lease_until REAL, started_at REAL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
 result TEXT, error TEXT, UNIQUE(principal,revision,event_id)
);
CREATE TABLE strategy_suggestions (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, source_kind TEXT NOT NULL,
 source_id TEXT NOT NULL, fingerprint TEXT NOT NULL, document TEXT NOT NULL,
 status TEXT NOT NULL, created_at REAL NOT NULL, strategy_id TEXT,
 UNIQUE(principal,source_kind,source_id,fingerprint)
);
