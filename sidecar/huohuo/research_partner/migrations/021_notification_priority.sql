ALTER TABLE notification_queue ADD COLUMN priority INTEGER NOT NULL DEFAULT 50;
ALTER TABLE notification_queue ADD COLUMN priority_version TEXT NOT NULL DEFAULT 'v1';
ALTER TABLE notification_queue ADD COLUMN priority_detail TEXT NOT NULL DEFAULT '{}';
CREATE INDEX notification_queue_priority ON notification_queue(principal,status,priority DESC,eligible_at);
