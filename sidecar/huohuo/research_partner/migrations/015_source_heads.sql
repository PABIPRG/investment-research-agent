CREATE TABLE source_versions_next (
    event_id TEXT PRIMARY KEY,
    principal TEXT NOT NULL,
    subject TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    source TEXT NOT NULL,
    version TEXT NOT NULL,
    document TEXT NOT NULL,
    observed_at TEXT NOT NULL
);
INSERT INTO source_versions_next SELECT event_id,principal,subject,scope_key,source,version,document,observed_at FROM source_versions;
DROP TABLE source_versions;
ALTER TABLE source_versions_next RENAME TO source_versions;
CREATE INDEX source_versions_lookup ON source_versions(principal,scope_key,source,observed_at);
CREATE TABLE source_heads (
    principal TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    source TEXT NOT NULL,
    event_id TEXT NOT NULL REFERENCES source_versions(event_id),
    content_version TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(principal,scope_key,source)
);
INSERT INTO source_heads(principal,scope_key,source,event_id,content_version,updated_at)
SELECT principal,scope_key,source,event_id,version,observed_at FROM (
    SELECT *,ROW_NUMBER() OVER (PARTITION BY principal,scope_key,source ORDER BY observed_at DESC,event_id DESC) AS newest
    FROM source_versions
) WHERE newest=1;
