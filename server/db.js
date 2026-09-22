import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS otp_codes (
    phone TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    window_start INTEGER NOT NULL,
    sent_in_window INTEGER NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    expires_at INTEGER NOT NULL
  );

  -- A fund's whole ledger is one JSON document, edited only by its manager.
  -- "version" guards against two tabs overwriting each other.
  CREATE TABLE IF NOT EXISTS funds (
    id TEXT PRIMARY KEY,
    owner_phone TEXT NOT NULL,
    data TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS funds_owner ON funds (owner_phone);

  -- Derived from funds.data on every save, so members can find their funds.
  CREATE TABLE IF NOT EXISTS fund_members (
    fund_id TEXT NOT NULL REFERENCES funds (id) ON DELETE CASCADE,
    member_id TEXT NOT NULL,
    phone TEXT NOT NULL,
    PRIMARY KEY (fund_id, member_id)
  );
  CREATE INDEX IF NOT EXISTS fund_members_phone ON fund_members (phone);

  -- Every draw is kept, including cancelled ones, so members can see
  -- whether the manager re-rolled a result they didn't like.
  CREATE TABLE IF NOT EXISTS draws (
    id TEXT PRIMARY KEY,
    fund_id TEXT NOT NULL REFERENCES funds (id) ON DELETE CASCADE,
    month TEXT NOT NULL,
    winner_member_id TEXT NOT NULL,
    winner_name TEXT NOT NULL,
    entries TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at INTEGER NOT NULL,
    resolved_at INTEGER
  );
  CREATE INDEX IF NOT EXISTS draws_fund ON draws (fund_id, created_at);
`;

export function openDatabase(path) {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;");
  db.exec(SCHEMA);
  return db;
}

export function transaction(db, fn) {
  db.exec("BEGIN");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}
