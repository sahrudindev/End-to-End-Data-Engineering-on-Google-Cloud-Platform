"""
E-commerce Event Data Generator

Generates fake e-commerce transaction events and publishes them to Google Cloud Pub/Sub.
This script is designed to simulate high-volume transaction data for testing data pipelines.

Usage:
    python main.py                         # Default: 100 events, publish to Pub/Sub
    python main.py --num-events 1000       # Generate 1000 events
    python main.py --dry-run               # Print events without publishing
    python main.py --batch-mode --output-file events.jsonl   # Save to JSONL file
    python main.py --csv-mode --output-file events.csv       # Save to CSV file
    python main.py --gcs-upload --gcs-bucket bucket-name     # Upload CSV to GCS for Airflow
"""

import argparse
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional
import csv
import io

from faker import Faker
from google.cloud import pubsub_v1
from google.cloud import storage
from google.api_core import exceptions as gcp_exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize Faker with seed for reproducibility in testing
fake = Faker()
Faker.seed(42)

# Constants
PRODUCT_CATEGORIES = [
    "Electronics",
    "Clothing",
    "Home & Garden",
    "Sports & Outdoors",
    "Books",
    "Toys & Games",
    "Health & Beauty",
    "Automotive",
    "Food & Grocery",
    "Jewelry",
]

ORDER_STATUSES = [
    "pending",
    "processing",
    "shipped",
    "delivered",
    "cancelled",
]

# Status weights (more realistic distribution)
STATUS_WEIGHTS = [0.15, 0.20, 0.25, 0.35, 0.05]


def generate_event() -> Dict[str, Any]:
    """
    Generate a single e-commerce transaction event.
    
    Returns:
        Dict containing order details with realistic fake data.
    """
    # Generate timestamp within last 30 days for more realistic data distribution
    days_ago = fake.random_int(min=0, max=30)
    hours_ago = fake.random_int(min=0, max=23)
    minutes_ago = fake.random_int(min=0, max=59)
    
    event_time = datetime.utcnow() - timedelta(
        days=days_ago, hours=hours_ago, minutes=minutes_ago
    )
    
    # Generate amount with realistic distribution (most orders $10-$500)
    amount = round(fake.random.lognormvariate(4.5, 1.0), 2)
    amount = min(max(amount, 5.0), 10000.0)  # Clamp to reasonable range
    
    return {
        "order_id": str(uuid.uuid4()),
        "user_id": f"user_{fake.random_int(min=1000, max=99999)}",
        "status": random.choices(ORDER_STATUSES, weights=STATUS_WEIGHTS, k=1)[0],
        "amount": amount,
        "timestamp": event_time.isoformat() + "Z",
        "product_category": fake.random_element(elements=PRODUCT_CATEGORIES),
    }


def generate_events(num_events: int) -> Generator[Dict[str, Any], None, None]:
    """
    Generator that yields specified number of events.
    
    Args:
        num_events: Number of events to generate.
        
    Yields:
        Dict containing event data.
    """
    for _ in range(num_events):
        yield generate_event()


def publish_to_pubsub(
    project_id: str,
    topic_name: str,
    events: List[Dict[str, Any]],
    batch_size: int = 100,
) -> int:
    """
    Publish events to Google Cloud Pub/Sub topic.
    
    Args:
        project_id: GCP project ID.
        topic_name: Pub/Sub topic name.
        events: List of event dictionaries to publish.
        batch_size: Number of messages to publish before logging progress.
        
    Returns:
        Number of successfully published messages.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)
    
    published_count = 0
    futures = []
    
    logger.info(f"Publishing {len(events)} events to {topic_path}")
    
    for i, event in enumerate(events):
        # Convert event to JSON bytes
        message_data = json.dumps(event).encode("utf-8")
        
        # Publish message with attributes for filtering
        future = publisher.publish(
            topic_path,
            message_data,
            order_id=event["order_id"],
            status=event["status"],
            category=event["product_category"],
        )
        futures.append(future)
        
        # Log progress
        if (i + 1) % batch_size == 0:
            logger.info(f"Queued {i + 1}/{len(events)} messages...")
    
    # Wait for all futures to complete
    logger.info("Waiting for publish confirmations...")
    for future in futures:
        try:
            message_id = future.result(timeout=60)
            published_count += 1
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
    
    return published_count


def save_to_file(events: List[Dict[str, Any]], output_file: str) -> None:
    """
    Save events to a JSONL file (batch mode).
    
    Args:
        events: List of event dictionaries.
        output_file: Path to output file.
    """
    with open(output_file, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    logger.info(f"Saved {len(events)} events to {output_file}")


def save_to_csv(events: List[Dict[str, Any]], output_file: str) -> None:
    """
    Save events to a CSV file for BigQuery batch loading.
    
    Args:
        events: List of event dictionaries.
        output_file: Path to output file.
    """
    if not events:
        logger.warning("No events to save")
        return
    
    # Define column order matching BigQuery schema
    fieldnames = [
        "order_id", "user_id", "status", "amount",
        "event_timestamp", "product_category", "ingestion_timestamp", "source"
    ]
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        ingestion_time = datetime.utcnow().isoformat() + "Z"
        for event in events:
            row = {
                "order_id": event["order_id"],
                "user_id": event["user_id"],
                "status": event["status"],
                "amount": event["amount"],
                "event_timestamp": event["timestamp"],
                "product_category": event["product_category"],
                "ingestion_timestamp": ingestion_time,
                "source": "batch",
            }
            writer.writerow(row)
    
    logger.info(f"Saved {len(events)} events to CSV: {output_file}")


def upload_to_gcs(
    events: List[Dict[str, Any]],
    bucket_name: str,
    destination_prefix: str = "incoming",
) -> str:
    """
    Upload events as CSV to GCS bucket for Airflow batch processing.
    
    Args:
        events: List of event dictionaries.
        bucket_name: GCS bucket name.
        destination_prefix: Folder prefix in bucket.
        
    Returns:
        GCS URI of uploaded file.
    """
    if not events:
        logger.warning("No events to upload")
        return ""
    
    # Generate unique filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"events_{timestamp}.csv"
    blob_name = f"{destination_prefix}/{filename}"
    
    # Create CSV content in memory
    fieldnames = [
        "order_id", "user_id", "status", "amount",
        "event_timestamp", "product_category", "ingestion_timestamp", "source"
    ]
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    ingestion_time = datetime.utcnow().isoformat() + "Z"
    for event in events:
        row = {
            "order_id": event["order_id"],
            "user_id": event["user_id"],
            "status": event["status"],
            "amount": event["amount"],
            "event_timestamp": event["timestamp"],
            "product_category": event["product_category"],
            "ingestion_timestamp": ingestion_time,
            "source": "batch",
        }
        writer.writerow(row)
    
    csv_content = output.getvalue()
    
    # Upload to GCS
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(csv_content, content_type="text/csv")
    
    gcs_uri = f"gs://{bucket_name}/{blob_name}"
    logger.info(f"Uploaded {len(events)} events to {gcs_uri}")
    
    return gcs_uri


def main():
    """Main entry point for the data generator."""
    parser = argparse.ArgumentParser(
        description="Generate fake e-commerce transaction events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GOOGLE_CLOUD_PROJECT  GCP project ID (required unless --dry-run)
  PUBSUB_TOPIC          Pub/Sub topic name (default: ecommerce-events)
  NUM_EVENTS            Number of events to generate (default: 100)
  GCS_BUCKET            GCS bucket name for --gcs-upload mode

Examples:
  # Dry run - print events without publishing
  python main.py --dry-run --num-events 10

  # Publish to Pub/Sub (streaming)
  export GOOGLE_CLOUD_PROJECT=my-project
  python main.py --num-events 1000

  # Batch mode - save to JSONL file
  python main.py --batch-mode --output-file events.jsonl --num-events 5000

  # CSV mode - save to CSV file
  python main.py --csv-mode --output-file events.csv --num-events 5000

  # GCS upload - upload CSV to GCS for Airflow batch processing
  python main.py --gcs-upload --gcs-bucket my-bucket --num-events 500
        """,
    )
    
    parser.add_argument(
        "--num-events",
        type=int,
        default=int(os.getenv("NUM_EVENTS", "100")),
        help="Number of events to generate (default: 100)",
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.getenv("BATCH_SIZE", "100")),
        help="Batch size for progress logging (default: 100)",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print events to stdout instead of publishing",
    )
    
    parser.add_argument(
        "--batch-mode",
        action="store_true",
        help="Save events to JSONL file instead of publishing to Pub/Sub",
    )
    
    parser.add_argument(
        "--csv-mode",
        action="store_true",
        help="Save events to CSV file for BigQuery batch loading",
    )
    
    parser.add_argument(
        "--gcs-upload",
        action="store_true",
        help="Upload CSV file to GCS bucket for Airflow batch processing",
    )
    
    parser.add_argument(
        "--gcs-bucket",
        type=str,
        default=os.getenv("GCS_BUCKET", ""),
        help="GCS bucket name for --gcs-upload mode",
    )
    
    parser.add_argument(
        "--gcs-prefix",
        type=str,
        default="incoming",
        help="GCS path prefix for uploaded files (default: incoming)",
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="events.jsonl",
        help="Output file path for batch/csv mode (default: events.jsonl)",
    )
    
    parser.add_argument(
        "--project-id",
        type=str,
        default=os.getenv("GOOGLE_CLOUD_PROJECT"),
        help="GCP project ID (can also use GOOGLE_CLOUD_PROJECT env var)",
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        default=os.getenv("PUBSUB_TOPIC", "ecommerce-events"),
        help="Pub/Sub topic name (default: ecommerce-events)",
    )
    
    args = parser.parse_args()
    
    # Validate arguments based on mode
    is_local_mode = args.dry_run or args.batch_mode or args.csv_mode
    
    if args.gcs_upload and not args.gcs_bucket:
        logger.error("Error: --gcs-bucket is required when using --gcs-upload")
        sys.exit(1)
    
    if not is_local_mode and not args.gcs_upload and not args.project_id:
        logger.error(
            "Error: GOOGLE_CLOUD_PROJECT environment variable or --project-id required"
        )
        sys.exit(1)
    
    # Generate events
    logger.info(f"Generating {args.num_events} fake e-commerce events...")
    start_time = time.time()
    events = list(generate_events(args.num_events))
    generation_time = time.time() - start_time
    logger.info(f"Generated {len(events)} events in {generation_time:.2f}s")
    
    # Handle output based on mode
    if args.dry_run:
        logger.info("DRY RUN MODE - Printing sample events:")
        for event in events[:10]:  # Print first 10
            print(json.dumps(event, indent=2))
        if len(events) > 10:
            print(f"... and {len(events) - 10} more events")
    
    elif args.csv_mode:
        save_to_csv(events, args.output_file)
    
    elif args.gcs_upload:
        try:
            gcs_uri = upload_to_gcs(
                events=events,
                bucket_name=args.gcs_bucket,
                destination_prefix=args.gcs_prefix,
            )
            total_time = time.time() - start_time
            logger.info(f"Upload completed in {total_time:.2f}s")
            print(f"Uploaded to: {gcs_uri}")
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            sys.exit(1)
    
    elif args.batch_mode:
        save_to_file(events, args.output_file)
    
    else:
        # Default: Pub/Sub streaming mode
        try:
            published = publish_to_pubsub(
                project_id=args.project_id,
                topic_name=args.topic,
                events=events,
                batch_size=args.batch_size,
            )
            total_time = time.time() - start_time
            logger.info(
                f"Successfully published {published}/{len(events)} events "
                f"in {total_time:.2f}s ({published/total_time:.1f} events/sec)"
            )
        except gcp_exceptions.NotFound:
            logger.error(
                f"Topic '{args.topic}' not found in project '{args.project_id}'. "
                "Make sure to run 'terraform apply' first."
            )
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to publish events: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

