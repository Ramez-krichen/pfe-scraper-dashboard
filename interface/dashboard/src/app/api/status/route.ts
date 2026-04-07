import { NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const domain = searchParams.get('domain');

    if (!domain) {
      return NextResponse.json({ error: 'Domain is required' }, { status: 400 });
    }

    // Get the latest run_log for this domain (using target_url or domain in future?)
    // For now, check run_log where target_url matches or domain matches
    const result = await query(
      'SELECT id, status, started_at, completed_at, error_message, report_id ' +
      'FROM run_log ' +
      'WHERE target_url ILIKE $1 ' +
      'ORDER BY started_at DESC LIMIT 1',
      [`%${domain}%`]
    );

    if (result.rowCount === 0) {
      return NextResponse.json({ status: 'not_found' });
    }

    return NextResponse.json(result.rows[0]);
  } catch (error: any) {
    console.error('API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
