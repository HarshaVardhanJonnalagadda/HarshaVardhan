## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Subtotal calculated from unit price only** | `PricingService.quote` – line **523**: <br>`subtotal = sum(line.unit_price_cents for line in lines)` |
| **Medium** | **Free‑shipping condition uses pre‑discount subtotal** | `PricingService.shipping_cost` – line **511‑515**: <br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` |
| **Low** | **Missing validation for unknown shipping method** | `PricingService.shipping_cost` – line **516**: <br>`return SHIPPING_CENTS[method]` (may raise `KeyError` if `method` is not a key) |
| **Low** | **`low_stock` accepts a threshold of 0** (business rule does not forbid it, but a threshold of 0 will return *all* active products, which may be unintended) | `InventoryService.low_stock` – line **465‑468** |

### 1. Subtotal calculated from unit price only  *(High)*  
*What the code does* – The `quote` method builds a list of `PricedLine` objects where each line already contains `line_total_cents = product.price_cents * line.quantity`. However, the subtotal is recomputed as the sum of **unit** prices:

```python
subtotal = sum(line.unit_price_cents for line in lines)   # line 523
```

*Why this matters* – For any cart line with `quantity > 1` the subtotal will be **under‑estimated** (e.g., a 2‑unit line contributes only the price of one unit). All downstream calculations – coupon discount, tax, shipping, and the final `total_cents` – are based on this wrong subtotal, so the order total can be too low and the discount may be applied incorrectly.

*Assumptions / missing context* – The `PricedLine` type is defined elsewhere, but the fragment shows `line_total_cents` is already computed (line 489‑490). The rest of the system (e.g., order persistence) likely expects the subtotal to be the sum of those line totals.

### 2. Free‑shipping condition uses pre‑discount subtotal  *(Medium)*  
*What the code does* – `shipping_cost` decides whether standard shipping is free by checking the **pre‑discount** subtotal:

```python
if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:   # line 514
    return 0
```

*Why this matters* – The business rules state: *“Standard shipping costs 500 cents, or is free when merchandise **AFTER discount** is at least 10,000 cents.”* The correct check should use `subtotal - discount` (the taxable amount) rather than the raw subtotal. Orders that qualify for free shipping after a coupon will still be charged shipping, and conversely, orders that do **not** qualify after discount may incorrectly receive free shipping.

*Assumptions* – `FREE_SHIPPING_CENTS` is defined elsewhere (presumably 10 000). The `quote` method passes `subtotal` and `discount` separately, so the shipping function has the data it needs; it just uses the wrong variable.

### 3. Missing validation for unknown shipping method  *(Low)*  
*What the code does* – If `method` is not `"pickup"` or `"standard"` the function falls through to:

```python
return SHIPPING_CENTS[method]   # line 516
```

If `method` is an unexpected string, a `KeyError` will be raised, bubbling up as an uncaught exception. This could abort the checkout process and leave the order in an inconsistent state.

*Why this matters* – While not directly altering totals, it can cause a failure that prevents the order from being recorded, potentially leaving reserved stock unreleased (depending on transaction handling).

### 4. `low_stock` accepts a threshold of 0  *(Low)*  
*What the code does* – The helper validates `threshold` with `integer(threshold, "threshold", 0, 100_000)`. A value of 0 is allowed, which makes the query return **all** active products (stock ≤ 0 includes every product).  

*Why this matters* – This is probably not a functional bug for order totals, but it could cause UI or reporting components to display an overwhelming list of products, masking genuine low‑stock items.

## Uncertainty  

| Area | What is unknown | Why it matters |
|------|----------------|----------------|
| Definition of `percentage` | Does it round half‑up to the nearest cent as required for tax and coupon calculations? | Incorrect rounding could affect tax totals and discount amounts. |
| `PricedLine` structure & usage | Are other parts of the system (e.g., order persistence) using `line_total_cents` or `unit_price_cents`? | If some downstream code also sums `unit_price_cents`, the subtotal bug may be compensated elsewhere, but that would be fragile. |
| `SHIPPING_CENTS` mapping | Does it contain only `"standard"` and `"express"` keys? | Determines whether the low‑validation risk can actually happen. |
| Transaction handling in `checkout` | Does `self.db.transaction()` roll back stock reservations if an exception occurs after some lines are reserved? | Needed to confirm that a failure in shipping cost calculation or elsewhere does not leave stock partially reserved. |
| `FREE_SHIPPING_CENTS` constant | Confirm its value matches the business rule (10 000 cents). | Ensures the free‑shipping check is using the correct threshold. |

## Next checks  

1. **Inspect `PricedLine` and order‑creation code** – Verify that the order record stores `line_total_cents` and that any other subtotal calculations (e.g., in reporting) also use the correct field.  
2. **Review `percentage` implementation** – Ensure it rounds half‑up to the nearest cent for both tax and coupon discount calculations.  
3. **Look at `shipping_cost` callers** – Confirm that the method argument is validated (e.g., only `"pickup"`, `"standard"`, `"express"` are allowed) before reaching the function.  
4. **Examine the transaction wrapper** (`self.db.transaction()`) and `_reserve_line` – Make sure that any exception after a partial reservation triggers a rollback, preventing stock from being permanently deducted on a failed checkout.  
5. **Check constants** – Verify the values of `FREE_SHIPPING_CENTS`, `SHIPPING_CENTS`, and `TAX_BASIS_POINTS` to ensure they match the business rules.  
6. **Test scenarios** – Write unit tests that: <br>• Cart lines with quantity > 1 and verify that `quote.subtotal_cents` equals the sum of `line_total_cents`. <br>• Apply a coupon that brings the post‑discount subtotal just above/below the free‑shipping threshold and confirm shipping cost is correct. <br>• Pass an invalid shipping method and confirm a controlled error is raised rather than a raw `KeyError`.  

Addressing the high‑severity subtotal bug will immediately bring order totals, discounts, tax, and shipping calculations in line with the stated business rules. The medium‑severity free‑shipping check should be corrected next to avoid over‑charging customers. Low‑severity issues can be mitigated with input validation and clearer threshold handling.