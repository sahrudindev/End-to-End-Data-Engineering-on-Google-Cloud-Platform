"""
E-commerce Streaming Pipeline

Apache Beam pipeline that ingests events from Pub/Sub and writes to BigQuery.
Includes data validation, dead-letter handling, and metadata enrichment.

Usage:
    # Local testing with DirectRunner
    python pipeline.py \
        --project=YOUR_PROJECT_ID \
        --subscription=projects/YOUR_PROJECT_ID/subscriptions/ecommerce-events-sub \
        --output_table=YOUR_PROJECT_ID:ecommerce_dw.raw_events \
        --dead_letter_bucket=gs://YOUR_BUCKET/dead-letter \
        --runner=DirectRunner

    # Production with DataflowRunner
    python pipeline.py \
        --project=YOUR_PROJECT_ID \
        --region=asia-southeast2 \
        --subscription=projects/YOUR_PROJECT_ID/subscriptions/ecommerce-events-sub \
        --output_table=YOUR_PROJECT_ID:ecommerce_dw.raw_events \
        --dead_letter_bucket=gs://YOUR_BUCKET/dead-letter \
        --runner=DataflowRunner \
        --temp_location=gs://YOUR_BUCKET/temp \
        --staging_location=gs://YOUR_BUCKET/staging \
        --job_name=ecommerce-streaming-ingest \
        --streaming
"""

import argparse
import json
import logging
from datetime import datetime
from typing import Any, Dict, Tuple

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition
from apache_beam.io.gcp.pubsub import ReadFromPubSub

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# BigQuery table schema
BIGQUERY_SCHEMA = {
    "fields": [
        {"name": "order_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "user_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "status", "type": "STRING", "mode": "REQUIRED"},
        {"name": "amount", "type": "FLOAT64", "mode": "REQUIRED"},
        {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "product_category", "type": "STRING", "mode": "REQUIRED"},
        {"name": "ingestion_timestamp", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "source", "type": "STRING", "mode": "NULLABLE"},
    ]
}

# Required fields for validation
REQUIRED_FIELDS = ["order_id", "user_id", "status", "amount", "timestamp", "product_category"]


class ParseAndValidateJson(beam.DoFn):
    """
    Parse JSON messages and validate required fields.
    
    Outputs:
        - Main output: Valid records (tagged 'valid')
        - Side output: Failed records with error info (tagged 'failed')
    """
    
    VALID_TAG = "valid"
    FAILED_TAG = "failed"
    
    def process(self, element: bytes) -> Tuple[Dict[str, Any], str]:
        """Process a single Pub/Sub message."""
        try:
            # Decode and parse JSON
            message_str = element.decode("utf-8")
            record = json.loads(message_str)
            
            # Validate required fields
            missing_fields = [
                field for field in REQUIRED_FIELDS 
                if field not in record or record[field] is None
            ]
            
            if missing_fields:
                yield beam.pvalue.TaggedOutput(
                    self.FAILED_TAG,
                    {
                        "original_message": message_str,
                        "error": f"Missing required fields: {missing_fields}",
                        "error_timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                )
                return
            
            # Validate amount is numeric and positive
            try:
                amount = float(record["amount"])
                if amount < 0:
                    raise ValueError("Amount must be positive")
            except (ValueError, TypeError) as e:
                yield beam.pvalue.TaggedOutput(
                    self.FAILED_TAG,
                    {
                        "original_message": message_str,
                        "error": f"Invalid amount: {str(e)}",
                        "error_timestamp": datetime.utcnow().isoformat() + "Z",
                    }
                )
                return
            
            # Output valid record
            yield beam.pvalue.TaggedOutput(self.VALID_TAG, record)
            
        except json.JSONDecodeError as e:
            yield beam.pvalue.TaggedOutput(
                self.FAILED_TAG,
                {
                    "original_message": element.decode("utf-8", errors="replace"),
                    "error": f"JSON parse error: {str(e)}",
                    "error_timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )
        except Exception as e:
            yield beam.pvalue.TaggedOutput(
                self.FAILED_TAG,
                {
                    "original_message": str(element),
                    "error": f"Unexpected error: {str(e)}",
                    "error_timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )


class EnrichWithMetadata(beam.DoFn):
    """
    Add ingestion metadata to valid records.
    
    - Converts 'timestamp' field to 'event_timestamp'
    - Adds 'ingestion_timestamp' 
    - Adds 'source' field
    """
    
    def process(self, record: Dict[str, Any]):
        """Enrich record with metadata."""
        # Get current timestamp for ingestion
        ingestion_time = datetime.utcnow().isoformat() + "Z"
        
        # Transform the record for BigQuery
        enriched = {
            "order_id": record["order_id"],
            "user_id": record["user_id"],
            "status": record["status"],
            "amount": float(record["amount"]),
            "event_timestamp": record["timestamp"],  # Rename timestamp -> event_timestamp
            "product_category": record["product_category"],
            "ingestion_timestamp": ingestion_time,
            "source": "streaming",
        }
        
        yield enriched


class FormatDeadLetter(beam.DoFn):
    """Format failed records for storage."""
    
    def process(self, record: Dict[str, Any]):
        """Convert failed record to JSON string for GCS."""
        yield json.dumps(record)


def run_pipeline(argv=None):
    """
    Main pipeline execution function.
    """
    parser = argparse.ArgumentParser(
        description="E-commerce Streaming Pipeline: Pub/Sub to BigQuery"
    )
    
    # Required arguments
    parser.add_argument(
        "--subscription",
        required=True,
        help="Pub/Sub subscription path (projects/PROJECT/subscriptions/SUB)",
    )
    parser.add_argument(
        "--output_table",
        required=True,
        help="BigQuery output table (PROJECT:DATASET.TABLE)",
    )
    parser.add_argument(
        "--dead_letter_bucket",
        default=None,
        help="GCS path for dead-letter records (gs://bucket/path)",
    )
    
    # Parse known args, pass remaining to PipelineOptions
    known_args, pipeline_args = parser.parse_known_args(argv)
    
    # Configure pipeline options
    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True
    
    logger.info(f"Starting pipeline with subscription: {known_args.subscription}")
    logger.info(f"Output table: {known_args.output_table}")
    
    # Build and run the pipeline
    with beam.Pipeline(options=pipeline_options) as pipeline:
        # Read from Pub/Sub
        messages = (
            pipeline
            | "Read from Pub/Sub" >> ReadFromPubSub(subscription=known_args.subscription)
        )
        
        # Parse and validate JSON
        parsed = (
            messages
            | "Parse and Validate" >> beam.ParDo(ParseAndValidateJson()).with_outputs(
                ParseAndValidateJson.VALID_TAG,
                ParseAndValidateJson.FAILED_TAG,
            )
        )
        
        valid_records = parsed[ParseAndValidateJson.VALID_TAG]
        failed_records = parsed[ParseAndValidateJson.FAILED_TAG]
        
        # Enrich valid records with metadata
        enriched_records = (
            valid_records
            | "Enrich with Metadata" >> beam.ParDo(EnrichWithMetadata())
        )
        
        # Write to BigQuery
        _ = (
            enriched_records
            | "Write to BigQuery" >> WriteToBigQuery(
                table=known_args.output_table,
                schema=BIGQUERY_SCHEMA,
                create_disposition=BigQueryDisposition.CREATE_NEVER,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                method="STREAMING_INSERTS",
            )
        )
        
        # Handle dead-letter records
        if known_args.dead_letter_bucket:
            _ = (
                failed_records
                | "Format Dead Letter" >> beam.ParDo(FormatDeadLetter())
                | "Write Dead Letter" >> beam.io.WriteToText(
                    file_path_prefix=f"{known_args.dead_letter_bucket}/failed",
                    file_name_suffix=".json",
                    num_shards=1,
                )
            )
        else:
            # Log failed records if no dead-letter bucket specified
            _ = (
                failed_records
                | "Log Failed Records" >> beam.Map(
                    lambda x: logger.warning(f"Failed record: {x}")
                )
            )
    
    logger.info("Pipeline completed successfully")


if __name__ == "__main__":
    run_pipeline()
