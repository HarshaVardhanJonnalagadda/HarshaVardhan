## Findings

| Severity | Title | Evidence | Explanation |
|----------|-------|----------|-------------|
| **High** | **Subtotal calculated from unit price instead of line total** | `quote` method (lines 0522‑0524):<br>`lines = self.price_lines(request.lines)`<br>`subtotal = sum(line.unit_price_cents for line in lines)` | `price_lines` creates a `PricedLine` that contains both `unit_price_cents` **and** `line_total_cents` (line 0489). The subtotal of an order must be the sum of *line totals* (price × quantity). Summing only the unit price ignores the quantity, so any line with `quantity > 1` under‑states the merchandise subtotal, which in turn reduces the computed discount, tax, and final total. This directly violates the business rule “Merchandise subtotal is the sum of unit price multiplied by quantity for every cart line.” |
| **Medium** | **Free‑shipping check uses pre‑discount subtotal** | `shipping_cost` method (lines 0511‑0516):<br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` | The rule states that standard shipping is free **when merchandise *after discount* is at least 10 000 cents**. The implementation checks `subtotal` (pre‑discount) and completely ignores the `discount` argument that is passed in. Orders that qualify for free shipping after a coupon will still be charged shipping, and conversely orders that do not qualify after discount could incorrectly receive free shipping if the pre‑discount subtotal is high enough. |
| **Low** | **`shipping_cost` signature includes an unused `discount` parameter** | Same method (lines 0511‑0516) – the `discount` argument is never referenced. | While not a functional bug by itself, the presence of an unused parameter suggests a missing implementation (the free‑shipping rule) and can lead to future maintenance errors. |

## Uncertainty

| Issue | Why it is uncertain |
|-------|----------------------|
| **Duplicate SKU handling in `price_lines`** | The business rule requires that repeated SKUs be combined into a single line before pricing. `price_lines` validates each line independently (`if product.stock < line.quantity`). If the caller supplies duplicate SKUs, the stock check could pass for each line individually while the combined quantity exceeds available stock. The snippet does not show the caller’s preprocessing, so we cannot determine whether this validation is guaranteed elsewhere. |
| **Atomicity of stock reservation** | `checkout` calls `_reserve_line` for each priced line after inserting the order. The code fragment does not show the implementation of `_reserve_line`; we cannot confirm that it correctly rolls back all reservations if any line fails, or that it prevents partial reservation when stock is insufficient across multiple lines. |

## Next checks

1. **Confirm subtotal calculation** – Verify that `Quote` objects (and any downstream code) expect `subtotal_cents` to be the sum of `line_total_cents`. If so, change line 0524 to:<br>`subtotal = sum(line.line_total_cents for line in lines)`.

2. **Fix free‑shipping logic** – Update `shipping_cost` to use the post‑discount amount:<br>`if method == "standard" and (subtotal - discount) >= FREE_SHIPPING_CENTS:`.

3. **Remove or use the `discount` parameter** – Either eliminate the unused argument from the method signature or incorporate it as shown above, to avoid confusion.

4. **Inspect caller of `PricingService.price_lines`** – Ensure that the checkout flow (or any API that builds a `CheckoutRequest`) consolidates duplicate SKUs before invoking `price_lines`. If not, add a deduplication step or adjust `price_lines` to aggregate quantities per SKU.

5. **Review `_reserve_line` implementation** – Check that it atomically decrements product stock, validates total quantity across all lines for the same SKU, and correctly rolls back on any failure within the surrounding transaction.

6. **Add tests** – Create unit tests that cover:<br>• Orders with multi‑quantity lines (e.g., quantity = 3) to verify subtotal, tax, discount, and total.<br>• Coupon‑discounted orders that should receive free standard shipping.<br>• Duplicate‑SKU carts to confirm stock validation and reservation behavior.