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

  -- ---------- guaranteed circles (paid product, Digipay as operator) ----------
  -- A circle is one run of a plan: N members, N months, one pot per month.
  -- Position 1 is always the operator, who takes month 1's pot.
  CREATE TABLE IF NOT EXISTS circles (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('forming', 'active', 'completed', 'expired')),
    size INTEGER NOT NULL,
    months INTEGER NOT NULL,
    share INTEGER NOT NULL,
    chain_secret TEXT NOT NULL,
    anchor TEXT NOT NULL,
    nonce_digest TEXT,
    current_month INTEGER NOT NULL DEFAULT 0,
    closing INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    deadline INTEGER NOT NULL,
    started_at INTEGER
  );
  CREATE INDEX IF NOT EXISTS circles_plan ON circles (plan_id, status);

  CREATE TABLE IF NOT EXISTS circle_members (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles (id),
    position INTEGER NOT NULL,
    phone TEXT,
    is_operator INTEGER NOT NULL DEFAULT 0,
    is_bot INTEGER NOT NULL DEFAULT 0,
    nonce TEXT NOT NULL,
    pay_method TEXT NOT NULL CHECK (pay_method IN ('operator', 'auto', 'manual')),
    mandate_id TEXT,
    -- Gateway reference of the first share, paid to take the seat.
    entry_ref TEXT,
    won_month INTEGER,
    -- The latest draw this member has watched (the reveal plays once).
    seen_month INTEGER NOT NULL DEFAULT 1,
    joined_at INTEGER NOT NULL,
    UNIQUE (circle_id, position)
  );
  CREATE INDEX IF NOT EXISTS circle_members_phone ON circle_members (phone);

  -- "covered" means the operator paid the pot share on the member's behalf
  -- (the guarantee); the member still owes it until settled_at is set.
  CREATE TABLE IF NOT EXISTS contributions (
    circle_id TEXT NOT NULL REFERENCES circles (id),
    member_id TEXT NOT NULL REFERENCES circle_members (id),
    month INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('due', 'paid', 'covered')),
    method TEXT,
    ref TEXT,
    paid_at INTEGER,
    settled_at INTEGER,
    PRIMARY KEY (circle_id, member_id, month)
  );

  -- One row per month. Lottery rows carry everything needed to re-check
  -- the result: the revealed hash-chain link, the seed and the entrants.
  CREATE TABLE IF NOT EXISTS circle_draws (
    circle_id TEXT NOT NULL REFERENCES circles (id),
    month INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('operator', 'lottery', 'last')),
    draw_no INTEGER,
    reveal TEXT,
    seed TEXT,
    eligible TEXT NOT NULL,
    winner_member_id TEXT NOT NULL,
    pot INTEGER NOT NULL,
    payout_ref TEXT,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (circle_id, month)
  );

  -- "entry" pays the first share to join a plan (the seat is taken once it's
  -- paid); "dues" pays a member's outstanding months.
  CREATE TABLE IF NOT EXISTS checkouts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('entry', 'dues')),
    phone TEXT NOT NULL,
    plan_id TEXT NOT NULL,
    nonce TEXT,
    circle_id TEXT REFERENCES circles (id),
    member_id TEXT,
    items TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded')),
    ref TEXT,
    created_at INTEGER NOT NULL
  );
`;

// The circle tables changed shape before release. They only ever held
// simulator data, so an old copy is dropped and rebuilt.
function dropPreReleaseCircleTables(db) {
  const columns = db.prepare("PRAGMA table_info(circle_members)").all();
  if (columns.length === 0 || columns.some((c) => c.name === "seen_month")) return;
  db.exec(`
    DROP TABLE IF EXISTS checkouts;
    DROP TABLE IF EXISTS circle_draws;
    DROP TABLE IF EXISTS contributions;
    DROP TABLE IF EXISTS circle_members;
    DROP TABLE IF EXISTS circles;
  `);
}

export function openDatabase(path) {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;");
  dropPreReleaseCircleTables(db);
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
