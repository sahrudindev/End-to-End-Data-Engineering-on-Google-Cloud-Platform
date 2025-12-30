# Architecture Documentation

## Phase 1: Foundation & Data Generation

This document describes the architecture for Phase 1 of the E-commerce Data Platform.

## Components

### 1. Data Generator (`src/generator/`)

A Dockerized Python application that simulates e-commerce transactions:

- **Technology**: Python 3.11 with Faker library
- **Output**: JSON events published to Pub/Sub
- **Modes**:
  - Streaming: Real-time publishing to Pub/Sub
  - Batch: Save events to JSONL file for batch loading

### 2. Cloud Storage (GCS)

Raw data lake with lifecycle management:

- **Bucket Structure**:
  ```
  gs://project-id-dev-raw-data/
  ├── raw/           # Raw ingested files
  ├── processed/     # Processed files
  └── archive/       # Archived data
  ```
- **Lifecycle Rules**:
  - Move to Nearline after 90 days
  - Move to Coldline after 180 days

### 3. BigQuery Data Warehouse

Structured storage with cost optimization:

- **Dataset**: `ecommerce_dw`
- **Tables**:
  - `raw_events`: Partitioned by day on `event_timestamp`
  - Clustered by `product_category`, `status`

### 4. Pub/Sub Messaging

Real-time event streaming:

- **Topic**: `ecommerce-events`
- **Subscription**: `ecommerce-events-sub`
  - Pull subscription for Dataflow (Phase 2)
  - 7-day message retention
  - 60-second ack deadline

## Data Flow (Phase 1)

```
Generator (Docker)
      │
      ▼
  Pub/Sub Topic
  (ecommerce-events)
      │
      ▼
  Pub/Sub Subscription ──────▶ [Phase 2: Dataflow]
  (ecommerce-events-sub)
```

## Security Model

### Service Account: `ecommerce-data-pipeline`

**Roles**:
- `roles/pubsub.publisher` - Publish events
- `roles/pubsub.subscriber` - Read events
- `roles/bigquery.dataEditor` - Write to BigQuery
- `roles/bigquery.jobUser` - Run queries
- `roles/storage.objectAdmin` - Manage GCS files

## Cost Optimization

1. **BigQuery Partitioning**: Reduces scan costs by limiting data read
2. **BigQuery Clustering**: Improves query performance
3. **GCS Lifecycle**: Automatic tiering to cheaper storage
4. **Pub/Sub**: Pay only for messages published/delivered

## Next Steps (Phase 2)

- Dataflow streaming pipeline
- Airflow for batch orchestration
- Dead letter queue for failed messages
