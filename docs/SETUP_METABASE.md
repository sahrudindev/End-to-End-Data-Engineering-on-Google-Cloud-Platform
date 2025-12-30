# Metabase Setup Guide

This guide explains how to access and configure Metabase after deployment.

## Deployment

Deploy Metabase with Terraform:

```powershell
cd infra
terraform apply -var="project_id=dataengineergcp-482812"
```

Get the Metabase URL:

```powershell
terraform output metabase_url
```

## First-Time Setup

1. Open the Metabase URL in your browser
2. Wait 1-2 minutes for Metabase to initialize
3. Complete the setup wizard:
   - Create admin account
   - Skip adding data for now

## Connect to BigQuery

1. Go to **Admin** → **Databases** → **Add database**
2. Select **BigQuery**
3. Configure:
   - **Display name**: E-commerce DW
   - **Project ID**: `dataengineergcp-482812`
   - **Dataset ID**: `ecommerce_dw`
   - **Service account JSON**: Upload the key file
4. Click **Save**

## Recommended Dashboards

### Daily Revenue Dashboard
- **Chart 1**: Revenue by Day (line chart from `dm_daily_revenue`)
- **Chart 2**: Revenue by Category (pie chart)
- **Chart 3**: Top Products (bar chart)

### Customer Analytics
- **Chart 1**: Customer Tier Distribution (from `dim_users`)
- **Chart 2**: Activity Status (active/at_risk/churned)

## ⚠️ Important Limitations

This demo deployment uses Metabase's embedded H2 database:
- **Data is ephemeral** - lost when container restarts
- **Not for production** - use Cloud SQL for persistence

## Stopping Metabase

To stop and remove:

```powershell
terraform destroy -target=google_cloud_run_v2_service.metabase
```

## Production Setup

For production, add Cloud SQL PostgreSQL:

```terraform
resource "google_sql_database_instance" "metabase_db" {
  name             = "metabase-db"
  database_version = "POSTGRES_15"
  ...
}
```
