################################################################################
# Main Infrastructure Resources
# E-commerce Data Platform - Phase 1: Infrastructure
################################################################################

#-------------------------------------------------------------------------------
# Enable Required APIs
#-------------------------------------------------------------------------------

resource "google_project_service" "required_apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "pubsub.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

#-------------------------------------------------------------------------------
# Service Account for Data Pipeline
#-------------------------------------------------------------------------------

resource "google_service_account" "data_pipeline_sa" {
  account_id   = "ecommerce-data-pipeline"
  display_name = "E-commerce Data Pipeline Service Account"
  description  = "Service account for data ingestion and processing pipelines"
  project      = var.project_id

  depends_on = [google_project_service.required_apis]
}

# IAM Roles for Service Account
resource "google_project_iam_member" "data_pipeline_roles" {
  for_each = toset([
    "roles/pubsub.publisher",    # Publish messages to Pub/Sub
    "roles/pubsub.subscriber",   # Subscribe to Pub/Sub topics
    "roles/bigquery.dataEditor", # Write data to BigQuery
    "roles/bigquery.jobUser",    # Run BigQuery jobs
    "roles/storage.objectAdmin", # Manage GCS objects
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.data_pipeline_sa.email}"

  depends_on = [google_service_account.data_pipeline_sa]
}

#-------------------------------------------------------------------------------
# Cloud Storage Bucket for Raw Data
#-------------------------------------------------------------------------------

resource "google_storage_bucket" "raw_data" {
  name          = local.gcs_bucket_name
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment != "prod" # Prevent accidental deletion in prod

  # Enable versioning for data protection
  versioning {
    enabled = true
  }

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  # Lifecycle rules for cost optimization
  lifecycle_rule {
    condition {
      age = var.data_retention_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = var.data_retention_days * 2
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  # Delete non-current versions after 30 days
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.required_apis]
}

# Create folder structure in bucket
resource "google_storage_bucket_object" "raw_folder" {
  name    = "raw/"
  content = " " # Empty content, just creating the folder
  bucket  = google_storage_bucket.raw_data.name
}

resource "google_storage_bucket_object" "processed_folder" {
  name    = "processed/"
  content = " "
  bucket  = google_storage_bucket.raw_data.name
}

resource "google_storage_bucket_object" "archive_folder" {
  name    = "archive/"
  content = " "
  bucket  = google_storage_bucket.raw_data.name
}

#-------------------------------------------------------------------------------
# BigQuery Dataset and Table
#-------------------------------------------------------------------------------

resource "google_bigquery_dataset" "ecommerce_dw" {
  dataset_id  = var.bigquery_dataset_id
  project     = var.project_id
  location    = var.region
  description = "E-commerce Data Warehouse - Raw and transformed event data"

  # Default table expiration (null = no expiration)
  default_table_expiration_ms = null

  labels = local.common_labels

  depends_on = [google_project_service.required_apis]
}

resource "google_bigquery_table" "raw_events" {
  dataset_id          = google_bigquery_dataset.ecommerce_dw.dataset_id
  table_id            = var.bigquery_table_id
  project             = var.project_id
  description         = "Raw e-commerce transaction events from streaming ingestion"
  deletion_protection = var.environment == "prod"

  # Time partitioning by day on timestamp field (COST OPTIMIZATION)
  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }

  # Clustering for query performance
  clustering = ["product_category", "status"]

  # Table schema matching the generator output
  schema = jsonencode([
    {
      name        = "order_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Unique order identifier"
    },
    {
      name        = "user_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "User identifier who placed the order"
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Order status (pending, processing, shipped, delivered, cancelled)"
    },
    {
      name        = "amount"
      type        = "FLOAT64"
      mode        = "REQUIRED"
      description = "Order total amount in USD"
    },
    {
      name        = "event_timestamp"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "Timestamp when the event occurred"
    },
    {
      name        = "product_category"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Primary product category of the order"
    },
    {
      name        = "ingestion_timestamp"
      type        = "TIMESTAMP"
      mode        = "NULLABLE"
      description = "Timestamp when the event was ingested into BigQuery"
    },
    {
      name        = "source"
      type        = "STRING"
      mode        = "NULLABLE"
      description = "Data source identifier (streaming, batch)"
    }
  ])

  labels = local.common_labels

  depends_on = [google_bigquery_dataset.ecommerce_dw]
}

#-------------------------------------------------------------------------------
# Pub/Sub Topic and Subscription
#-------------------------------------------------------------------------------

resource "google_pubsub_topic" "ecommerce_events" {
  name    = var.pubsub_topic_name
  project = var.project_id

  # Message retention for replay capability
  message_retention_duration = "604800s" # 7 days

  labels = local.common_labels

  depends_on = [google_project_service.required_apis]
}

resource "google_pubsub_subscription" "ecommerce_events_sub" {
  name    = var.pubsub_subscription_name
  topic   = google_pubsub_topic.ecommerce_events.id
  project = var.project_id

  # Subscription settings
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Expiration policy (never expire)
  expiration_policy {
    ttl = "" # Never expire
  }

  # Dead letter policy (optional, for Phase 2)
  # dead_letter_policy {
  #   dead_letter_topic     = google_pubsub_topic.dead_letter.id
  #   max_delivery_attempts = 5
  # }

  labels = local.common_labels

  depends_on = [google_pubsub_topic.ecommerce_events]
}

# IAM binding to allow service account to publish to topic
resource "google_pubsub_topic_iam_member" "publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.ecommerce_events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.data_pipeline_sa.email}"
}

# IAM binding to allow service account to subscribe
resource "google_pubsub_subscription_iam_member" "subscriber" {
  project      = var.project_id
  subscription = google_pubsub_subscription.ecommerce_events_sub.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.data_pipeline_sa.email}"
}
