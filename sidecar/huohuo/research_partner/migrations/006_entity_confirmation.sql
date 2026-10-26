CREATE TABLE entity_snapshots (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 version TEXT NOT NULL, payload TEXT NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE entity_confirmations (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 snapshot_id TEXT NOT NULL REFERENCES entity_snapshots(id), mention_id TEXT NOT NULL,
 entity_id TEXT NOT NULL, payload TEXT NOT NULL, source_call TEXT NOT NULL,
 expires_at REAL NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX entity_confirmation_context ON entity_confirmations(principal,session,active);
CREATE TABLE entity_mandate_receipts (
 principal TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
 mandate_id TEXT NOT NULL, PRIMARY KEY(principal,request_key)
);
