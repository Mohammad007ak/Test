// The database, behind one small async interface so the same code runs on
// SQLite (local development, tests, a single server with a disk) and on
// PostgreSQL (hosting where the app's own disk doesn't survive a deploy).
//
//   db.get(sql, ...params)     first row or undefined
//   db.all(sql, ...params)     all rows
//   db.run(sql, ...params)     { changes }
//   db.transaction(async (tx) => { ... })   tx has get/all/run
//
// SQL is written once with "?" placeholders; the Postgres side numbers them.
// Inside a transaction use only `tx`, and await nothing but its queries.
import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS otp_codes (
    phone TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL,
    expires_at BIGINT NOT NULL,
    attempts BIGINT NOT NULL DEFAULT 0,
    window_start BIGINT NOT NULL,
    sent_in_window BIGINT NOT NULL DEFAULT 0
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    expires_at BIGINT NOT NULL
  );

  -- A fund's whole ledger is one JSON document, edited only by its manager.
  -- "version" guards against two tabs overwriting each other.
  CREATE TABLE IF NOT EXISTS funds (
    id TEXT PRIMARY KEY,
    owner_phone TEXT NOT NULL,
    data TEXT NOT NULL,
    version BIGINT NOT NULL DEFAULT 1,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
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
    created_at BIGINT NOT NULL,
    resolved_at BIGINT
  );
  CREATE INDEX IF NOT EXISTS draws_fund ON draws (fund_id, created_at);

  -- ---------- guaranteed circles (paid product, Digipay as operator) ----------
  -- A circle is one run of a plan: N members, N months, one pot per month.
  -- Position 1 is always the operator, who takes month 1's pot.
  CREATE TABLE IF NOT EXISTS circles (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('forming', 'active', 'completed', 'expired')),
    size BIGINT NOT NULL,
    months BIGINT NOT NULL,
    share BIGINT NOT NULL,
    chain_secret TEXT NOT NULL,
    anchor TEXT NOT NULL,
    nonce_digest TEXT,
    current_month BIGINT NOT NULL DEFAULT 0,
    closing BIGINT NOT NULL DEFAULT 0,
    created_at BIGINT NOT NULL,
    deadline BIGINT NOT NULL,
    started_at BIGINT
  );
  CREATE INDEX IF NOT EXISTS circles_plan ON circles (plan_id, status);

  CREATE TABLE IF NOT EXISTS circle_members (
    id TEXT PRIMARY KEY,
    circle_id TEXT NOT NULL REFERENCES circles (id),
    position BIGINT NOT NULL,
    phone TEXT,
    is_operator BIGINT NOT NULL DEFAULT 0,
    is_bot BIGINT NOT NULL DEFAULT 0,
    nonce TEXT NOT NULL,
    pay_method TEXT NOT NULL CHECK (pay_method IN ('operator', 'auto', 'manual')),
    mandate_id TEXT,
    -- Gateway reference of the first share, paid to take the seat.
    entry_ref TEXT,
    won_month BIGINT,
    -- The latest draw this member has watched (the reveal plays once).
    seen_month BIGINT NOT NULL DEFAULT 1,
    joined_at BIGINT NOT NULL,
    UNIQUE (circle_id, position)
  );
  CREATE INDEX IF NOT EXISTS circle_members_phone ON circle_members (phone);

  -- "covered" means the operator paid the pot share on the member's behalf
  -- (the guarantee); the member still owes it until settled_at is set.
  CREATE TABLE IF NOT EXISTS contributions (
    circle_id TEXT NOT NULL REFERENCES circles (id),
    member_id TEXT NOT NULL REFERENCES circle_members (id),
    month BIGINT NOT NULL,
    amount BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('due', 'paid', 'covered')),
    method TEXT,
    ref TEXT,
    paid_at BIGINT,
    settled_at BIGINT,
    PRIMARY KEY (circle_id, member_id, month)
  );

  -- One row per month. Lottery rows carry everything needed to re-check
  -- the result: the revealed hash-chain link, the seed and the entrants.
  CREATE TABLE IF NOT EXISTS circle_draws (
    circle_id TEXT NOT NULL REFERENCES circles (id),
    month BIGINT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('operator', 'lottery', 'last')),
    draw_no BIGINT,
    reveal TEXT,
    seed TEXT,
    eligible TEXT NOT NULL,
    winner_member_id TEXT NOT NULL,
    pot BIGINT NOT NULL,
    payout_ref TEXT,
    created_at BIGINT NOT NULL,
    PRIMARY KEY (circle_id, month)
  );

  -- A month's pot nobody could take: everyone still waiting owes the
  -- guarantee. Digipay holds it until one of them settles (debt plus the
  -- late fee) and claims it; unclaimed past the grace period, Digipay keeps it.
  CREATE TABLE IF NOT EXISTS held_pots (
    circle_id TEXT NOT NULL REFERENCES circles (id),
    month BIGINT NOT NULL,
    pot BIGINT NOT NULL,
    held_at BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('held', 'claimed', 'forfeited')),
    member_id TEXT,
    resolved_at BIGINT,
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
    amount BIGINT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'cancelled', 'refunded')),
    ref TEXT,
    created_at BIGINT NOT NULL
  );

  -- Every money movement and lifecycle step in the guaranteed plans, for the
  -- operator's reports and audit trail. Append-only.
  CREATE TABLE IF NOT EXISTS ops_events (
    id TEXT PRIMARY KEY,
    at BIGINT NOT NULL,
    kind TEXT NOT NULL,
    circle_id TEXT,
    member_id TEXT,
    phone TEXT,
    amount BIGINT,
    detail TEXT
  );
  CREATE INDEX IF NOT EXISTS ops_events_at ON ops_events (at);

  -- Members who have been shown the first-visit tour, so every new
  -- account gets it once right after signing in, on whatever device.
  CREATE TABLE IF NOT EXISTS tour_seen (
    phone TEXT PRIMARY KEY,
    seen_at BIGINT NOT NULL
  );

  -- Admin panel sign-ins (username/password), apart from members' sessions.
  CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    expires_at BIGINT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS ops_events_circle ON ops_events (circle_id, at);
`;

// The circle tables changed shape before release. They only ever held
// simulator data, so an old SQLite copy is dropped and rebuilt.
function dropPreReleaseCircleTables(sqlite) {
  const columns = sqlite.prepare("PRAGMA table_info(circle_members)").all();
  if (columns.length === 0 || columns.some((c) => c.name === "seen_month")) return;
  sqlite.exec(`
    DROP TABLE IF EXISTS checkouts;
    DROP TABLE IF EXISTS circle_draws;
    DROP TABLE IF EXISTS contributions;
    DROP TABLE IF EXISTS circle_members;
    DROP TABLE IF EXISTS circles;
  `);
}

function openSqlite(path) {
  if (path !== ":memory:") mkdirSync(dirname(path), { recursive: true });
  const sqlite = new DatabaseSync(path);
  sqlite.exec("PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;");
  dropPreReleaseCircleTables(sqlite);
  sqlite.exec(SCHEMA);

  const handle = {
    kind: "sqlite",
    get: async (sql, ...params) => sqlite.prepare(sql).get(...params),
    all: async (sql, ...params) => sqlite.prepare(sql).all(...params),
    run: async (sql, ...params) => ({ changes: Number(sqlite.prepare(sql).run(...params).changes) }),
  };
  // One connection: transactions take turns.
  let queue = Promise.resolve();
  return {
    ...handle,
    transaction(fn) {
      const next = queue.then(async () => {
        sqlite.exec("BEGIN");
        try {
          const result = await fn(handle);
          sqlite.exec("COMMIT");
          return result;
        } catch (error) {
          sqlite.exec("ROLLBACK");
          throw error;
        }
      });
      queue = next.catch(() => {});
      return next;
    },
    close: async () => sqlite.close(),
  };
}

// ---------- PostgreSQL ----------

const numbered = (sql) => {
  let n = 0;
  return sql.replace(/\?/g, () => `$${++n}`);
};

async function openPostgres(url, { schema } = {}) {
  const { default: pg } = await import("pg");
  // COUNT/SUM and BIGINT columns come back as strings by default; every
  // number here (money in toman, timestamps in ms) fits in a JS number.
  pg.types.setTypeParser(20, (v) => (v === null ? null : Number(v)));
  pg.types.setTypeParser(1700, (v) => (v === null ? null : Number(v)));

  const pool = new pg.Pool({
    connectionString: url,
    max: 10,
    ...(schema ? { options: `-c search_path=${schema}` } : {}),
  });
  // The database may still be starting when the app does (a fresh deploy,
  // a restarted service): keep trying for about a minute before giving up.
  for (let attempt = 1; ; attempt++) {
    try {
      if (schema) await pool.query(`CREATE SCHEMA IF NOT EXISTS ${schema}`);
      await pool.query(SCHEMA);
      break;
    } catch (error) {
      if (attempt >= 12) throw new Error(`Can't reach PostgreSQL: ${error.message}`);
      console.warn(`PostgreSQL not ready (${error.message}); retrying in 5s (${attempt}/12)`);
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }
  }

  const over = (client) => ({
    kind: "postgres",
    get: async (sql, ...params) => (await client.query(numbered(sql), params)).rows[0],
    all: async (sql, ...params) => (await client.query(numbered(sql), params)).rows,
    run: async (sql, ...params) => ({ changes: (await client.query(numbered(sql), params)).rowCount }),
  });
  return {
    ...over(pool),
    async transaction(fn) {
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        const result = await fn(over(client));
        await client.query("COMMIT");
        return result;
      } catch (error) {
        await client.query("ROLLBACK").catch(() => {});
        throw error;
      } finally {
        client.release();
      }
    },
    close: () => pool.end(),
  };
}

// A postgres:// URL opens PostgreSQL; anything else is a SQLite file path
// (or ":memory:").
export function openDatabase(target, options) {
  return /^postgres(ql)?:\/\//.test(target) ? openPostgres(target, options) : Promise.resolve(openSqlite(target));
}
