################################################################################
# Terraform Configuration & Provider Setup
# E-commerce Data Platform - Phase 1: Infrastructure
################################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Remote state backend configuration
  # Uncomment and configure after creating the state bucket manually
  # backend "gcs" {
  #   bucket  = "YOUR_PROJECT_ID-tfstate"
  #   prefix  = "ecommerce-platform/state"
  # }
}

# Primary GCP Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Beta Provider for preview features
provider "google-beta" {
  project = var.project_id
  region  = var.region
}
