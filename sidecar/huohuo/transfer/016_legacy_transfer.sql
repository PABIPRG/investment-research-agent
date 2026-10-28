CREATE TABLE legacy_transfer_uploads (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, filename TEXT NOT NULL,
 payload TEXT NOT NULL, summary TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(principal,session,request_key)
);
CREATE TABLE legacy_transfer_previews (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, upload_id TEXT NOT NULL,
 payload TEXT NOT NULL, base_version TEXT NOT NULL, expires_at REAL NOT NULL,
 status TEXT NOT NULL, receipt TEXT, UNIQUE(principal,session,request_key)
);
CREATE TABLE legacy_transfer_archives (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, batch_id TEXT NOT NULL,
 category TEXT NOT NULL, source_id TEXT NOT NULL, title TEXT NOT NULL,
 document TEXT NOT NULL, source TEXT NOT NULL, imported_at TEXT NOT NULL
);
CREATE INDEX legacy_transfer_archive_owner ON legacy_transfer_archives(principal,category,imported_at);
CREATE TABLE legacy_transfer_audit (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, package_digest TEXT NOT NULL,
 selections TEXT NOT NULL, receipt TEXT NOT NULL, imported_at TEXT NOT NULL
);
