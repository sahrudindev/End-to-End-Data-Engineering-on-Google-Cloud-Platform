################################################################################
# Metabase Dashboard on Cloud Run
# E-commerce Data Platform - Phase 4: Visualization
################################################################################
#
# IMPORTANT: This is a demonstration setup using Metabase's embedded H2 database.
# Data and configurations will be lost when the container restarts.
# For production, use Cloud SQL (PostgreSQL) for persistence.
#
################################################################################

#-------------------------------------------------------------------------------
# Enable Cloud Run API
#-------------------------------------------------------------------------------

resource "google_project_service" "cloud_run" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

#-------------------------------------------------------------------------------
# Cloud Run Service - Metabase (Simplified)
#-------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "metabase" {
  name     = "metabase-dashboard"
  location = var.region
  project  = var.project_id

  template {
    containers {
      image = "metabase/metabase:v0.48.0"

      ports {
        container_port = 3000
      }

      # Resource limits - more memory for Metabase
      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
        cpu_idle = true
      }

      # Environment variables
      env {
        name  = "MB_JETTY_PORT"
        value = "3000"
      }

      env {
        name  = "JAVA_TIMEZONE"
        value = "Asia/Jakarta"
      }
    }

    # Scaling configuration
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    # Timeout for cold start (Metabase needs time)
    timeout = "600s"

    # Service account
    service_account = google_service_account.data_pipeline_sa.email
  }

  # Traffic configuration
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = local.common_labels

  depends_on = [google_project_service.cloud_run]
}

#-------------------------------------------------------------------------------
# IAM - Allow Public Access (unauthenticated)
#-------------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "metabase_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.metabase.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
