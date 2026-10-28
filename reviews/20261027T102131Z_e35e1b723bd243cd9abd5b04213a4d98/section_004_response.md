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