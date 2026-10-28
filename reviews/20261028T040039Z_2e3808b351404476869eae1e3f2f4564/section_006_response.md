## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are counted in sales totals** | `ReportingService.sales` – lines **0712‑0719** and **0720‑0725**. The `SELECT … FROM orders` query does **not** filter `status != 'cancelled'`, so cancelled orders contribute to `order_count`, `gross_cents`, `discount_cents`, `tax_cents`, and `shipping_cents`. The business rules explicitly state *“Exclude cancelled orders from order counts and gross sales.”* |
| **Medium** | **Refunds can be created with a non‑positive amount** | `ReportingService.refund` – line **0674‑0675** only checks that the requested amount does not exceed the remaining order total. There is no validation that `amount_cents` is **> 0**. A zero or negative amount would be recorded, altering the order’s financial history and potentially inflating net totals. |
| **Medium** | **Export may overwrite an existing CSV file** | `ReportingService.export_orders` – line **0786‑0788** checks that the *parent* directory exists but never checks whether `path` already points to an existing file. The specification requires *“must not overwrite an existing file.”* |
| **Low** | **Potential refund‑ID collision** | `ReportingService.refund` – line **0676** builds `refund_id` from `payload_hash(request_id)[:12]`. If two different `request_id`s happen to produce the same 12‑character prefix, the `INSERT` will raise a DB‑level conflict (or silently overwrite depending on schema). The code does not detect or handle this case. |

### What the code demonstrably does  

* **Sales query** – pulls *all* rows from `orders` within the date window, regardless of status.  
* **Refund creation** – accepts any integer `amount_cents` (including 0 or negative) as long as it does not exceed the remaining order total.  
* **Export** – proceeds to read orders and (presumably) write them to `path` without checking if the file already exists.  
* **Refund ID** – deterministically derives a 12‑character ID from the request ID; collisions are possible but not guarded against.

### How the behavior could change totals or stock  

* Including cancelled orders inflates `gross_cents`, `order_count`, and derived metrics (average order value, tax, shipping, etc.), giving a misleading picture of revenue.  
* A zero‑ or negative‑valued refund would *increase* the reported net sales (because `net_cents = gross_cents - refunded_cents` would subtract a non‑positive number).  
* Overwriting an existing export file could cause loss of previously generated reports, making audits impossible and potentially hiding discrepancies in stock or financial data.  
* A refund‑ID collision could either abort the refund (raising an integrity error) or, if the DB silently replaces the row, double‑count a refund and distort totals.

## Uncertainty  

| Area | Why the evidence is incomplete | What is assumed |
|------|--------------------------------|-----------------|
| **Idempotency of refunds** – The code returns the existing refund when the same `request_id` is reused *and* the `order_id` and `amount_cents` match. It is unclear whether the surrounding system guarantees that `request_id` is globally unique across all orders; if not, a duplicate `request_id` for a different order would raise a `Conflict`, which may be intended. | Need to see how `payload_hash` is defined and whether `request_id` is scoped per order. |
| **Export implementation** – The snippet stops after fetching rows; the actual CSV‑writing logic is not shown. It may already contain a check for existing files. | Assume the missing part does not perform an existence check. |
| **Database schema constraints** – We do not see the table definitions (e.g., UNIQUE constraints on `refund_id`). The collision risk for refund IDs depends on those constraints. | Assume `refund_id` is a primary key, so a collision would raise an error. |
| **Negative amount handling elsewhere** – There may be higher‑level validation before calling `refund`. | Assume the service method is the sole gatekeeper for the amount. |

## Next checks  

1. **Inspect the `sales` query** – Verify whether cancelled orders should be excluded elsewhere (e.g., a view or trigger). If not, add `WHERE status != 'cancelled'` to the SELECT.  
2. **Validate refund amount** – Look for any pre‑validation of `amount_cents`. If none, add a check `if amount_cents <= 0: raise Conflict("Refund amount must be positive")`.  
3. **Review export implementation** – Locate the code that writes the CSV file after line 7890. Ensure it checks `if path.exists(): raise ServiceError("File already exists")` before opening for write.  
4. **Examine `payload_hash` and DB schema** – Confirm the length and uniqueness guarantees of `refund_id`. If collisions are possible, consider using a longer hash or a UUID.  
5. **Search for other reporting functions** – Ensure that any other reports (e.g., inventory value, top products) also respect the “exclude cancelled orders” rule where appropriate.  
6. **Run unit tests** that create cancelled orders, issue refunds of zero/negative amounts, and attempt to export to an existing file to confirm the defects manifest.  

Addressing the high‑severity sales‑totals issue first will bring the financial reports back in line with the stated business rules. The medium‑severity items should be fixed next to prevent subtle data‑integrity problems.