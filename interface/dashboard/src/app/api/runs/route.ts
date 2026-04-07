import { NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function GET() {
  try {
    const result = await query(
      'SELECT id, target_url, status, triggered_by, started_at, completed_at, error_message, report_id ' +
      'FROM run_log ' +
      'ORDER BY started_at DESC LIMIT 50'
    );
    return NextResponse.json(result.rows);
  } catch (error: any) {
    console.error('API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
