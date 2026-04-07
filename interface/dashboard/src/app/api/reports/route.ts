import { NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const domain = searchParams.get('domain');

    let sql = 'SELECT id, target_url, target_domain, competitor_count, pdf_url, created_at FROM reports';
    let params: any[] = [];

    if (domain) {
      sql += ' WHERE target_domain ILIKE $1';
      params.push(`%${domain}%`);
    }

    sql += ' ORDER BY created_at DESC';

    const result = await query(sql, params);
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error('API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
