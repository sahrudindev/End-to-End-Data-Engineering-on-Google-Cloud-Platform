/*
  Singular Test: Assert Reasonable Order Dates
  
  Purpose:
    Ensure order dates are within expected range (not in future, not too old).
    Catches data quality issues like incorrect timestamp parsing.
  
  Test passes if: Query returns 0 rows
  Test fails if: Query returns any rows (orders with unreasonable dates)
*/

select
    order_id,
    order_date,
    occurred_at,
    'Invalid order date' as error_message
    
from {{ ref('fct_orders') }}

where 
    -- No future dates
    order_date > current_date()
    
    -- No dates older than 2 years
    or order_date < date_sub(current_date(), interval 2 year)
