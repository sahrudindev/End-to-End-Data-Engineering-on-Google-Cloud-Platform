################################################################################
# Output Values
# E-commerce Data Platform - Phase 1: Infrastructure
################################################################################

#-------------------------------------------------------------------------------
# Service Account Outputs
#-------------------------------------------------------------------------------

output "service_account_email" {
  description = "Email of the data pipeline service account"
  value       = google_service_account.data_pipeline_sa.email
}

output "service_account_name" {
  description = "Full name of the service account"
  value       = google_service_account.data_pipeline_sa.name
}

#-------------------------------------------------------------------------------
# Cloud Storage Outputs
#-------------------------------------------------------------------------------

output "gcs_bucket_name" {
  description = "Name of the raw data GCS bucket"
  value       = google_storage_bucket.raw_data.name
}

output "gcs_bucket_url" {
  description = "URL of the raw data GCS bucket"
  value       = google_storage_bucket.raw_data.url
}

output "gcs_bucket_self_link" {
  description = "Self-link of the GCS bucket"
  value       = google_storage_bucket.raw_data.self_link
}

#-------------------------------------------------------------------------------
# BigQuery Outputs
#-------------------------------------------------------------------------------

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.ecommerce_dw.dataset_id
}

output "bigquery_dataset_full_id" {
  description = "Full BigQuery dataset ID (project:dataset)"
  value       = "${var.project_id}:${google_bigquery_dataset.ecommerce_dw.dataset_id}"
}

output "bigquery_table_id" {
  description = "BigQuery table ID for raw events"
  value       = google_bigquery_table.raw_events.table_id
}

output "bigquery_table_full_id" {
  description = "Full BigQuery table ID (project.dataset.table)"
  value       = "${var.project_id}.${google_bigquery_dataset.ecommerce_dw.dataset_id}.${google_bigquery_table.raw_events.table_id}"
}

#-------------------------------------------------------------------------------
# Pub/Sub Outputs
#-------------------------------------------------------------------------------

output "pubsub_topic_name" {
  description = "Name of the Pub/Sub topic"
  value       = google_pubsub_topic.ecommerce_events.name
}

output "pubsub_topic_id" {
  description = "Full ID of the Pub/Sub topic"
  value       = google_pubsub_topic.ecommerce_events.id
}

output "pubsub_subscription_name" {
  description = "Name of the Pub/Sub subscription"
  value       = google_pubsub_subscription.ecommerce_events_sub.name
}

output "pubsub_subscription_id" {
  description = "Full ID of the Pub/Sub subscription"
  value       = google_pubsub_subscription.ecommerce_events_sub.id
}

#-------------------------------------------------------------------------------
# Convenience Outputs for Phase 2
#-------------------------------------------------------------------------------

output "generator_env_vars" {
  description = "Environment variables for the data generator"
  value = {
    GOOGLE_CLOUD_PROJECT = var.project_id
    PUBSUB_TOPIC         = google_pubsub_topic.ecommerce_events.name
    GCS_BUCKET           = google_storage_bucket.raw_data.name
    BIGQUERY_DATASET     = google_bigquery_dataset.ecommerce_dw.dataset_id
    BIGQUERY_TABLE       = google_bigquery_table.raw_events.table_id
  }
}

#-------------------------------------------------------------------------------
# Cloud Run / Metabase Outputs (Phase 4)
#-------------------------------------------------------------------------------

output "metabase_url" {
  description = "URL for Metabase dashboard"
  value       = google_cloud_run_v2_service.metabase.uri
}

output "metabase_service_name" {
  description = "Cloud Run service name for Metabase"
  value       = google_cloud_run_v2_service.metabase.name
}
