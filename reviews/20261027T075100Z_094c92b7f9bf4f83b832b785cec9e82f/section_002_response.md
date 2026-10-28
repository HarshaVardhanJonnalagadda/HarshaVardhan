## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Info** | **Quantity is parsed correctly** | `CheckoutRequest.from_dict` (lines 0189‑0194) – `quantity = integer(value.get("quantity"), "quantity", 1, MAX_LINE_QUANTITY)` and the tuple of `CartLine` objects is built without modification. The code **does not truncate or ignore** the quantity value supplied by the client. |
| **Info** | **Duplicate‑SKU check only rejects duplicates** | `CheckoutRequest.from_dict` (lines 0195‑0196) – `if len({line.sku for line in lines}) != len(lines): raise ServiceError("Combine duplicate SKUs into one cart line")`. This enforces the business rule that a cart must not contain the same SKU more than once, but it does **not** combine them; it simply raises an error. |
| **Info** | **Shipping method validation** | `CheckoutRequest.from_dict` (lines 0197‑0199) – validates that the supplied `shipping` string is one of the keys in `SHIPPING_CENTS`. No evidence here that “pickup” is incorrectly mapped to a non‑zero cost. |

The supplied fragment **does not contain any arithmetic** that computes the merchandise subtotal, tax, shipping, or total. Consequently, the observed discrepancy (subtotal $10 instead of $30) cannot be traced to the code shown.

## Uncertainty  

* The user’s symptom (subtotal of one unit instead of three) must arise in the part of the code that **prices the cart** (e.g., a function that builds a `Quote` from a `CheckoutRequest`). That logic is not present in the excerpt, so we cannot confirm whether the bug is due to:  
  * an off‑by‑one error when iterating over `lines`,  
  * mistakenly using `line.unit_price_cents` instead of `line.unit_price_cents * line.quantity`,  
  * a database write/read problem that stores only a single quantity, or  
  * a later transformation that collapses the `lines` tuple incorrectly.  

* The constant `MAX_LINE_QUANTITY` is referenced but not shown; if it were set to `1` the validator would reject a quantity of 3, but the request succeeded, so the constant is presumably larger. Still, we cannot verify its value.

* The `SHIPPING_CENTS` mapping is not displayed; if “pickup” were mistakenly mapped to a non‑zero value, the total would be higher, not lower, so it is unlikely to explain the $10 subtotal.

## Next checks  

1. **Locate the function that creates a `Quote`** (or any function that computes `subtotal_cents`, `discount_cents`, `tax_cents`, `shipping_cents`, `total_cents`). Examine how it iterates over `CheckoutRequest.lines` and whether it multiplies `unit_price_cents` by `quantity`.  

2. **Inspect the price‑lookup logic** for a product SKU (likely a query against the `products` table). Verify that the retrieved `price_cents` is the *current* catalog price and that the quantity is applied correctly.  

3. **Check any database write for `order_lines`** (INSERT statements). Ensure the `quantity` column receives the value from the request and is not overwritten by a default of `1`.  

4. **Review any post‑processing that aggregates line totals** (e.g., summing `line_total_cents` into `subtotal_cents`). Look for accidental use of `sum(line.unit_price_cents for line in lines)` instead of `sum(line.unit_price_cents * line.quantity for line in lines)`.  

5. **Confirm the tax calculation** follows the rule “10 % of merchandise after discount, rounded half‑up”. Although tax is not the root of the $10 vs $30 issue, an incorrect rounding implementation could affect the final total.  

6. **Run a unit test** (or manually invoke the pricing routine) with a payload matching the user’s scenario: three items of a known SKU priced at 1000 cents each, shipping = “pickup”, no coupon. Compare the intermediate values (`lines`, `priced_lines`, `subtotal_cents`, etc.) against expectations.  

By focusing on the missing pricing logic, we can determine whether the subtotal is being truncated to a single unit and fix the bug accordingly.