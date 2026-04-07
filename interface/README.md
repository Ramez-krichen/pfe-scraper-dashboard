# Competitive Intelligence Automation System

A full-stack, AI-powered system for monitoring and analyzing competitor ecommerce sites. This system coordinates a web scraper, an n8n automation workflow, and a Next.js dashboard to provide strategic business insights.

## 🚀 Overview

The system works by:
1.  **Dashboard**: User enters a target URL in the [Next.js Dashboard](file:///C:/Users/ramez/Desktop/PFE/dashboard).
2.  **n8n Workflow**: The dashboard triggers a webhook in n8n.
3.  **Scraper**: n8n calls a FastAPI-based scraper (FastAPI) to fetch product data.
4.  **AI Intelligence**: n8n processes the data through 6 AI nodes (OpenRouter) for competitive analysis.
5.  **Data Storage**: Results are stored in [PostgreSQL](file:///C:/Users/ramez/Desktop/PFE/schema/init.sql).
6.  **Reporting**: Users view rich reports and live run logs on the dashboard.

## 🛠️ Infrastructure Setup

### 1. Database (PostgreSQL)
Initialize the database schema by running:
```bash
psql -d <your_db_name> -f schema/init.sql
```

### 2. Dashboard (Next.js 14)
The dashboard is located in the `dashboard` folder.

**Required Environment Variables (`dashboard/.env.local`):**
- `N8N_WEBHOOK_URL`: The endpoint to trigger the n8n workflow.
- `DATABASE_URL`: Your PostgreSQL connection string.
- `SCRAPER_API_URL`: The base URL of your FastAPI scraper.

**Running the Dashboard:**
```bash
cd dashboard
npm install
npm run dev
```

### 3. n8n Workflow (External)
Ensure your n8n instance is configured with the following credentials:
- `openRouterApi`: For AI analysis nodes.
- `Slack`: For alert notifications.
- `Gmail`: For report delivery.
- `PostgreSQL`: For data persistence and report retrieval.

## 📂 Project Structure

-   `dashboard/`: Next.js 14 App Router application.
-   `schema/`: PostgreSQL migration and table definitions.
-   `README.md`: This documentation.

## 🧪 Documentation & Walkthrough
A detailed build walkthrough can be found in the [walkthrough.md](file:///C:/Users/ramez/.gemini/antigravity/brain/19256c90-795b-47a8-816b-1a0490bda745/walkthrough.md) artifact from the build process.
