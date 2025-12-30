"""
GCS to BigQuery Batch Ingestion DAG

This DAG monitors the GCS bucket for new CSV files, loads them into BigQuery,
and moves processed files to an archive folder for idempotency.

Schedule: Runs every 15 minutes
Path: gs://{bucket}/incoming/*.csv -> BigQuery -> gs://{bucket}/archive/

Author: Data Engineering Team
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.sensors.gcs import GCSObjectsWithPrefixExistenceSensor
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.transfers.gcs_to_gcs import GCSToGCSOperator
from airflow.providers.google.cloud.operators.gcs import GCSDeleteObjectsOperator
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule


# =============================================================================
# Configuration
# =============================================================================

# GCP Settings from environment variables
GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "dataengineergcp-482812")
GCS_BUCKET = os.getenv("GCP_BUCKET_NAME", "dataengineergcp-482812-dev-raw-data")
BQ_DATASET = os.getenv("BIGQUERY_DATASET", "ecommerce_dw")
BQ_TABLE = os.getenv("BIGQUERY_TABLE", "raw_events")

# GCS Paths
INCOMING_PREFIX = "incoming/"
ARCHIVE_PREFIX = "archive/"

# BigQuery Schema for CSV loading
BIGQUERY_SCHEMA = [
    {"name": "order_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "user_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "status", "type": "STRING", "mode": "REQUIRED"},
    {"name": "amount", "type": "FLOAT64", "mode": "REQUIRED"},
    {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "product_category", "type": "STRING", "mode": "REQUIRED"},
    {"name": "ingestion_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "source", "type": "STRING", "mode": "NULLABLE"},
]

# =============================================================================
# DAG Default Arguments
# =============================================================================

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "start_date": datetime(2024, 1, 1),
}

# =============================================================================
# Helper Functions
# =============================================================================

def list_incoming_files(**context):
    """
    List CSV files in the incoming folder and push to XCom.
    Returns list of file names to process.
    """
    from airflow.providers.google.cloud.hooks.gcs import GCSHook
    
    hook = GCSHook()
    blobs = hook.list(bucket_name=GCS_BUCKET, prefix=INCOMING_PREFIX)
    
    # Filter for CSV files only
    csv_files = [
        blob for blob in blobs 
        if blob.endswith(".csv") and blob != INCOMING_PREFIX
    ]
    
    if csv_files:
        context["ti"].xcom_push(key="csv_files", value=csv_files)
        print(f"Found {len(csv_files)} CSV files to process: {csv_files}")
        return "load_csv_to_bigquery"
    else:
        print("No CSV files found in incoming folder")
        return "no_files_to_process"


def get_archive_destination(source_object: str) -> str:
    """Generate archive path for a source file."""
    filename = source_object.split("/")[-1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ARCHIVE_PREFIX}{timestamp}_{filename}"


# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id="gcs_to_bq_load",
    default_args=default_args,
    description="Load CSV files from GCS to BigQuery and archive processed files",
    schedule_interval="*/15 * * * *",  # Every 15 minutes
    catchup=False,
    max_active_runs=1,
    tags=["ecommerce", "batch", "bigquery", "gcs"],
) as dag:
    
    # -------------------------------------------------------------------------
    # Task: Start
    # -------------------------------------------------------------------------
    start = EmptyOperator(task_id="start")
    
    # -------------------------------------------------------------------------
    # Task: Sensor - Check for new files in incoming folder
    # -------------------------------------------------------------------------
    check_for_files = GCSObjectsWithPrefixExistenceSensor(
        task_id="check_for_incoming_files",
        bucket=GCS_BUCKET,
        prefix=INCOMING_PREFIX,
        mode="reschedule",  # Don't block a worker slot while waiting
        poke_interval=60,
        timeout=60 * 10,  # 10 minutes timeout
        soft_fail=True,  # Don't fail DAG if no files found
    )
    
    # -------------------------------------------------------------------------
    # Task: Branch - List files and decide next step
    # -------------------------------------------------------------------------
    list_files = BranchPythonOperator(
        task_id="list_incoming_files",
        python_callable=list_incoming_files,
    )
    
    # -------------------------------------------------------------------------
    # Task: No files to process (skip branch)
    # -------------------------------------------------------------------------
    no_files = EmptyOperator(task_id="no_files_to_process")
    
    # -------------------------------------------------------------------------
    # Task: Load CSV to BigQuery
    # -------------------------------------------------------------------------
    load_to_bq = GCSToBigQueryOperator(
        task_id="load_csv_to_bigquery",
        bucket=GCS_BUCKET,
        source_objects=[f"{INCOMING_PREFIX}*.csv"],
        destination_project_dataset_table=f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}",
        schema_fields=BIGQUERY_SCHEMA,
        source_format="CSV",
        skip_leading_rows=1,  # Skip header row
        write_disposition="WRITE_APPEND",
        create_disposition="CREATE_NEVER",  # Table must exist
        allow_quoted_newlines=True,
        allow_jagged_rows=False,
    )
    
    # -------------------------------------------------------------------------
    # Task: Move processed files to archive
    # -------------------------------------------------------------------------
    archive_files = GCSToGCSOperator(
        task_id="archive_processed_files",
        source_bucket=GCS_BUCKET,
        source_object=f"{INCOMING_PREFIX}*.csv",
        destination_bucket=GCS_BUCKET,
        destination_object=ARCHIVE_PREFIX,
        move_object=True,  # Move instead of copy (deletes source)
    )
    
    # -------------------------------------------------------------------------
    # Task: End
    # -------------------------------------------------------------------------
    end = EmptyOperator(
        task_id="end",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
    
    # -------------------------------------------------------------------------
    # DAG Flow
    # -------------------------------------------------------------------------
    start >> check_for_files >> list_files
    list_files >> [load_to_bq, no_files]
    load_to_bq >> archive_files >> end
    no_files >> end
