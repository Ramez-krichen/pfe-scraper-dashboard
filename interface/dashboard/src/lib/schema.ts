import { pgTable, text, integer, timestamp, uuid, jsonb, index } from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const targetCache = pgTable("target_cache", {
  id: uuid("id").default(sql`gen_random_uuid()`).primaryKey(),
  url: text("url").notNull(),
  domain: text("domain"),
  scrapedData: jsonb("scraped_data"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).default(sql`now() + interval '24 hours'`).notNull(),
}, (table) => [
  index("idx_target_cache_domain_expires").on(table.domain, table.expiresAt),
]);

export const competitorCache = pgTable("competitor_cache", {
  id: uuid("id").default(sql`gen_random_uuid()`).primaryKey(),
  domain: text("domain").notNull(),
  url: text("url"),
  scrapedData: jsonb("scraped_data"),
  apiData: jsonb("api_data"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  expiresAt: timestamp("expires_at", { withTimezone: true }).default(sql`now() + interval '24 hours'`).notNull(),
}, (table) => [
  index("idx_competitor_cache_domain_expires").on(table.domain, table.expiresAt),
]);

export const reports = pgTable("reports", {
  id: uuid("id").default(sql`gen_random_uuid()`).primaryKey(),
  targetUrl: text("target_url").notNull(),
  targetDomain: text("target_domain"),
  reportData: jsonb("report_data"),
  pdfUrl: text("pdf_url"),
  competitorCount: integer("competitor_count"),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
}, (table) => [
  index("idx_reports_target_domain_created").on(table.targetDomain, table.createdAt),
]);

export const runLog = pgTable("run_log", {
  id: uuid("id").default(sql`gen_random_uuid()`).primaryKey(),
  targetUrl: text("target_url"),
  status: text("status").default("running").notNull(),
  triggeredBy: text("triggered_by"),
  startedAt: timestamp("started_at", { withTimezone: true }).defaultNow().notNull(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
  errorMessage: text("error_message"),
  reportId: uuid("report_id").references(() => reports.id),
}, (table) => [
  index("idx_run_log_status").on(table.status),
  index("idx_run_log_started_at").on(table.startedAt.desc()),
]);
