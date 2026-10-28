## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Subtotal calculated from unit price instead of line total** | `PricingService.quote` – line 0523: <br>`subtotal = sum(line.unit_price_cents for line in lines)` |
| **Medium** | **Free‑shipping rule uses pre‑discount subtotal** | `PricingService.shipping_cost` – line 0514‑0515: <br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` |

### Subtotal mis‑calculation  
*What the code does*  
- `price_lines` (lines 0476‑0490) creates a `PricedLine` that contains both `unit_price_cents` and `line_total_cents` (price × quantity).  
- `quote` (lines 0518‑0536) then computes the order subtotal by **summing only `unit_price_cents`** of each line (line 0523).  

*Why this causes the reported problem*  
- For three mugs priced at 1 000 cents each, `price_lines` produces a line with `unit_price_cents = 1000` and `line_total_cents = 3000`.  
- The subtotal is calculated as `1000` (the unit price) instead of `3000`.  
- Tax (10 %) is applied to the wrong subtotal, yielding `tax = 100` and a total of `1 100` cents ($11) – exactly the numbers the user observed.

*Assumptions / missing cross‑function evidence*  
- The `Quote` object is later persisted unchanged (no other code in this section rewrites `subtotal_cents`).  
- No later adjustment of `subtotal_cents` is performed elsewhere in the codebase (outside the supplied section).  

### Shipping‑cost free‑shipping condition  
*What the code does*  
- `shipping_cost` checks `if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` (line 0514).  
- The business rule states free standard shipping applies when **merchandise after discount** is ≥ 10 000 cents.  

*Why this could be a problem*  
- If a discount reduces the subtotal below the free‑shipping threshold, the current implementation may still grant free shipping because it looks at the pre‑discount subtotal.  

*Assumptions / missing evidence*  
- The rest of the system may compensate for this elsewhere (e.g., by passing a discounted subtotal), but within this file the condition is clearly based on the wrong value.

## Uncertainty  

- Whether any later processing step (outside the provided section) overwrites `subtotal_cents` with the correct `line_total_cents`. The current evidence shows no such step, but the full file is not present.  
- Whether the free‑shipping rule is intentionally simplified for this exercise; the code comment does not clarify the intended behavior beyond the rule excerpt.  

## Next checks  

1. **Inspect order‑creation persistence** – locate where the `Quote` returned by `PricingService.quote` is written to the `orders` table. Verify that `subtotal_cents` is stored directly from the `Quote` without further modification.  

2. **Search for any post‑quote adjustments** – look for functions that might recompute or replace `subtotal_cents` after `quote` is generated (e.g., in `OrderService._insert_order` or elsewhere).  

3. **Validate free‑shipping logic** – find any callers of `PricingService.shipping_cost` and confirm whether they pass the discounted subtotal or the raw subtotal. If the rule is meant to use the post‑discount amount, adjust the condition accordingly.  

4. **Run unit tests (if present)** – especially tests that cover multiple‑quantity cart lines and free‑shipping thresholds, to see if they currently fail or pass unexpectedly.  

Addressing the subtotal bug will resolve the user’s immediate discrepancy (subtotal $10 → $30, total $11 → $33). The shipping‑cost check should be reviewed to ensure compliance with the documented business rule.