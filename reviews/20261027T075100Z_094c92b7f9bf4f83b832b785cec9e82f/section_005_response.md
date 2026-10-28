## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Cancel can be executed repeatedly, inflating stock** | `checkout.py` lines **0622‑0636** – the `cancel` method restores product stock for every line **without first verifying that the order is not already cancelled**. <br>```python\nfor line in self.db.lines(order_id):\n    self.db.execute(\"UPDATE products SET stock = stock + ?, updated_at = ? \"\n                    \"WHERE sku = ?\",\n                    (line[\"quantity\"], timestamp(now), line[\"sku\"]))\n    self.db.inventory_event(...)\n```<br>If `cancel` is called a second time on the same order (e.g., a client retries the request), the same quantities are added back to `products.stock` again, leaving the inventory ledger inconsistent. The order status is later set to `'cancelled'`, but the stock adjustment has already been performed. |

### Why this matters for the reported problem  

The user’s complaint is about an **incorrect order subtotal/total**, not about inventory. The bug above does **not** affect pricing, but it is a concrete defect that can surface in the same service (e.g., a UI that retries a cancellation). It is therefore a *supported finding* in the supplied code.

## Uncertainty  

| Area | Why the evidence is insufficient | What is unknown |
|------|----------------------------------|-----------------|
| **Subtotal of $10 instead of $30** | The code that computes the subtotal lives in `self.pricing.quote(request, now)`, which is **not included** in this section. The logic that aggregates repeated SKUs, multiplies unit price by quantity, and applies coupons is missing, so we cannot confirm whether the subtotal error originates here. | Whether `quote` correctly sums `line.quantity * line.unit_price_cents` for each line, and whether it merges duplicate SKUs as required by the business rules. |
| **Tax calculation** | Tax is derived from `quote.tax_cents`, also produced by the missing `quote` implementation. | Whether the 10 % tax (rounded half‑up) is applied to the merchandise subtotal *after* discount, as the rules state. |
| **Shipping cost for pickup** | The shipping method is stored in `request.shipping` and later copied into `quote.shipping_cents`. The mapping from shipping method to cost is not shown. | Whether the “pickup” method is correctly mapped to a zero‑cent shipping charge. |
| **Idempotent checkout** | Checkout checks `existing[\"request_hash\"] != request.fingerprint()`. The definition of `request.fingerprint()` (which fields are hashed) is not provided. | Whether two semantically identical checkout requests (same cart, same shipping, no coupon) always produce the same hash, guaranteeing true idempotency. |

## Next checks  

1. **Pricing / Quote logic** – Open the file(s) that define `Pricing.quote`. Verify:  
   * Repeated SKUs are combined into a single `PricedLine` with the summed quantity.  
   * `line_total_cents` = `quantity * unit_price_cents`.  
   * `quote.subtotal_cents` is the sum of all `line_total_cents`.  
   * No coupon is applied (coupon fields should be `None`/`0`).  

2. **Tax computation** – Ensure the tax is calculated as `round_half_up(merchandise_after_discount * 0.10)`. Confirm the rounding rule matches “half up to the nearest cent”.

3. **Shipping cost mapping** – Locate the function that translates `request.shipping` (e.g., `"pickup"`) to `quote.shipping_cents`. Confirm that `"pickup"` yields `0` and that free‑shipping thresholds are respected for other methods.

4. **Request fingerprint** – Review `CheckoutRequest.fingerprint()` implementation. Check that it includes all fields that affect order pricing (cart contents, shipping method, coupon) and excludes volatile data (timestamps) so that identical requests generate identical hashes.

5. **Cancel idempotency** – Add a guard in `cancel` to skip the stock‑restock loop when `order[\"status\"] == \"cancelled\"`, or otherwise make the operation idempotent.

6. **Audit trail consistency** – Verify that `self.db.audit` records snapshots of the quote *before* any mutable state (e.g., price changes) could affect the stored order.

Addressing the points above will let us confirm whether the subtotal discrepancy is due to a bug in the quote calculation, and will also fix the identified inventory‑stock bug.