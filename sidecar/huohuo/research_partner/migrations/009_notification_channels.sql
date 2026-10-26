-- 新版配置和多渠道投递；不导入 master 通知库或旧凭据。
CREATE TABLE notification_channels (principal TEXT NOT NULL, channel TEXT NOT NULL, config TEXT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(principal,channel));
ALTER TABLE notification_queue RENAME TO notification_queue_v1;
CREATE TABLE notification_queue (decision_id TEXT NOT NULL REFERENCES contact_decisions(decision_id), principal TEXT NOT NULL, mandate_id TEXT NOT NULL, revision INTEGER NOT NULL, generation INTEGER NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL, eligible_at REAL NOT NULL, expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '', permit_id TEXT, updated_at REAL NOT NULL, config_revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(decision_id,channel));
INSERT INTO notification_queue(decision_id,principal,mandate_id,revision,generation,channel,status,eligible_at,expires_at,attempts,detail,permit_id,updated_at) SELECT * FROM notification_queue_v1;
DROP TABLE notification_queue_v1;
ALTER TABLE notification_receipts ADD COLUMN channel TEXT NOT NULL DEFAULT 'app';
