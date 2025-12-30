# GitHub Upload Security Checklist

## Pre-Upload Verification

Run these commands before pushing to GitHub:

```powershell
# Check for sensitive files that might be committed
git status

# Verify no secrets in staged files
git diff --cached --name-only | Select-String -Pattern "\.json$|\.env$|key|secret|credential"

# Double-check .gitignore is working
git check-ignore -v .env
git check-ignore -v *.json
```

## Files That Should NEVER Be Committed

| File Pattern | Reason |
|-------------|--------|
| `.env` | Contains project IDs, API keys |
| `*.json` (GCP keys) | Service account credentials |
| `*.tfstate` | Contains sensitive infrastructure state |
| `*.tfvars` | May contain secrets |
| `*-key.json` | GCP service account keys |
| `application_default_credentials.json` | Local GCP auth |

## Files That ARE Safe to Commit

| File | Purpose |
|------|---------|
| `.env.example` | Template (no real values) |
| `.gitignore` | Security rules |
| `profiles.yml.template` | dbt config template |
| All `.tf` files | Infrastructure code |
| All Python files | Application code |

## GitHub Secrets to Configure

For CI/CD to work, add these secrets in GitHub:

1. Go to **Settings → Secrets and variables → Actions**
2. Add these secrets:

| Secret Name | Value |
|-------------|-------|
| `GCP_SA_KEY` | Contents of service account JSON key |
| `GCP_PROJECT_ID` | `dataengineergcp-482812` |

## Create Service Account Key

```powershell
# Create key for GitHub Actions
gcloud iam service-accounts keys create github-actions-key.json `
    --iam-account=github-actions-dbt@dataengineergcp-482812.iam.gserviceaccount.com

# Copy the contents to GitHub Secrets, then DELETE the file!
cat github-actions-key.json
Remove-Item github-actions-key.json
```

## Push to GitHub

```powershell
# Initialize if not already
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/dataengineerkumplit.git

# Add all files (gitignore will protect secrets)
git add .

# Verify what will be committed
git status

# Commit
git commit -m "Initial commit: End-to-end data platform on GCP"

# Push
git branch -M main
git push -u origin main
```

## Post-Upload Verification

1. Visit your GitHub repo
2. Verify NO `.env` or `.json` credential files are visible
3. Check the Actions tab - workflow should be visible but not running yet (needs secrets)

## Emergency: If You Accidentally Committed Secrets

```powershell
# Remove file from git history (DANGEROUS - rewrites history)
git filter-branch --force --index-filter `
    "git rm --cached --ignore-unmatch PATH/TO/SECRET/FILE" `
    --prune-empty --tag-name-filter cat -- --all

# Force push
git push origin --force --all

# Rotate the exposed credentials immediately!
gcloud iam service-accounts keys delete KEY_ID `
    --iam-account=SERVICE_ACCOUNT_EMAIL
```

## Security Best Practices

1. ✅ Use `.env.example` for templates
2. ✅ Never hardcode credentials in code
3. ✅ Use GitHub Secrets for CI/CD
4. ✅ Rotate keys if exposed
5. ✅ Review git diff before every commit
