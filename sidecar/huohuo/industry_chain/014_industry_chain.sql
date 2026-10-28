CREATE TABLE industry_chain_state (
  principal TEXT PRIMARY KEY,
  revision INTEGER NOT NULL DEFAULT 0,
  document TEXT NOT NULL
);
CREATE TABLE industry_chain_previews (
  id TEXT PRIMARY KEY,
  principal TEXT NOT NULL,
  session TEXT NOT NULL,
  request_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  action TEXT NOT NULL,
  payload TEXT NOT NULL,
  base_version TEXT NOT NULL,
  expires_at REAL NOT NULL,
  status TEXT NOT NULL,
  result TEXT,
  UNIQUE(principal, session, request_key)
);
