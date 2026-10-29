## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are included in sales totals** | `ReportingService.sales` (lines 0710‑0734) – the query<br>`SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS gross_cents, … FROM orders WHERE created_at >= ? AND created_at < ?` does **not** filter out orders whose `status = 'cancelled'`. The business rules state: *“Exclude cancelled orders from order counts and gross sales.”* The function later computes `net_cents = gross_cents - refunded_cents`, so the inflated `gross_cents` propagates to the reported net sales. |
| **Medium** | **Average order amount uses Python’s bankers‑rounding, not “round half up”** | `ReportingService.sales` (line 0732) – `result["average_order_cents"] = round(result["gross_cents"] / count) if count else 0`<br>Python’s built‑in `round` implements “round‑to‑even”. The specification for tax rounding (and generally for monetary values) requires *half‑up* rounding. If the average is expected to be presented with the same rounding rule, the current implementation may produce a value that is off by one cent for .5 cases. |
| **Low** | **`date_bounds` builds ISO‑8601 strings by concatenating a suffix** | `ReportingService.date_bounds` (lines 0700‑0708) – `return first.isoformat() + "T00:00:00+00:00", after.isoformat() + "T00:00:00+00:00"`<br>`first` and `after` are `date` objects; `isoformat()` yields `"YYYY‑MM‑DD"`. Concatenating the suffix works, but it relies on the caller never passing a `datetime` object. If the implementation of `parse_day` were to change to return a `datetime`, the resulting string would contain an extra time component (e.g., `"2023‑01‑01T00:00:00+00:00T00:00:00+00:00"`). This could break date filtering in all reporting queries. |
| **Low** | **`export_orders` does not validate that the requested date range is non‑empty** | `ReportingService.export_orders` (lines 0784‑0800) – after calling `date_bounds`, the function proceeds even if `start` and `end` represent the same day (resulting in an empty result set). While not a correctness error per se, the business rule for reports expects a *valid* range; an empty export may be surprising to callers. |

### Evidence status
All findings are **SUPPORTED IN SUPPLIED CODE** – the problematic statements are present in the excerpt.

## Uncertainty

| Issue | Reason |
|-------|--------|
| Definition of `VALID_STATUSES` | Not shown in this fragment; we assume it contains `'cancelled'` among other statuses, but the exact set is unknown. |
| Behaviour of helper functions (`parse_day`, `integer`, `ServiceError`) | Their implementations are outside the provided section, so we cannot confirm they enforce the required validation (e.g., date format, limit bounds). |
| Database schema for `orders.total_cents` | We assume `total_cents` already includes discount, tax, and shipping as per the business rules, but the schema is not visible here. |
| Whether refunds are ever linked to cancelled orders | The refund query joins `orders` without a status filter; if the system ever creates refunds for cancelled orders, the current logic would double‑count them. This cannot be verified without seeing the refund creation code. |

## Next checks

1. **Verify sales query filtering** – Confirm that cancelled orders must be excluded from the `sales` report and adjust the SQL to `WHERE created_at >= ? AND created_at < ? AND status != 'cancelled'`.  
2. **Confirm rounding policy for averages** – If the specification requires half‑up rounding for monetary values, replace `round(...)` with a helper that implements that rule (e.g., `Decimal(...).quantize(Decimal('1'), rounding=ROUND_HALF_UP)`).  
3. **Inspect `parse_day` implementation** – Ensure it always returns a `date` object; if it may return a `datetime`, refactor `date_bounds` to build the timestamp using `datetime.combine` instead of string concatenation.  
4. **Check `export_orders` edge cases** – Determine whether an empty result set is acceptable or if the function should raise an error when `lower == upper`.  
5. **Review refund creation flow** – Ensure refunds cannot be issued for orders whose status is `'cancelled'`, or add a status filter to the refunds query in `sales`.  
6. **Validate `VALID_STATUSES` includes all expected statuses** – Especially `'cancelled'`, to guarantee `status_counts` reports correctly.  

Addressing the high‑severity inclusion of cancelled orders will bring the sales totals in line with the business rules and prevent overstated revenue figures. The other items are lower‑severity but may affect monetary rounding consistency and robustness of date handling.