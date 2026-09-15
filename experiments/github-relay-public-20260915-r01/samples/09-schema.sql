-- Benign SQL fixture; do not execute against production.
CREATE TABLE relay_probe (
    id INTEGER PRIMARY KEY,
    task_id TEXT NOT NULL,
    route TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

INSERT INTO relay_probe (id, task_id, route, observed_at)
VALUES (1, 'TG-GITHUB-CODE-RELAY-EXPERIMENT-20260915-R01', 'github-public-fixture', '2026-09-15T00:00:00Z');
