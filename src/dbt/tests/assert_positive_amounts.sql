/*
  Singular Test: Assert Positive Amounts
  
  Purpose:
    Ensure that no orders have negative amounts.
    This is a critical data quality check for financial integrity.
  
  Test passes if: Query returns 0 rows
  Test fails if: Query returns any rows (orders with negative amounts)
*/

select
    order_id,
    user_id,
    amount_usd,
    order_date,
    'Negative amount detected' as error_message
    
from {{ ref('fct_orders') }}

where amount_usd < 0
