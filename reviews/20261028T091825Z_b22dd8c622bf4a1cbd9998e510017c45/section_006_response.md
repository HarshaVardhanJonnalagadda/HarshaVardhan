## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are included in sales totals** | `ReportingService.sales` – lines 0710‑0724. The query `SELECT … FROM orders WHERE created_at >= ? AND created_at < ?` does **not** filter out `status = 'cancelled'`. Business rules explicitly state *“Exclude cancelled orders from order counts and gross sales.”* Consequently `order_count`, `gross_cents`, `discount_cents`, `tax_cents`, `shipping_cents`, and the derived `average_order_cents` and `net_cents` can be inflated by cancelled orders. |
| **High** | **Refunds from cancelled orders are counted** | `ReportingService.sales` – lines 0720‑0725. The refund query joins `refunds r` to `orders o` but also lacks a `status != 'cancelled'` condition. If a cancelled order somehow has a refund record (or a refund is mistakenly linked), the `refunded_cents` will be subtracted from a gross that already includes the cancelled order, producing an incorrect net figure. |
| **Medium** | **`date_bounds` may allow a 367‑day inclusive range that exceeds the rule** | `ReportingService.date_bounds` – lines 0700‑0706. The rule says *“Report range must not exceed 367 days.”* The code checks `(last - first).days > 366`. For a non‑leap‑year, `first = 2023‑01‑01`, `last = 2024‑01‑01` gives a difference of **366** days, which passes the test and yields a 367‑day inclusive range (Jan 1 2023 … Jan 1 2024). This matches the rule, but the comment “must not exceed 367 days” is ambiguous; the implementation should be reviewed to confirm the intended inclusive/exclusive semantics. |
| **Low** | **`status_counts` silently drops unknown statuses** | `ReportingService.status_counts` – lines 0736‑0740. The result dict is pre‑filled with keys from `VALID_STATUSES`. If the `orders` table ever contains a status not listed there, the count for that status is omitted rather than reported as zero or flagged. This could hide data quality problems that affect stock‑related reporting (e.g., a stray “returned” status). |
| **Low** | **`export_orders` does not verify that the target path is a file, not a directory** | `ReportingService.export_orders` – lines 0784‑0799. The code only checks `path.parent.is_dir()`. If `path` itself points to an existing directory, `path.open("x")` will raise an exception, but the error message is not user‑friendly. This does not affect totals directly but could interrupt a reporting workflow. |

## Uncertainty  

| Area | Why the evidence is insufficient | What needs clarification |
|------|----------------------------------|--------------------------|
| **Definition of `total_cents`** in the `orders` table | The snippet does not show how `total_cents` is calculated when an order is created (whether it already includes discount, tax, shipping). Without that, we cannot be 100 % sure that the sales query’s omission of cancelled orders is the only problem affecting totals. | Inspect the order‑creation logic (e.g., `OrderService.place_order`) to confirm the composition of `total_cents`. |
| **Presence of a `status = 'cancelled'` row in the `refunds` join** | The refunds query joins on `orders` but we do not know whether the schema enforces that refunds can only reference non‑cancelled orders (e.g., via a foreign‑key constraint or application‑level check). | Review the refund‑creation code and any database constraints that prevent refunds on cancelled orders. |
| **Behavior of `parse_day`** | The date‑parsing helper is not shown; it could return a timezone‑aware `datetime` or a plain `date`. The string formatting with `+00:00` assumes UTC; mismatched types could cause off‑by‑one‑day errors in the report range. | Look at the implementation of `parse_day` and the storage format of `orders.created_at`. |
| **`VALID_STATUSES` definition** | We do not see the full list; it may already include all possible statuses, making the “unknown status” risk moot. | Examine the constant `VALID_STATUSES`. |

## Next checks  

1. **Order creation / total calculation** – Verify that `orders.total_cents` already reflects the full order total (subtotal − discount + tax + shipping). Ensure that cancelled orders are still stored with a total that should be ignored in reports.  

2. **Refund creation rules** – Confirm that the system prevents refunds on cancelled orders, either via application logic or a DB constraint. If such protection exists, the refund query may be safe; otherwise add `AND o.status != 'cancelled'` to the refunds SELECT.  

3. **`date_bounds` semantics** – Clarify the intended inclusive range. If the rule truly caps the *inclusive* span at 367 days, the current check is correct; otherwise adjust the comparison to `(last - first).days >= 367`.  

4. **`VALID_STATUSES` completeness** – Review the definition to ensure no legitimate status is omitted, or add a fallback to count unknown statuses for diagnostic purposes.  

5. **`parse_day` and timestamp storage** – Ensure that the ISO‑8601 strings produced by `date_bounds` match the format stored in `orders.created_at`. Mismatched timezones could cause orders to be excluded from a report unintentionally.  

6. **Export error handling** – Consider adding an explicit check that `path` is not an existing directory and provide a clearer error message.  

Addressing the high‑severity findings (excluding cancelled orders from the sales aggregates and from the refunds aggregate) will bring the reporting service in line with the business rules that directly affect totals and, indirectly, stock‑related decision‑making.