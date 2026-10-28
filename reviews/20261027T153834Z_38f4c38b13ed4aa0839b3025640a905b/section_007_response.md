## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Low** | **CSV export includes cancelled orders** | `export_orders` (lines 0784‑0800) – the query `SELECT … FROM orders WHERE created_at >= ? AND created_at < ? …` does **not** filter on `status`. The function is documented as “CSV export lists all orders in the date range, including their status.” This matches the spec, but if a caller uses this export as a “sales report” the cancelled orders will be counted, which is contrary to the business rule *“Exclude cancelled orders from order counts and gross sales.”* |
| **Info** | **No sales‑report implementation in this section** | The user’s problem concerns the *sales report* logic, but the supplied fragment (lines 777‑902) does not contain any function that generates a sales report. Consequently we cannot confirm whether the report correctly excludes cancelled orders. |

### What the code demonstrably does
- `export_orders` writes every order that falls within the supplied date bounds to a CSV file, regardless of its `status` (`placed`, `cancelled`, `shipped`, etc.).  
- The function returns the path and row count, but it never performs any aggregation or exclusion logic.

### How that behavior could cause the reported problem
If a downstream tool or a developer mistakenly treats the CSV export as the “sales report”, the presence of cancelled orders would inflate the order count and gross‑sales totals, reproducing the symptom described by the user. However, the actual sales‑report function (which should apply the exclusion rule) is not present in the excerpt, so we cannot attribute the bug to it here.

### Assumptions / Missing evidence
- The real *sales report* generation code is located in another part of the source file (or another module).  
- The `export_orders` function is **not** the official sales‑report endpoint; the spec distinguishes CSV export from the sales report.  
- No other code in this fragment manipulates order totals after cancellation.

## Uncertainty
- Whether the application’s public API for “sales report” internally re‑uses `export_orders` (unlikely, but possible).  
- Whether there is a separate `sales_report` function that correctly filters cancelled orders; without seeing it we cannot confirm the presence or absence of the bug.

## Next checks
1. **Locate the sales‑report implementation** (e.g., a method named `sales_report`, `report_sales`, or similar). Examine its SQL query:
   - Verify that it includes a condition such as `WHERE status != 'cancelled'` (or `status = 'placed'`/`shipped`).
   - Ensure it subtracts refunds as required by the business rule.
2. **Check any code that calls `export_orders`** to see if it is mistakenly presented to users as a sales summary.
3. **Review unit tests** (if any) for the sales‑report feature to confirm they assert that cancelled orders are omitted.
4. **Confirm that order cancellation correctly updates the `status` field** in the `orders` table and that no other tables (e.g., `order_items`) retain stale “gross” values that could be summed elsewhere.  

If the sales‑report function is found to omit the `status` filter, that would be the root cause of the user’s observation. If it already filters correctly, the issue likely stems from using the CSV export (or another reporting path) instead of the dedicated sales report.