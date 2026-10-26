CREATE TABLE investment_facts (principal TEXT PRIMARY KEY, version INTEGER NOT NULL, document TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE investment_versions (principal TEXT NOT NULL, version INTEGER NOT NULL, document TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(principal,version));
CREATE TABLE investment_previews (principal TEXT NOT NULL, preview_id TEXT NOT NULL, version INTEGER NOT NULL, command TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(principal,preview_id));
CREATE TABLE investment_receipts (principal TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL, PRIMARY KEY(principal,request_key));
CREATE TABLE investment_audit (principal TEXT NOT NULL, version INTEGER NOT NULL, command TEXT NOT NULL, payload TEXT NOT NULL, recorded_at TEXT NOT NULL, PRIMARY KEY(principal,version));
CREATE TABLE investment_outbox (event_id TEXT PRIMARY KEY, principal TEXT NOT NULL, version INTEGER NOT NULL, envelope TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
CREATE TABLE investment_collections (principal TEXT NOT NULL, mandate_id TEXT NOT NULL, collection TEXT NOT NULL, mode TEXT NOT NULL, bound_version INTEGER NOT NULL, members TEXT NOT NULL, PRIMARY KEY(principal,mandate_id));
CREATE TABLE investment_run_facts (principal TEXT NOT NULL, execution_id TEXT PRIMARY KEY, version INTEGER NOT NULL, collection TEXT, mode TEXT, members TEXT NOT NULL);
