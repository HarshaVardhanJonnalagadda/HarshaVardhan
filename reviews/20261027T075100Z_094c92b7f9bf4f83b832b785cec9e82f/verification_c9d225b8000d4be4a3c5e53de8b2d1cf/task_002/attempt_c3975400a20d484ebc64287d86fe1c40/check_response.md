## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.shipping_cost` definition (lines 0511‑0516):  

  ```python
  0511: def shipping_cost(self, method: str, subtotal: int, discount: int) -> int:
  0512:     if method == "pickup":
  0513:         return 0
  0514:     if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
  0515:         return 0
  0516:     return SHIPPING_CENTS[method]
  ```

- Call site in `PricingService.quote` (lines 0524‑0525):  

  ```python
  0524: discount = self.coupon_discount(request.coupon, subtotal, now)
  0525: shipping = self.shipping_cost(request.shipping, subtotal, discount)
  ```

## Explanation and limits  
The business rule states that **standard shipping is free when merchandise *after discount* is at least 10,000 cents**. The code’s `shipping_cost` receives both `subtotal` (pre‑discount) and `discount`, but the free‑shipping check (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS`) uses only `subtotal`. It never incorporates `discount`, so the condition is evaluated on the pre‑discount amount, contrary to the rule.

Consequences: an order whose pre‑discount subtotal exceeds 10 000 cents will receive free standard shipping even if a coupon reduces the post‑discount amount below that threshold. Conversely, an order that meets the free‑shipping threshold only after discount will still be charged the standard 500‑cent fee.

No other helper or later adjustment to shipping is shown in the provided source; the only place shipping cost is computed is this function. Therefore the evidence directly refutes the intended behavior.

## Next check  
- Verify whether any downstream logic (e.g., after `quote` creation) overrides `shipping_cents` based on post‑discount totals. If such logic exists elsewhere, it could mitigate the issue, but it is not present in the retrieved excerpts.