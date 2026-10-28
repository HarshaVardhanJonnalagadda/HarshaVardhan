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