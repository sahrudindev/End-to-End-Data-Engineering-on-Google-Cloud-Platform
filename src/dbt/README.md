# E-commerce Data Warehouse - dbt Project

Production-grade dbt project for transforming raw e-commerce data into business-ready models.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         dbt Layers                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌────────────────┐    ┌────────────────┐  │
│  │   Sources    │───▶│    Staging     │───▶│     Marts      │  │
│  │  (raw_events)│    │ (stg_events)   │    │ (fct_/dim_/dm_)│  │
│  └──────────────┘    └────────────────┘    └────────────────┘  │
│                                                                 │
│  Materialization:    View                  Table/Incremental   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
src/dbt/
├── dbt_project.yml           # Project configuration
├── profiles.yml.template     # BigQuery connection template
├── packages.yml              # dbt packages
├── models/
│   ├── staging/              # 1:1 source cleaning
│   │   ├── src_ecommerce.yml
│   │   ├── stg_ecommerce__events.sql
│   │   └── stg_ecommerce.yml
│   └── marts/
│       ├── core/             # Core business entities
│       │   ├── fct_orders.sql (INCREMENTAL)
│       │   ├── dim_users.sql
│       │   └── core.yml
│       └── finance/          # Financial metrics
│           ├── dm_daily_revenue.sql
│           └── finance.yml
├── tests/                    # Singular tests
│   ├── assert_positive_amounts.sql
│   └── assert_reasonable_order_dates.sql
├── macros/                   # Custom macros
│   └── generate_schema_name.sql
├── seeds/                    # Static reference data
└── snapshots/                # SCD Type 2 tracking
```

## 🚀 Quick Start

### 1. Install dbt

```bash
pip install dbt-bigquery
```

### 2. Configure Profile

```bash
# Copy template to dbt profiles directory
# Windows:
copy profiles.yml.template %USERPROFILE%\.dbt\profiles.yml

# Linux/Mac:
cp profiles.yml.template ~/.dbt/profiles.yml

# Edit and update project ID
```

### 3. Install Dependencies

```bash
cd src/dbt
dbt deps
```

### 4. Validate Setup

```bash
# Check connection
dbt debug

# Compile models (without running)
dbt compile
```

### 5. Run Models

```bash
# Run all models
dbt run

# Run specific model
dbt run --select fct_orders

# Run with dependencies
dbt run --select +dm_daily_revenue

# Full refresh (ignore incremental logic)
dbt run --full-refresh --select fct_orders
```

### 6. Run Tests

```bash
# Run all tests
dbt test

# Run tests for specific model
dbt test --select fct_orders

# Run only singular tests
dbt test --select test_type:singular
```

### 7. Generate Documentation

```bash
# Generate docs
dbt docs generate

# Serve locally (opens browser)
dbt docs serve --port 8081
```

## 📊 Models

### Staging Layer

| Model | Type | Description |
|-------|------|-------------|
| `stg_ecommerce__events` | View | Cleaned raw events with type casting |

### Core Marts

| Model | Type | Description |
|-------|------|-------------|
| `fct_orders` | Incremental | Order fact table (partitioned by date) |
| `dim_users` | Table | User dimension with lifetime metrics |

### Finance Marts

| Model | Type | Description |
|-------|------|-------------|
| `dm_daily_revenue` | Table | Daily revenue by category |

## 🧪 Data Quality Tests

| Test | Type | Description |
|------|------|-------------|
| `unique` | Generic | Ensures no duplicate keys |
| `not_null` | Generic | Ensures required fields exist |
| `accepted_values` | Generic | Validates enum values |
| `assert_positive_amounts` | Singular | No negative order amounts |
| `assert_reasonable_order_dates` | Singular | Dates within valid range |

## ⚡ Incremental Strategy

The `fct_orders` model uses:
- **Strategy**: `merge` (upsert based on unique key)
- **Unique Key**: `order_id`
- **Partition**: `order_date` (day granularity)
- **Cluster**: `product_category`, `status`

This ensures:
- Cost-effective updates (only new data processed)
- Efficient queries (partition pruning)
- Deduplication (merge handles duplicates)

## 🔧 Commands Cheat Sheet

```bash
# Development
dbt run                          # Run all models
dbt run --select staging         # Run only staging models
dbt run --select +fct_orders     # Run fct_orders and all upstream

# Testing
dbt test                         # Run all tests
dbt test --select fct_orders     # Test specific model
dbt source freshness             # Check source freshness

# Documentation
dbt docs generate                # Build docs
dbt docs serve                   # View in browser

# Maintenance
dbt clean                        # Remove target/dbt_packages
dbt deps                         # Install packages
dbt debug                        # Check connection

# Production
dbt run --target prod            # Run against prod
dbt run --full-refresh           # Rebuild incremental tables
```
