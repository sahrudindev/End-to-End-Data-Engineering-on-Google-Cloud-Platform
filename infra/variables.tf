################################################################################
# Input Variables
# E-commerce Data Platform - Phase 1: Infrastructure
################################################################################

variable "project_id" {
  description = "The GCP project ID where resources will be created"
  type        = string

  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  description = "The default GCP region for resources"
  type        = string
  default     = "asia-southeast2" # Jakarta
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for the data warehouse"
  type        = string
  default     = "ecommerce_dw"
}

variable "bigquery_table_id" {
  description = "BigQuery table ID for raw events"
  type        = string
  default     = "raw_events"
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic name for streaming events"
  type        = string
  default     = "ecommerce-events"
}

variable "pubsub_subscription_name" {
  description = "Pub/Sub subscription name"
  type        = string
  default     = "ecommerce-events-sub"
}

variable "gcs_bucket_suffix" {
  description = "Suffix for the GCS bucket name (will be prefixed with project_id)"
  type        = string
  default     = "raw-data"
}

variable "data_retention_days" {
  description = "Number of days to retain data in GCS before archiving"
  type        = number
  default     = 90
}

# Local values for computed configurations
locals {
  # Resource naming convention: {project_id}-{environment}-{resource}
  gcs_bucket_name = "${var.project_id}-${var.environment}-${var.gcs_bucket_suffix}"

  # Common labels for all resources
  common_labels = {
    project     = "ecommerce-platform"
    environment = var.environment
    managed_by  = "terraform"
    phase       = "1"
  }
}
