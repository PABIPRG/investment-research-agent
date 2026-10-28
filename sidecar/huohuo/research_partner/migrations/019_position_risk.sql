CREATE TABLE position_risk_bindings (
 principal TEXT NOT NULL, ticker TEXT NOT NULL, kind TEXT NOT NULL,
 config_key TEXT NOT NULL, mandate_id TEXT NOT NULL,
 basis_cost REAL NOT NULL, resolved_price REAL NOT NULL,
 generation INTEGER NOT NULL, alive INTEGER NOT NULL,
 PRIMARY KEY(principal,ticker,kind)
);
CREATE UNIQUE INDEX position_risk_mandate ON position_risk_bindings(mandate_id);
