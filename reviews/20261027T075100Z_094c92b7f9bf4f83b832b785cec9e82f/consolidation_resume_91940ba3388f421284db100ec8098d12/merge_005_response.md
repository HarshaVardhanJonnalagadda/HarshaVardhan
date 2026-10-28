# Review  

This report **consolidates all section notes** you supplied (the previous draft and the additional findings) and highlights evidence that may explain why an order for three MUGs ($10 each, pickup, no coupon) shows a merchandise subtotal of **$10** and a total of **$11** instead of the expected $30 + tax.  

> **Important:** The original source code has **not** been inspected in this step. All conclusions are based solely on the quoted excerpts and comments you provided. **Human validation against the complete implementation and the business rules is required** before any defect is confirmed or a change is made.  

---  

## Answer to the request  

The most plausible explanation, given the available evidence, is that **the order‑pricing routine computes the merchandise subtotal from the unit price only, ignoring the line quantity**.  

* In `PricingService.quote` the subtotal is calculated as  

```python
subtotal = sum(line.unit_price_cents for line in lines)   # line 0523
```  

  which yields **1 000 cents** (the price of a single mug) instead of **3 000 cents**.  

* Tax (10 % rounded half‑up) is then applied to that incorrect subtotal, giving 100 cents tax and a total of 1 100 cents ($11) – exactly the numbers you observed.  

Thus the discrepancy is most likely caused by the **“subtotal calculated from unit price instead of line total”** defect reported in `PricingService.quote` (line 0523).  

---  

## Important findings  

| Severity | Finding | Source quotation & line reference |
|----------|---------|-----------------------------------|
| **High** | **Subtotal calculated from unit price instead of line total** – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |
| **Medium** | **Cancel can be executed repeatedly, inflating stock** – `cancel` adds back stock without checking order status. | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |
| **Medium** | **Free‑shipping rule uses pre‑discount subtotal** – condition checks raw subtotal, not post‑discount amount. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |
| **Info** | **Quantity parsing is correct** – `CheckoutRequest.from_dict` extracts `quantity` with proper bounds. | `CheckoutRequest.from_dict` – lines 0189‑0194 |
| **Info** | **Duplicate‑SKU validation only rejects duplicates** – does not combine them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |
| **Info** | **Shipping‑method validation present** – request validates that `shipping` is a key in `SHIPPING_CENTS`. | `CheckoutRequest.from_dict` – lines 0197‑0199 |
| **Info** | **Catalog price update works** – `CatalogService.update_price` writes the new `price_cents`. | `CatalogService.update_price` – lines 0428‑0436 |
| **Info** | **No subtotal‑related logic in the data‑class excerpt** – the shown file contains only helpers and validation; arithmetic lives elsewhere. | “Lines 1‑188 (entire excerpt).” |

---  

## Uncertainty and conflicting evidence  

| Area | Why evidence is insufficient | What remains unknown |
|------|------------------------------|----------------------|
| **Subtotal of $10 vs. $30** | The code that creates the `Quote` (`self.pricing.quote`) is not included, so we cannot see the full aggregation logic. | Whether duplicate SKUs are merged correctly and whether any later step overwrites `subtotal_cents`. |
| **Tax calculation** | `quote.tax_cents` is produced by the missing `quote` implementation. | Whether tax is applied to the *post‑discount* subtotal and whether rounding follows “half‑up”. |
| **Shipping cost for pickup** | Mapping from `request.shipping` (e.g., `"pickup"`) to `quote.shipping_cents` is not shown. | Whether `"pickup"` correctly maps to `0` cents. |
| **Idempotent checkout** | Definition of `CheckoutRequest.fingerprint()` (fields hashed) is absent. | Whether two semantically identical checkout requests always generate the same hash, guaranteeing true idempotency. |
| **Free‑shipping rule** | Business rule requires the *post‑discount* amount ≥ 10 000 cents; code checks the raw subtotal. | Impact on orders that use discounts (not the current case, but a rule mismatch). |

The high‑severity subtotal bug is strongly supported, while the other points need the missing source to be verified.

---  

## Next checks  

1. **Inspect `PricingService.quote`**  
   * Confirm that `subtotal` is computed as `sum(line.unit_price_cents for line in lines)`.  
   * Change it to `sum(line.unit_price_cents * line.quantity for line in lines)` or use the already‑computed `line_total_cents`.  

2. **Verify order‑creation persistence**  
   * Locate where the `Quote` is written to the `orders` table. Ensure `subtotal_cents` is stored directly from the corrected `Quote` without later alteration.  

3. **Search for post‑quote adjustments**  
   * Look for any function that might replace `subtotal_cents` after the quote is generated (e.g., in `OrderService._insert_order`).  

4. **Validate free‑shipping logic**  
   * Find all callers of `PricingService.shipping_cost`.  
   * Ensure they pass the **post‑discount** subtotal; if not, adjust the condition to match the business rule.  

5. **Confirm shipping‑method mapping**  
   * Locate the mapping that turns `request.shipping` into `quote.shipping_cents`. Verify that `"pickup"` yields `0` cents.  

6. **Review `CheckoutRequest.fingerprint()`**  
   * Check that it hashes all pricing‑relevant fields (cart items, quantities, shipping, coupon) and excludes volatile data.  

7. **Make `cancel` idempotent**  
   * Add a guard: if `order["status"] == "cancelled"` skip the stock‑restock loop, preventing repeated inventory inflation.  

8. **Run a targeted test**  
   * Payload: three MUG lines, `quantity: 3`, `unit_price_cents: 1000`, `shipping: "pickup"`, no coupon.  
   * Expected: `subtotal_cents = 3000`, `tax_cents = 300`, `total_cents = 3300` ($33.00). Compare actual intermediate values (`priced_lines`, `subtotal_cents`, etc.) against expectations.  

9. **Audit trail consistency**  
   * Verify that `self.db.audit` records a snapshot of the quote **before** any mutable state (e.g., price changes) could affect the stored order.  

10. **Run the full test suite** (if available) with emphasis on multiple‑quantity cart lines, free‑shipping thresholds, and tax calculations.  

---  

> **Note:** This report aggregates the supplied section notes and highlights likely problem areas. **Human validation against the complete source code and the business rules is essential** before any defect is confirmed or a change is made.