# CI/CD Setup Guide

This guide explains how to set up the GitHub Actions workflow for automated dbt builds.

## Prerequisites

- GitHub repository created
- GCP project with BigQuery and dbt models

## Step 1: Create Service Account

Create a service account with necessary permissions:

```powershell
# Set variables
$PROJECT_ID = "dataengineergcp-482812"
$SA_NAME = "github-actions-dbt"

# Create service account
gcloud iam service-accounts create $SA_NAME `
    --display-name="GitHub Actions dbt Runner" `
    --project=$PROJECT_ID

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" `
    --role="roles/bigquery.jobUser"

# Create and download key
gcloud iam service-accounts keys create github-actions-key.json `
    --iam-account="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

## Step 2: Add GitHub Secret

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `GCP_SA_KEY`
5. Value: Paste the entire contents of `github-actions-key.json`
6. Click **Add secret**

## Step 3: Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## Step 4: Trigger Workflow

### Manual Trigger
1. Go to **Actions** tab in GitHub
2. Select **dbt Daily Build**
3. Click **Run workflow**

### Automatic
Workflow runs daily at 07:00 UTC (14:00 WIB).

## Troubleshooting

### Authentication Error
- Verify `GCP_SA_KEY` secret contains valid JSON
- Check service account has required roles

### dbt Build Failures
- Check logs in GitHub Actions
- Verify BigQuery table exists
- Run `dbt debug` locally to test

## Security Note

⚠️ **Never commit service account keys to the repository!**

Add to `.gitignore`:
```
*-key.json
*-credentials.json
```
