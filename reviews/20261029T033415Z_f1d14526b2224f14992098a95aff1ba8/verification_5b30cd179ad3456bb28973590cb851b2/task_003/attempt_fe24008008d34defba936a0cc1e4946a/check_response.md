## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0511: def shipping_cost(self, method: str, subtotal: int, discount: int) -> int:
0512:     if method == "pickup":
0513:         return 0
0514:     if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
0515:         return 0
0516:     return SHIPPING_CENTS[method]
```
*Lines 0511‑0516 of `PricingService.shipping_cost`*  

## Explanation and limits  
The business rule states that **standard shipping is free when the merchandise *after discount* is ≥ 10 000 cents**.  
The implementation receives both `subtotal` (pre‑discount) and `discount` (the coupon amount) but the conditional on line 0514 checks only `subtotal` against `FREE_SHIPPING_CENTS`. The `discount` argument is never used, so the free‑shipping eligibility is calculated on the pre‑discount amount.  

Consequences:  

* An order whose discounted subtotal reaches 10 000 cents but whose original subtotal is lower will be incorrectly charged the standard shipping fee.  
* Conversely, an order whose original subtotal exceeds 10 000 cents but falls below that threshold after applying a coupon will incorrectly receive free shipping.  

The bug is directly visible in the `shipping_cost` method; no other helper in the provided code adjusts this logic. The `quote` method (lines 0518‑0535) passes both `subtotal` and `discount` to `shipping_cost`, but the latter ignores `discount`, confirming the mismatch.

## Next check  
* Verify whether any other part of the code (e.g., a wrapper around `shipping_cost` or a later adjustment) compensates for this omission.  
* Ensure that tests cover scenarios where a coupon brings the post‑discount subtotal below/above the free‑shipping threshold.  
* Consider adding unit tests that assert free shipping is granted only when `subtotal - discount >= FREE_SHIPPING_CENTS`.  