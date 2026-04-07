import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

const globalForPg = global as unknown as { pool: Pool };

export const pool =
  globalForPg.pool ||
  new Pool({
    connectionString: process.env.DATABASE_URL || "postgresql://postgres:12345678@localhost:5432/competitive_intel",
  });

if (process.env.NODE_ENV !== "production") globalForPg.pool = pool;

export const db = drizzle(pool, { schema });

// Keep the raw query for compatibility if needed, but promote Drizzle usage
export async function query(text: string, params?: any[]) {
  const start = Date.now();
  const res = await pool.query(text, params);
  const duration = Date.now() - start;
  console.log("executed query", { text, duration, rows: res.rowCount });
  return res;
}
