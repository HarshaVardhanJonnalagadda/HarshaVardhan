## Findings

| Severity | Title |
|----------|-------|
| **High** | **Sales report includes cancelled orders** |

**Location**: `ReportingService.sales` (lines 0710‑0734)  

**Relevant code**  

```python
0711: lower, upper = self.date_bounds(start, end)
0712: row = self.db.one(
0713:     "SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS gross_cents, "
0714:     "COALESCE(SUM(discount_cents), 0) AS discount_cents, "
0715:     "COALESCE(SUM(tax_cents), 0) AS tax_cents, "
0716:     "COALESCE(SUM(shipping_cents), 0) AS shipping_cents "
0717:     "FROM orders WHERE created_at >= ? AND created_at < ?",
0718:     (lower, upper),
0719: )
```

**What the code does**  
The query aggregates **all** rows in `orders` whose `created_at` timestamp falls in the requested date range. It does **not** filter on the order `status`. Consequently, orders with `status = 'cancelled'` are counted in `order_count` and their `total_cents` are summed into `gross_cents`.

**Why this violates the reported problem / business rule**  
The business rules state:

> “Sales reports … Exclude cancelled orders from order counts and gross sales.”

Because the query lacks a `status != 'cancelled'` condition, a cancelled order will still appear in the sales report, exactly the behavior the user observed (order count = 1, gross amount includes the cancelled order).

**Assumptions / missing cross‑function evidence**  
- We assume the `orders` table stores a `status` column with the literal value `'cancelled'` (the rest of the code uses that string, e.g., in `top_products` and `customer_summary`).  
- We do not have the cancellation implementation here, so we cannot confirm whether a cancelled order’s `total_cents` is set to zero or left unchanged. If it were zero, the gross total might be unaffected, but the order count would still be wrong.

## Uncertainty

- **Cancellation side‑effects**: Without seeing the `cancel` method, we cannot be certain whether a cancelled order’s monetary fields (`total_cents`, `discount_cents`, etc.) are cleared or left as‑is. If they are cleared, the gross total might be correct even though the count is wrong.  
- **Status values**: The exact string used for a cancelled order (`'cancelled'` vs `'canceled'` or another enum) is inferred from other queries but not verified in this snippet.

## Next checks

1. **Inspect the order‑cancellation implementation** – verify that it updates the `status` column to `'cancelled'` and whether it modifies monetary columns (`total_cents`, etc.).  
2. **Confirm the exact status string** used for cancelled orders across the codebase (e.g., in the `OrderService` or database schema).  
3. **Add a status filter** to the sales report query, e.g.:

   ```sql
   FROM orders
   WHERE created_at >= ? AND created_at < ?
     AND status != 'cancelled'
   ```

   and ensure the same filter is applied consistently to any other aggregate reports that should exclude cancelled orders.  

4. **Run tests** that create an order, cancel it, and generate a sales report for the same day to confirm that the order count and gross sales are now zero (or reflect only non‑cancelled orders).  

If the cancellation code already zeroes monetary fields, still add the status filter to satisfy the “exclude cancelled orders from order counts” rule.