import { NextResponse } from 'next/server';
import { query } from '@/lib/db';

export async function POST(req: Request) {
  try {
    const { url, triggeredBy } = await req.json();

    if (!url) {
      return NextResponse.json({ error: 'URL is required' }, { status: 400 });
    }

    // 1. Create a log entry in run_log
    const runResult = await query(
      'INSERT INTO run_log (target_url, status, triggered_by, started_at) VALUES ($1, $2, $3, NOW()) RETURNING id',
      [url, 'running', triggeredBy || 'dashboard']
    );
    const runId = runResult.rows[0].id;

    // 2. Trigger n8n webhook
    const n8nWebhookUrl = process.env.N8N_WEBHOOK_URL;
    if (!n8nWebhookUrl) {
      console.error('N8N_WEBHOOK_URL not configured');
      // Update run_log as failed if n8n is not configured
      await query(
        'UPDATE run_log SET status = $1, error_message = $2, completed_at = NOW() WHERE id = $3',
        ['failed', 'N8N_WEBHOOK_URL not configured', runId]
      );
      return NextResponse.json({ error: 'System configuration error' }, { status: 500 });
    }

    // Non-blocking trigger to n8n (or wait for it?)
    // Usually, we just trigger it and let it run.
    fetch(n8nWebhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, triggeredBy: triggeredBy || 'dashboard', runId }),
    }).catch(err => {
      console.error('Error triggering n8n:', err);
      query(
        'UPDATE run_log SET status = $1, error_message = $2, completed_at = NOW() WHERE id = $3',
        ['failed', 'Failed to reach n8n webhook', runId]
      );
    });

    return NextResponse.json({ runId, status: 'running' });
  } catch (error: any) {
    console.error('API Error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
