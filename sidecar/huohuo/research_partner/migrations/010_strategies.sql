CREATE TABLE strategy_documents (
 principal TEXT NOT NULL, collection TEXT NOT NULL, id TEXT NOT NULL,
 document TEXT NOT NULL, PRIMARY KEY(principal, collection, id)
);
CREATE TABLE strategy_previews (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, action TEXT NOT NULL,
 payload TEXT NOT NULL, state_version TEXT NOT NULL, expires_at REAL NOT NULL,
 status TEXT NOT NULL, result TEXT, UNIQUE(principal, session, request_key)
);
CREATE TABLE strategy_runs (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, strategy_id TEXT NOT NULL,
 request_key TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL,
 updated_at REAL NOT NULL, source_version TEXT NOT NULL, result TEXT, error TEXT
);
CREATE TABLE strategy_run_evidence (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES strategy_runs(id),
 document TEXT NOT NULL
);
