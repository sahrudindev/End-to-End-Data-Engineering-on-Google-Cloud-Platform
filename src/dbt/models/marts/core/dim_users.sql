{#
  Dimension Model: dim_users
  
  Purpose:
    User dimension table with aggregated metrics.
    Provides a single view of each user with their ordering behavior.
  
  Grain: One row per user (user_id)
#}

{{
  config(
    materialized = 'table',
    tags = ['core', 'dimension']
  )
}}

with orders as (
    select * from {{ ref('fct_orders') }}
),

user_metrics as (
    select
        user_id,
        
        -- Order counts
        count(distinct order_id) as total_orders,
        countif(is_completed = true) as completed_orders,
        countif(is_cancelled = true) as cancelled_orders,
        
        -- Revenue metrics
        sum(amount_usd) as lifetime_value_usd,
        avg(amount_usd) as avg_order_value_usd,
        max(amount_usd) as max_order_value_usd,
        min(amount_usd) as min_order_value_usd,
        
        -- Time metrics
        min(occurred_at) as first_order_at,
        max(occurred_at) as last_order_at,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        
        -- Recency
        date_diff(current_date(), max(order_date), day) as days_since_last_order,
        
        -- Favorite category (most ordered)
        approx_top_count(product_category, 1)[offset(0)].value as favorite_category
        
    from orders
    group by user_id
),

final as (
    select
        -- Primary key
        user_id,
        
        -- Order metrics
        total_orders,
        completed_orders,
        cancelled_orders,
        
        -- Derived metrics
        round(safe_divide(completed_orders, total_orders) * 100, 2) as completion_rate_pct,
        
        -- Revenue
        round(lifetime_value_usd, 2) as lifetime_value_usd,
        round(avg_order_value_usd, 2) as avg_order_value_usd,
        round(max_order_value_usd, 2) as max_order_value_usd,
        round(min_order_value_usd, 2) as min_order_value_usd,
        
        -- Time dimensions
        first_order_at,
        last_order_at,
        first_order_date,
        last_order_date,
        days_since_last_order,
        
        -- Segmentation
        favorite_category,
        
        -- Customer tier based on lifetime value
        case
            when lifetime_value_usd >= 1000 then 'platinum'
            when lifetime_value_usd >= 500 then 'gold'
            when lifetime_value_usd >= 100 then 'silver'
            else 'bronze'
        end as customer_tier,
        
        -- Activity status
        case
            when days_since_last_order <= 30 then 'active'
            when days_since_last_order <= 90 then 'at_risk'
            else 'churned'
        end as activity_status,
        
        -- Metadata
        current_timestamp() as _dbt_updated_at
        
    from user_metrics
)

select * from final
