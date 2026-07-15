-- Issued API keys. We store a SHA-256 hash of each key, never the raw
-- value -- the raw key is shown to the caller exactly once, at creation
-- time, the same way GitHub/Stripe-style tokens work.

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    created_at REAL NOT NULL,
    revoked_at REAL
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
