## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancel is not idempotent – repeated cancellations restock inventory** | `cancel` (lines 0622‑0637) – the loop `for line in self.db.lines(order_id): … self.db.execute("UPDATE products SET stock = stock + ?, …")` runs **every** time `cancel` is called, even when the order is already in status *cancelled*. The only guard is `if order["status"] == "shipped": raise Conflict`, so a second call on a cancelled order will add the same quantities back to `products.stock` and write another audit entry. |
| **Medium** | **Missing guard against cancelling an already‑cancelled order** | Same function as above – after the first cancellation the order status is set to `'cancelled'` (line 0634). A subsequent call finds `order["status"] == "cancelled"` (which is *not* `"shipped"`), so it proceeds to restock again. |
| **Low** | **Potential double‑stock adjustment if the same SKU appears on multiple order lines** | `_reserve_line` (lines 0612‑0619) decrements stock per line, while `cancel` adds back per line (lines 0629‑0633). If earlier code does not collapse duplicate SKUs into a single line (business rule says it should), the net stock change is still correct, but the *idempotency* problem above could cause the same quantity to be added back multiple times. |
| **Low** | **`_insert_order` stores the raw `quote.coupon` object** | Line 0600 passes `quote.coupon` directly into the `orders` table. If the column expects a scalar (e.g., coupon code string) the DB driver may serialize the object implicitly or raise an error, potentially corrupting the stored coupon data and affecting later discount calculations. The fragment does not show the table schema, so the impact is uncertain. |

## Uncertainty  

| Area | Why the evidence is insufficient | What to verify |
|------|----------------------------------|----------------|
| **Idempotency of `cancel`** – The fragment does not show any outer guard (e.g., a request‑ID deduplication layer) that might prevent a second call from reaching the function. If such a guard exists, the double‑stock issue would be mitigated. | Need to inspect the public `cancel` endpoint or any wrapper that records request IDs. |
| **Schema of `orders.coupon` column** – Without the table definition we cannot know whether storing the whole `quote.coupon` object is valid. | Look at the `CREATE TABLE orders …` statement and the type of `quote.coupon`. |
| **Transaction handling for `_reserve_line` and the whole checkout flow** – The fragment shows `_reserve_line` alone; we do not see whether the caller wraps all line reservations in a single DB transaction. If not, a partial reservation could leave stock inconsistent. | Examine the checkout implementation that calls `_reserve_line` for each line. |
| **Whether duplicate SKUs are already collapsed before reaching `_reserve_line`** – The business rule requires consolidation, but the fragment does not show the code that builds `quote.lines`. | Review the code that builds the `Quote` object from the cart. |

## Next checks  

1. **Cancel idempotency** – Search for a higher‑level cancel API that validates a `request_id` or checks `order["status"]` before invoking `cancel`. If none exists, add a guard: `if order["status"] == "cancelled": return self.view(order_id)` (or raise a specific error).  
2. **Database schema for `orders.coupon`** – Verify the column type and ensure only a serializable value (e.g., coupon code string or JSON) is stored. If an object is being persisted, adjust the insertion to store a primitive representation.  
3. **Checkout transaction** – Locate the method that creates an order (likely `checkout`) and confirm that it:  
   * Begins a DB transaction,  
   * Calls `_reserve_line` for **all** lines before inserting the order, and  
   * Rolls back if any reservation fails.  
   If any step is missing, add proper transaction handling to avoid partial stock reservation.  
4. **SKU deduplication before reservation** – Review the code that builds `Quote.lines` from the cart to ensure repeated SKUs are merged into a single `PricedLine`. If not, add that step to prevent unnecessary multiple stock updates.  
5. **Audit of inventory events** – Check whether `self.db.inventory_event` enforces uniqueness (e.g., by request ID). If not, a duplicated cancel could create duplicate inventory events, making later reconciliation harder. Consider adding a unique constraint or idempotency token.  

Addressing the high‑severity cancel‑idempotency issue will stop stock from inflating when a cancellation request is retried, directly protecting the correctness of inventory totals. The other items are lower‑risk but still important for maintaining accurate financial totals and robust reporting.