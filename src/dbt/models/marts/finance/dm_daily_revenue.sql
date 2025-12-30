{#
  Data Mart Model: dm_daily_revenue
  
  Purpose:
    Daily revenue aggregations by product category.
    Used for financial reporting and trend analysis.
  
  Grain: One row per (order_date, product_category)
#}

{{
  config(
    materialized = 'table',
    partition_by = {
      'field': 'order_date',
      'data_type': 'date',
      'granularity': 'day'
    },
    cluster_by = ['product_category'],
    tags = ['finance', 'metrics', 'daily']
  )
}}

with orders as (
    select * from {{ ref('fct_orders') }}
    where is_cancelled = false  -- Exclude cancelled orders from revenue
),

daily_aggregates as (
    select
        order_date,
        product_category,
        
        -- Order metrics
        count(distinct order_id) as order_count,
        count(distinct user_id) as unique_customers,
        
        -- Revenue metrics
        sum(amount_usd) as total_revenue_usd,
        avg(amount_usd) as avg_order_value_usd,
        min(amount_usd) as min_order_value_usd,
        max(amount_usd) as max_order_value_usd,
        
        -- Status breakdown
        countif(status = 'delivered') as delivered_orders,
        countif(status = 'shipped') as shipped_orders,
        countif(status = 'processing') as processing_orders,
        countif(status = 'pending') as pending_orders,
        
        -- Completion rate
        safe_divide(countif(status = 'delivered'), count(*)) as delivery_rate
        
    from orders
    group by order_date, product_category
),

with_running_totals as (
    select
        *,
        
        -- Running totals by category
        sum(total_revenue_usd) over (
            partition by product_category 
            order by order_date 
            rows unbounded preceding
        ) as cumulative_revenue_usd,
        
        -- Day-over-day change
        lag(total_revenue_usd) over (
            partition by product_category 
            order by order_date
        ) as prev_day_revenue_usd
        
    from daily_aggregates
),

final as (
    select
        -- Dimensions
        order_date,
        product_category,
        
        -- Date parts for filtering
        extract(year from order_date) as year,
        extract(month from order_date) as month,
        extract(week from order_date) as week_of_year,
        format_date('%A', order_date) as day_name,
        
        -- Order metrics
        order_count,
        unique_customers,
        
        -- Revenue
        round(total_revenue_usd, 2) as total_revenue_usd,
        round(avg_order_value_usd, 2) as avg_order_value_usd,
        round(min_order_value_usd, 2) as min_order_value_usd,
        round(max_order_value_usd, 2) as max_order_value_usd,
        round(cumulative_revenue_usd, 2) as cumulative_revenue_usd,
        
        -- Day-over-day metrics
        round(prev_day_revenue_usd, 2) as prev_day_revenue_usd,
        round(
            safe_divide(
                total_revenue_usd - prev_day_revenue_usd,
                prev_day_revenue_usd
            ) * 100, 
            2
        ) as revenue_change_pct,
        
        -- Status breakdown
        delivered_orders,
        shipped_orders,
        processing_orders,
        pending_orders,
        round(delivery_rate * 100, 2) as delivery_rate_pct,
        
        -- Metadata
        current_timestamp() as _dbt_updated_at
        
    from with_running_totals
)

select * from final
