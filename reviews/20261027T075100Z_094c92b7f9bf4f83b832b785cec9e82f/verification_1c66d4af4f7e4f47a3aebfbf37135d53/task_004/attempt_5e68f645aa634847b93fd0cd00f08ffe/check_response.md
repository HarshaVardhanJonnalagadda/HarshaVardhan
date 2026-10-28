## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.shipping_cost` implementation (lines 0514‑0515):  

  ```python
  0514:         if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
  0515:             return 0
  ```

  The condition uses only `subtotal`; the `discount` argument is never referenced.

## Explanation and limits  
The business rule states that standard shipping is free **when merchandise *after* discount is at least 10,000 cents**. The function receives both `subtotal` (pre‑discount amount) and `discount`, yet the free‑shipping check compares only `subtotal` to `FREE_SHIPPING_CENTS`. Because `discount` is ignored, the function applies free shipping based on the pre‑discount subtotal, contradicting the rule that requires the post‑discount amount.  

Thus, the claim that the free‑shipping rule checks pre‑discount subtotal, not post‑discount as required, is directly supported by the source code.  

Limitations: This assessment is confined to the `PricingService.shipping_cost` method. We cannot verify how callers compute or pass `subtotal` and `discount`; however, the method itself does not incorporate the discount in its free‑shipping decision, which is sufficient to support the claim for this batch.

## Next check  
Further verification could examine callers of `PricingService.shipping_cost` to see whether they pre‑adjust `subtotal` to reflect discounts before invoking the method. If callers already pass a post‑discount subtotal, the rule might be satisfied indirectly. However, based solely on the examined function, the free‑shipping logic does not use the discount parameter.