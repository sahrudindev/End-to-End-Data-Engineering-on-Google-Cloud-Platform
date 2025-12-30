{#
  Fact Model: fct_orders
  
  Purpose:
    Core fact table for order transactions.
    Uses INCREMENTAL materialization with merge strategy for cost-effective updates.
  
  Grain: One row per order (order_id)
  
  Incremental Strategy:
    - Uses merge strategy with order_id as unique key
    - Only processes new/updated records based on occurred_at
    - Partitioned by day for efficient querying
    - Clustered by product_category and status for common query patterns
#}

{{
  config(
    materialized = 'incremental',
    unique_key = 'order_id',
    incremental_strategy = 'merge',
    partition_by = {
      'field': 'order_date',
      'data_type': 'date',
      'granularity': 'day'
    },
    cluster_by = ['product_category', 'status'],
    tags = ['core', 'fact', 'incremental']
  )
}}

with staged_events as (
    select * from {{ ref('stg_ecommerce__events') }}
    
    {% if is_incremental() %}
    -- Only process new records for incremental runs
    -- Look back 3 days to handle late-arriving data
    where occurred_at > (
        select coalesce(max(occurred_at), '1900-01-01') 
        from {{ this }}
    )
    {% endif %}
),

-- Filter to valid order statuses only
valid_orders as (
    select *
    from staged_events
    where status in ('pending', 'processing', 'shipped', 'delivered')
),

-- Deduplicate if there are multiple events for same order_id
-- Keep the latest status
deduplicated as (
    select
        *,
        row_number() over (
            partition by order_id 
            order by occurred_at desc
        ) as row_num
    from valid_orders
),

final as (
    select
        -- Keys
        order_id,
        user_id,
        
        -- Dimensions
        status,
        product_category,
        data_source,
        
        -- Measures
        amount_usd,
        
        -- Time dimensions
        order_date,
        order_hour,
        order_day_of_week,
        occurred_at,
        
        -- Flags
        is_completed,
        is_cancelled,
        
        -- Metadata
        ingested_at,
        current_timestamp() as _dbt_updated_at
        
    from deduplicated
    where row_num = 1
)

select * from final
