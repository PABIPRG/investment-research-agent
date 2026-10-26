CREATE TABLE research_tool_calls (
 id TEXT PRIMARY KEY, principal TEXT NOT NULL, session TEXT NOT NULL,
 call_id TEXT NOT NULL, tool_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 request TEXT NOT NULL, result TEXT, created_at REAL NOT NULL,
 UNIQUE(principal, session, call_id, tool_id)
);
CREATE INDEX research_tool_session ON research_tool_calls(principal,session,created_at);
