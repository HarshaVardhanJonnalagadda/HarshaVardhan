# Section review results

Run outcome: failed

These are separate model reviews of source sections. They are not a consolidated assessment. Cross-section behavior may be unresolved and duplicate findings may appear. Human validation is pending.

# Section 1: original lines 1-188

## Findings
**No supported defect found in the supplied section**

The code fragment you provided (lines 1‑188) contains:

* module‑level constants, utility functions, and data‑class definitions (`Customer`, `Product`, `CartLine`, `CheckoutRequest`).
* Validation helpers for timestamps, money, percentages, JSON payloads, etc.
* No implementation of order creation, cancellation, or sales‑report generation.

Because the logic that decides whether a cancelled order is counted in a sales report is **not present** in this excerpt, we cannot demonstrate that the implementation violates the business rule:

> *“Sales reports … Exclude cancelled orders from order counts and gross sales.”*

Therefore no concrete defect can be identified from the current evidence.

## Uncertainty
* **Cancellation handling** – We need to see the code that updates an order’s `status` to `"cancelled"` and any related stock‑restoration logic.
* **Report generation** – The SQL query (or Python aggregation) that builds the sales report must filter out rows where `status = 'cancelled'`. Without that code we cannot confirm whether the filter is missing or incorrectly implemented.
* **Idempotency of cancellation** – The business rule requires that repeating a cancellation must not add stock again. The implementation of that safeguard is not visible here.
* **Order‑status constants usage** – Although `VALID_STATUSES` is defined, we have not observed where it is applied; the report may be using a different column or value.

## Next checks
1. **Order model / table schema** – Locate the `orders` table definition and the column that stores the order status.
2. **Cancellation command** – Review the function that processes `order_service.py cancel …`. Verify:
   * It sets `status = 'cancelled'`.
   * It does **not** delete the order row (so the report can see it).
   * It restores reserved stock only once.
3. **Sales‑report command** – Inspect the implementation of the `report` sub‑command (likely in a function called `run_report` or similar). Confirm that:
   * The query filters `WHERE status != 'cancelled'` (or `status = 'placed'`/`'shipped'`).
   * Gross sales are summed from the appropriate columns (order total) **after** the filter.
   * Refunds are subtracted only for the included (non‑cancelled) orders.
4. **Unit tests / fixtures** – If test files exist, check whether they cover the scenario “place → cancel → report” and whether they assert the correct totals.
5. **Edge‑case handling** – Ensure that a cancelled order that was never shipped does not affect coupon usage counts, as required by the business rules (may affect later report calculations).

Once the above sections are examined, we can determine whether the sales report incorrectly includes cancelled orders and, if so, pinpoint the exact line(s) that need correction.

---

# Section 2: original lines 174-342

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Info** | No evidence in this section that cancelled orders are excluded from sales reports | The supplied code only defines data‑classes (`CheckoutRequest`, `PricedLine`, `Quote`) and the SQLite schema (tables `orders`, `order_lines`, etc.). The **sales‑report** generation logic is not present, nor is the **cancellation** routine that would change `orders.status` from `'placed'` to `'cancelled'`. |
| **Info** | `orders.status` column is defined with a `CHECK` constraint but there is no default value | `orders` table (lines 0268‑0270): `status TEXT NOT NULL CHECK(status IN ('placed', 'shipped', 'cancelled'))`. If the cancellation code forgets to update this column, the row will stay `'placed'`. The schema itself does not enforce the “exclude cancelled” rule – that must be done by the query that builds the report. |
| **Info** | No index on `orders.status`, which could make a “exclude cancelled” filter slower on large data sets | The only indexes created are on `customer_id`, `created_at`, `sku`, and `order_id` for refunds. Absence of an index on `status` is not a functional bug, but it is a performance consideration for the report query. |

**What the supplied code demonstrably does**  
- Parses a checkout request, validates fields, and creates immutable data objects.  
- Declares the database schema, including a `status` column for orders.  
- Provides a `Database.initialize()` method that creates the tables and checks a (missing) `metadata` entry for schema version.

**How that behavior could cause the reported problem**  
- If the *cancellation* implementation fails to set `orders.status = 'cancelled'`, the order will remain `'placed'`. A sales‑report query that simply filters on `created_at` (as the business rule requires) but does **not** filter out rows where `status = 'cancelled'` would count the order and its total amount, reproducing the symptom the user sees.  
- The schema alone does not prevent this; the bug would be in the cancellation routine or the report‑generation query, which are not part of the provided excerpt.

**Assumptions / Missing Cross‑Function Evidence**  
- The actual **cancellation** function (which should update `orders.status` and possibly `updated_at`) is not shown.  
- The **sales‑report** implementation (SQL query or Python aggregation) is not included, so we cannot verify whether it correctly excludes cancelled orders.  
- The `one()` helper used in `Database.initialize()` is referenced but not defined in this snippet; its behavior could affect schema‑version handling but is unrelated to the report issue.

## Uncertainty  

- Whether the cancellation code correctly updates `orders.status`.  
- Whether the sales‑report query includes a `WHERE status <> 'cancelled'` clause as required by the business rules.  
- Whether any triggers or view definitions (outside this section) automatically filter cancelled orders.  

## Next checks  

1. **Cancellation logic** – locate the function that processes an order cancellation. Verify that it:  
   - Updates `orders.status` to `'cancelled'`.  
   - Updates `orders.updated_at`.  
   - Does **not** create duplicate inventory‑restock events on repeated cancellations.  

2. **Sales‑report generation** – find the code that builds the daily sales report. Confirm that the query:  
   - Filters on `created_at` (inclusive start/end dates, UTC).  
   - Excludes rows where `status = 'cancelled'`.  
   - Subtracts any refunds linked to the included orders.  

3. **Tests / Audits** – look for unit or integration tests that cover:  
   - Placing an order, cancelling it, then running a sales report for that day.  
   - Re‑cancelling the same order (idempotency).  

4. **Database helpers** – inspect the implementation of `Database.one()` and any other query‑building utilities to ensure they correctly bind parameters and do not inadvertently ignore the `status` filter.  

If those sections behave as intended, the reported discrepancy must stem from elsewhere (e.g., a stale cache, an out‑of‑date CSV export, or a client‑side display bug). Otherwise, the defects identified above are the likely root causes.

---

# Section 3: original lines 328-466

## Findings
**None found in the supplied section.**  
The code fragment you provided (lines 328‑466) contains only low‑level database utilities and the `CatalogService` (price updates, activation, restocking, inventory history). It does **not** include any of the following pieces that are required to explain why a cancelled order still appears in a sales report:

* the data model for an order’s status (e.g., a `status` column in the `orders` table)  
* the implementation of the *order‑cancellation* operation (how the status is changed, whether inventory is restocked, etc.)  
* the sales‑report generation logic (the SQL query that selects orders for a given date range and is supposed to exclude cancelled orders)

Because none of those components are present in the excerpt, there is no concrete evidence of a defect that would cause the reported problem.

## Uncertainty
* **Order‑cancellation implementation** – We need to see the function that marks an order as cancelled. Does it update a `status` field, delete the row, or merely create a separate “cancellation” record? If the status is not persisted or is set to a value the report does not recognise as “cancelled”, the report could mistakenly count the order.
* **Sales‑report query** – The report is supposed to “Exclude cancelled orders from order counts and gross sales”. The SQL used for the report must filter on the appropriate status flag (e.g., `WHERE status != 'cancelled'`). If the query omits that filter, cancelled orders will be included.
* **Database schema** – The `orders` table definition (not shown) may lack a `status` column or may use a different naming convention (e.g., `is_cancelled` boolean). Mismatch between the cancellation code and the report query could cause the bug.
* **Audit / idempotency** – The cancellation operation should be idempotent (re‑cancelling must not restock again). If the implementation mistakenly creates duplicate cancellation events, the report might double‑count or fail to recognise the cancellation.

## Next checks
1. **Locate the order‑cancellation service** (likely a method such as `OrderService.cancel(order_id, ...)`). Verify:
   * Which column(s) are updated to indicate cancellation.
   * That the update occurs inside a `transaction` block.
   * That the operation is idempotent (re‑cancelling does not alter state again).

2. **Inspect the `orders` table schema** (look for the `SCHEMA` constant or the `CREATE TABLE orders …` statement). Confirm the existence and data type of the field used to represent cancellation.

3. **Find the sales‑report generation code** (e.g., a method `ReportService.sales_report(start, end)` or similar). Examine the SQL query:
   * Ensure it filters out cancelled orders (`WHERE status != 'cancelled'` or `WHERE is_cancelled = 0`).
   * Verify that it uses the order **creation** date (as required) and not the cancellation date.

4. **Check any view or materialised table** that the report might read from. If a denormalised view is built elsewhere, confirm it is refreshed after cancellations.

5. **Run a mental test** (no execution) with a sample order:
   * Create an order → status = `placed`.
   * Cancel the order → status should become `cancelled`.
   * Generate a sales report for the order’s creation date → the query must exclude rows where status = `cancelled`.

If any of the above steps reveal a mismatch (e.g., status not updated, report not filtering), that would explain why the cancelled order still appears in the report. Otherwise, the bug lies outside the currently provided code.

---

# Section 4: original lines 452-588

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Incorrect subtotal calculation** | `PricingService.quote` – lines 0522‑0524:<br>`subtotal = sum(line.unit_price_cents for line in lines)`<br>The code sums *unit* prices only, ignoring the quantity of each line. The correct subtotal should be the sum of `line.line_total_cents` (price × quantity). |
| **Low** | **Free‑shipping condition uses pre‑discount subtotal** | `PricingService.shipping_cost` – lines 0511‑0516:<br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`<br>Business rules state free shipping when *merchandise **after discount*** is ≥ 10 000 cents. The function checks the raw subtotal, not `subtotal - discount`. |
| **Low** | **Potential status‑spelling mismatch for cancelled orders** | `PricingService.coupon_discount` – line 0505:<br>`WHERE coupon = ? AND status != 'cancelled'`<br>If any other part of the code (not shown) stores the status as `"canceled"` (American spelling) the query will treat cancelled orders as *not* cancelled, causing them to be counted in reports and coupon‑use limits. |

### What the code demonstrably does
* **Subtotal** – The quote returned to the caller contains a `subtotal_cents` that is too low (it equals the sum of unit prices). All downstream calculations (discount eligibility, free‑shipping check, total amount) are based on this incorrect value.
* **Shipping cost** – Free standard shipping is granted based on the raw subtotal, not the discounted merchandise amount, violating the rule that the discount‑adjusted subtotal determines free shipping.
* **Coupon usage** – The usage count deliberately excludes rows whose `status` equals `'cancelled'`. If the stored status string differs, cancelled orders will be counted as used, and later report logic that also checks `status != 'cancelled'` could mistakenly include them.

### How the behavior could cause the reported problem
* An order that is later cancelled may have been **inserted with an incorrect total** (because of the subtotal bug). When the sales report aggregates gross sales, it uses the stored `total_cents` from the order row. If the cancellation routine does not overwrite or delete that total, the report will still show the (incorrect) amount.
* If the cancellation routine marks the order with a status string that does **not** match `'cancelled'`, the report’s filter (`status != 'cancelled'`) will treat the order as active, causing it to be counted.
* The free‑shipping bug does not directly affect cancellation, but it demonstrates a pattern where business‑rule checks are implemented incorrectly, raising the possibility that the *sales‑report* filter itself may be mis‑implemented elsewhere.

## Uncertainty
* The **cancellation implementation** and the **sales‑report generation** code are not present in this excerpt. We cannot confirm whether the status string used for cancelled orders matches the literal `'cancelled'` expected by the report query.
* It is unknown whether the `orders` table stores a separate column (e.g., `is_cancelled`) that the report uses instead of the `status` field.
* The exact query that the sales report runs is not shown; it may have its own bugs unrelated to the snippets examined.

## Next checks
1. **Inspect the cancellation flow** (`OrderService.cancel` or equivalent). Verify:
   * The status value written to the `orders` table on cancellation (spelling, case).
   * That the total amount is not left unchanged or that a separate “gross_sales” column is not left untouched.
2. **Review the sales‑report implementation**:
   * Confirm the `WHERE` clause filters on `status = 'cancelled'` (or the correct column).
   * Ensure it subtracts refunds *after* the cancellation filter.
3. **Search for any other places that compute order subtotals or totals** (e.g., after refunds, after shipping changes) to see if they also use the faulty `subtotal` calculation.
4. **Run a data‑integrity test**:
   * Create an order, cancel it, then query the `orders` table directly to see the stored `status` and `total_cents`.
   * Compare the result of the sales‑report query with a manual aggregation that excludes cancelled rows.
5. **Check for spelling inconsistencies** of the cancelled status across the codebase (`'cancelled'` vs `'canceled'`). Adjust queries or constants to use a single canonical value.

---

# Section 5: original lines 574-681

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Repeated cancellation restocks inventory** | `cancel` method, lines **0628‑0634**:<br>`self.db.execute("UPDATE products SET stock = stock + ?, …")` is executed for **every** call to `cancel`, regardless of the order’s current status. The method only checks that the order is not *shipped*; it does **not** verify that the order is already *cancelled* before adding stock back. |
| **Low / Potential** | **Sales report may include cancelled orders** | No code for the sales‑report generation is present in the supplied section. The business rule states *“Exclude cancelled orders from order counts and gross sales.”* The `cancel` method does set `status = 'cancelled'` (line 0634‑0635), but we have no evidence that the report query filters on `status`. If the report simply sums `total_cents` from the `orders` table without a `WHERE status <> 'cancelled'`, cancelled orders will be counted, which matches the symptom reported by the user. |

### What the supplied code demonstrably does
* **`checkout`** – creates an order with `status = 'placed'` and reserves stock.  
* **`cancel`** –  
  * Validates a non‑empty reason.  
  * Throws a `Conflict` if the order is already shipped.  
  * **Adds back** the ordered quantity to product stock for **every** call (lines 0629‑0632).  
  * Updates the order’s `status` to `'cancelled'`.  
  * Audits the cancellation.  
* **`ship`** – marks an order as `'shipped'`.  
* **`refund`** – creates a refund record only for shipped orders.

### How the behavior could cause the reported problem
* The **cancel** routine correctly flips the order’s status, which *should* make the order invisible to a correctly‑implemented sales report.  
* Because the **sales‑report code is not shown**, we cannot confirm that it respects the `status` column. If it merely aggregates `total_cents` from `orders` (or from a view that does not filter out `'cancelled'` rows), the cancelled order will still contribute to the gross sales figure, reproducing the user’s observation.

### Assumptions / Missing Cross‑Function Evidence
* The sales‑report implementation is elsewhere; we have no visibility into its SQL or business‑logic.  
* We assume the `orders` table is the source of truth for the report, as implied by the business rule.  
* No evidence that the `cancel` method is guarded against being called multiple times; the idempotency requirement (“Repeating cancellation must not add stock again”) is not satisfied.

## Uncertainty
* **Exact query used for the sales report** – without the report‑generation code we cannot definitively say whether cancelled orders are being filtered out.  
* **Whether other parts of the system (e.g., a view or a materialised table) automatically exclude cancelled orders** – this could mitigate the issue even if the report code itself does not filter.

## Next checks
1. **Inspect the sales‑report generation function** (likely in a `reports.py` or similar module). Look for:
   * SQL that selects from `orders` and whether it includes `WHERE status <> 'cancelled'`.
   * Any joins with `refunds` that correctly subtract refunds.
2. **Verify idempotency of `cancel`**:
   * Search for any guard that prevents a second cancellation (e.g., a check `if order["status"] == "cancelled": return …`).
   * If absent, add a status check before restocking to satisfy the rule “Repeating cancellation must not add stock again.”
3. **Check audit logs** to see if a second cancellation is recorded; this may reveal hidden logic elsewhere.
4. **Run a unit test** that:
   * Places an order, cancels it, runs the sales report, and asserts that the order count and gross sales exclude the cancelled order.
   * Calls `cancel` twice on the same order and asserts that product stock is only restored once.  

If the report code already filters cancelled orders, the user’s symptom may stem from stale cached data or an out‑of‑date materialised view; those components should also be examined.

---

# Section 6: original lines 667-791

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

---

# Section 7: original lines 777-902

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

---

# Section 8: original lines 888-1019

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Info** | **CLI dispatch forwards “cancel” and “report” commands correctly** | `dispatch` (lines 998‑1019). The function calls `orders.cancel(...)` for the *cancel* command and `reports.sales(...)` for the *report* command. No transformation of arguments is performed that could hide a cancelled order. |
| **Info** | **`write_invoice` does not filter out cancelled orders** | `write_invoice` (lines 0950‑0978). The function simply reads an order via `OrderService(db).view(order_id)` and writes its fields to a file. It does **not** attempt to exclude cancelled orders – but this is expected because an invoice is requested for a specific order, not a sales‑report aggregation. |
| **Possible** | **Cancelled‑order status may not be persisted or may use a non‑standard value** | Not present in this excerpt. The `orders.cancel` call (line 1000) is the only place we see cancellation being triggered. Whether the `OrderService.cancel` method updates the order’s `status` field to the value that `ReportingService.sales` expects (e.g., `"cancelled"`), is unknown from the supplied code. If the status is left unchanged or set to a value not recognized by the report, the cancelled order could still be counted. |
| **Possible** | **`ReportingService.sales` may not filter by order status** | The call `reports.sales(args.start, args.end)` (line 1019) passes raw start/end strings to the reporting service. The implementation of `ReportingService.sales` is not shown, so we cannot confirm that it excludes orders whose status is cancelled, as required by the business rule: “Exclude cancelled orders from order counts and gross sales.” |

### Summary of what the supplied code demonstrably does  

* The CLI parser builds sub‑commands and passes arguments unchanged to the appropriate service methods.  
* `write_invoice` creates a text invoice for a **single** order, regardless of its status.  
* The `dispatch` function correctly routes the *cancel* and *report* commands to `OrderService.cancel` and `ReportingService.sales` respectively, but the internal behavior of those methods is not visible in this section.

### How the observed behavior could cause the reported problem  

* If `OrderService.cancel` does **not** mark the order with a status that the reporting service recognises as “cancelled”, the sales report may still count the order.  
* If `ReportingService.sales` does **not** filter out orders whose status is cancelled (or checks a different field), cancelled orders will appear in the report, matching the user’s symptom.  

Both possibilities stem from code that is **outside** the provided excerpt.

## Uncertainty  

* **Cancellation implementation** – We have no visibility into `OrderService.cancel`. Does it:  
  * Update a `status` column to a canonical value (e.g., `"cancelled"`)?  
  * Record a cancellation event without changing the order’s status?  
  * Prevent double‑cancellation and restock inventory?  

* **Sales‑report implementation** – The body of `ReportingService.sales` is missing. We cannot verify:  
  * That it parses the `start`/`end` arguments into UTC dates correctly.  
  * That it filters orders by `status != "cancelled"` (or the appropriate enum).  
  * That it subtracts refunds **after** excluding cancelled orders, as required.  

* **Order status representation** – The exact string or enum used for a cancelled order is unknown. If the reporting service expects a different token than the cancellation routine sets, the filter will fail.

## Next checks  

1. **`OrderService.cancel` implementation** – Look at the method that handles cancellation:  
   * Does it set a `status` field?  
   * What exact value is stored for a cancelled order?  
   * Does it guard against double‑cancellation and restocking?  

2. **`Order` data model** – Inspect the schema or dictionary keys for order status. Confirm the canonical value for a cancelled order.  

3. **`ReportingService.sales` implementation** – Verify that:  
   * The method parses `start`/`end` as UTC dates.  
   * It queries orders created within the range **and** filters out any order whose status equals the cancelled value identified in step 1.  
   * It correctly subtracts refunds after the cancellation filter.  

4. **Integration test** – After reviewing the two methods above, run a scenario (order → cancel → sales report) to see whether the cancelled order is omitted. This will confirm whether the bug lies in cancellation, reporting, or both.  

If those components behave as the business rules dictate, the issue may be elsewhere (e.g., a caching layer, stale data, or a CLI‑side date‑parsing bug). Otherwise, the defect will likely be in one of the two inspected methods.