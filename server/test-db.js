// A fresh, empty database for one test. Runs on SQLite in memory, or on
// PostgreSQL (each test in its own schema) when TEST_DATABASE_URL is set:
//   TEST_DATABASE_URL=postgres://user:pass@localhost/db npm test
import { randomBytes } from "node:crypto";
import { after } from "node:test";
import { openDatabase } from "./db.js";

const open = [];
after(() => Promise.all(open.map((db) => db.close())));

export async function testDatabase() {
  const url = process.env.TEST_DATABASE_URL;
  const db = url
    ? await openDatabase(url, { schema: `test_${randomBytes(6).toString("hex")}` })
    : await openDatabase(":memory:");
  open.push(db);
  return db;
}
