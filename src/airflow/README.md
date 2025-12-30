# Phase 2: Airflow Batch Pipeline

Local Apache Airflow environment for batch data ingestion from GCS to BigQuery.

## Prerequisites

- Docker and Docker Compose installed
- Google Cloud SDK authenticated (credentials at `%APPDATA%\gcloud\`)
- GCS bucket and BigQuery table created (Terraform Phase 1)

## Quick Start

### 1. Start Airflow

```powershell
# Navigate to airflow directory
cd src/airflow

# Initialize and start Airflow
docker compose up airflow-init
docker compose up -d

# Check status
docker compose ps
```

### 2. Access Web UI

- **URL**: http://localhost:8080
- **Username**: airflow
- **Password**: airflow

### 3. Enable the DAG

1. Go to http://localhost:8080
2. Find `gcs_to_bq_load` DAG
3. Toggle the switch to enable it

### 4. Test with Sample Data

```powershell
# Upload test CSV to GCS incoming folder
cd ../generator

# Generate and upload CSV to GCS
$credPath = "$env:APPDATA\gcloud\application_default_credentials.json"
docker run --rm `
    -v "${credPath}:/tmp/creds.json:ro" `
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/creds.json `
    ecommerce-generator --gcs-upload --gcs-bucket dataengineergcp-482812-dev-raw-data --num-events 100
```

### 5. Monitor DAG Execution

1. Go to Airflow UI → DAGs → `gcs_to_bq_load`
2. Click "Trigger DAG" manually or wait for scheduled run
3. Monitor task progress in Graph view

## DAG Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    gcs_to_bq_load DAG                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────┐    ┌──────────────┐    ┌───────────────┐            │
│  │ Start │───▶│ Check Files  │───▶│ List Files    │            │
│  └───────┘    │ (Sensor)     │    │ (Branch)      │            │
│               └──────────────┘    └───────┬───────┘            │
│                                           │                     │
│                          ┌────────────────┼────────────────┐   │
│                          ▼                ▼                │   │
│                  ┌──────────────┐  ┌──────────────┐        │   │
│                  │ Load to BQ   │  │ No Files     │        │   │
│                  └──────┬───────┘  └──────┬───────┘        │   │
│                         │                 │                │   │
│                         ▼                 │                │   │
│                  ┌──────────────┐         │                │   │
│                  │ Archive      │         │                │   │
│                  │ Files        │         │                │   │
│                  └──────┬───────┘         │                │   │
│                         │                 │                │   │
│                         ▼                 ▼                │   │
│                        ┌───────────────────┐               │   │
│                        │       End         │               │   │
│                        └───────────────────┘               │   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## File Processing Flow

1. **Sensor**: Detects new files in `gs://bucket/incoming/`
2. **Load**: Uses `GCSToBigQueryOperator` to load CSV
3. **Archive**: Moves processed files to `gs://bucket/archive/`

This ensures **idempotency** - files are only processed once.

## Stopping Airflow

```powershell
cd src/airflow
docker compose down

# To remove all data (fresh start)
docker compose down -v
```

## Troubleshooting

### Credentials Error

If you see "Could not automatically determine credentials":

1. Make sure `gcloud auth application-default login` was run
2. Check that credentials file exists:
   ```powershell
   Test-Path "$env:APPDATA\gcloud\application_default_credentials.json"
   ```

### DAG Not Appearing

1. Check scheduler logs:
   ```powershell
   docker compose logs airflow-scheduler
   ```
2. Verify DAG file syntax:
   ```powershell
   docker compose exec airflow-webserver python -c "from dags.ingest_gcs_to_bq import *"
   ```

### BigQuery Load Errors

1. Verify table exists and schema matches
2. Check CSV header matches BigQuery column names
3. Review task logs in Airflow UI
