CREATE TABLE personalization_state (
  principal TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  document TEXT NOT NULL
);
CREATE TABLE personalization_previews (
  id TEXT PRIMARY KEY,
  principal TEXT NOT NULL,
  version INTEGER NOT NULL,
  context_version TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE personalization_receipts (
  principal TEXT NOT NULL,
  request_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  result TEXT NOT NULL,
  PRIMARY KEY(principal, request_key)
);
CREATE TABLE personalization_audit (
  principal TEXT NOT NULL,
  version INTEGER NOT NULL,
  action TEXT NOT NULL,
  detail TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  PRIMARY KEY(principal,version)
);
