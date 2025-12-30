{#
  Staging Model: stg_ecommerce__events
  
  Purpose:
    Clean and standardize raw event data from the source table.
    This is a 1:1 transformation layer that handles:
    - Type casting
    - Column renaming for consistency
    - Derived columns for downstream use
  
  Materialization: View (always fresh, no storage cost)
#}

with source as (
    select * from {{ source('ecommerce_raw', 'raw_events') }}
),

cleaned as (
    select
        -- Primary key
        order_id,
        
        -- Foreign keys
        user_id,
        
        -- Attributes
        status,
        product_category,
        source as data_source,
        
        -- Measures (cast to ensure correct types)
        cast(amount as float64) as amount_usd,
        
        -- Timestamps (rename for clarity)
        event_timestamp as occurred_at,
        ingestion_timestamp as ingested_at,
        
        -- Derived columns
        date(event_timestamp) as order_date,
        extract(hour from event_timestamp) as order_hour,
        extract(dayofweek from event_timestamp) as order_day_of_week,
        
        -- Status flags
        case 
            when status = 'delivered' then true
            when status = 'cancelled' then false
            else null
        end as is_completed,
        
        case
            when status = 'cancelled' then true
            else false
        end as is_cancelled,
        
        -- Metadata
        current_timestamp() as _dbt_loaded_at
        
    from source
    
    -- Filter out any completely null rows (data quality)
    where order_id is not null
)

select * from cleaned
