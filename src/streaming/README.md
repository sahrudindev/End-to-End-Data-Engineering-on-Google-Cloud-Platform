# Phase 2: Ingestion Pipelines

This directory contains the Apache Beam streaming pipeline for Pub/Sub to BigQuery ingestion.

## Prerequisites

- Python 3.9+
- Google Cloud SDK authenticated
- BigQuery table `ecommerce_dw.raw_events` exists (created by Terraform in Phase 1)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Local Testing (DirectRunner)

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=dataengineergcp-482812

# Run pipeline locally (processes a few messages then stops)
python pipeline.py \
    --project=$GOOGLE_CLOUD_PROJECT \
    --subscription=projects/$GOOGLE_CLOUD_PROJECT/subscriptions/ecommerce-events-sub \
    --output_table=$GOOGLE_CLOUD_PROJECT:ecommerce_dw.raw_events \
    --runner=DirectRunner
```

### Production (DataflowRunner)

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=dataengineergcp-482812
export REGION=asia-southeast2
export BUCKET=dataengineergcp-482812-dev-raw-data

# Deploy to Dataflow (runs continuously)
python pipeline.py \
    --project=$GOOGLE_CLOUD_PROJECT \
    --region=$REGION \
    --subscription=projects/$GOOGLE_CLOUD_PROJECT/subscriptions/ecommerce-events-sub \
    --output_table=$GOOGLE_CLOUD_PROJECT:ecommerce_dw.raw_events \
    --dead_letter_bucket=gs://$BUCKET/dead-letter \
    --runner=DataflowRunner \
    --temp_location=gs://$BUCKET/temp \
    --staging_location=gs://$BUCKET/staging \
    --job_name=ecommerce-streaming-ingest \
    --streaming \
    --setup_file=./setup.py
```

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Apache Beam Pipeline                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌────────────┐    ┌──────────┐    ┌─────────┐ │
│  │ Pub/Sub  │───▶│Parse JSON  │───▶│ Validate │───▶│ Enrich  │ │
│  │ Source   │    │            │    │          │    │Metadata │ │
│  └──────────┘    └────────────┘    └──────────┘    └────┬────┘ │
│                        │                                │      │
│                        │ (failed)                       │      │
│                        ▼                                ▼      │
│               ┌────────────────┐              ┌────────────┐   │
│               │ Dead Letter    │              │  BigQuery  │   │
│               │ (GCS)          │              │  Sink      │   │
│               └────────────────┘              └────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Quality Checks

The pipeline validates:
- Required fields: `order_id`, `user_id`, `status`, `amount`, `timestamp`, `product_category`
- Amount must be numeric and positive
- JSON must be well-formed

Failed records are written to `gs://BUCKET/dead-letter/` with error details.

## Testing the Pipeline

1. Start the pipeline (DirectRunner for testing):
   ```bash
   python pipeline.py --subscription=... --output_table=... --runner=DirectRunner
   ```

2. Generate test events using the generator:
   ```bash
   cd ../generator
   docker run --rm -v "$APPDATA/gcloud:/tmp/creds:ro" \
       -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/creds/application_default_credentials.json \
       -e GOOGLE_CLOUD_PROJECT=dataengineergcp-482812 \
       ecommerce-generator --num-events 50
   ```

3. Check BigQuery for ingested records:
   ```bash
   bq query --use_legacy_sql=false \
       "SELECT * FROM dataengineergcp-482812.ecommerce_dw.raw_events LIMIT 10"
   ```
