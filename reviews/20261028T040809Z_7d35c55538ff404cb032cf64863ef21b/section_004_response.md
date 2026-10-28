## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Subtotal uses unit price instead of line total** | `PricingService.quote` (lines 0522‑0524) – `subtotal = sum(line.unit_price_cents for line in lines)` |
| **High** | **Free‑shipping condition ignores discount** | `PricingService.shipping_cost` (lines 0511‑0516) – `if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` |
| **Medium** | **`shipping_cost` may raise `KeyError` for unknown method** | `PricingService.shipping_cost` (lines 0511‑0516) – `return SHIPPING_CENTS[method]` |
| **Medium** | **`price_lines` checks stock before reservation, but reservation is done later; a race could cause over‑reservation** | `PricingService.price_lines` (lines 0476‑0491) and `OrderService.checkout` (lines 0584‑0588) – stock is read, then later `_reserve_line` is called inside the same DB transaction, but the check does not lock the row. |
| **Low** | **`low_stock` returns rows ordered by `stock, sku`; if two products have the same stock the order is deterministic only by SKU, which may not be intended for a “lowest‑stock first” report** | `InventoryService.low_stock` (lines 0464‑0469) – `ORDER BY stock, sku` |

### What the code demonstrably does  

1. **Subtotal mis‑calculation** – `quote` adds only the *unit* price of each line, ignoring the quantity. For a line of 3 units at 100 ¢, the subtotal contributes 100 ¢ instead of 300 ¢. All downstream values (discount eligibility, tax, total) are therefore based on an understated merchandise amount.  

2. **Free‑shipping rule mismatch** – The business rule states that standard shipping is free when *merchandise after discount* ≥ 10 000 ¢. The implementation checks `subtotal >= FREE_SHIPPING_CENTS` **before** discount is applied, so orders that qualify after discount will still be charged shipping.  

3. **Potential `KeyError`** – `SHIPPING_CENTS` is a dict (presumably) keyed by known methods (`standard`, `express`, `pickup`). If a caller passes an unsupported string, the function will raise an uncaught `KeyError` instead of a controlled `Conflict`/`ServiceError`.  

4. **Stock race condition** – `price_lines` validates `product.stock < line.quantity` and raises `Conflict` if insufficient. The actual reservation (`_reserve_line`) happens later in `checkout`. If another concurrent checkout reduces the same product’s stock between those two points, the reservation could fail or cause negative stock, violating the “stock shortage must not partially reserve a cart” rule.  

5. **Ordering tie‑break in low‑stock** – Using `ORDER BY stock, sku` may be acceptable, but if the intent is to surface *only* the lowest‑stock items, the deterministic secondary ordering by SKU could mask items that have the same low stock but a higher SKU, potentially confusing UI/reporting.  

## Uncertainty  

| Area | Why evidence is insufficient |
|------|------------------------------|
| `_reserve_line` implementation | We do not see how the reservation updates `product.stock` or whether it uses row‑level locking. Without that code we cannot confirm whether the race described above actually manifests. |
| Definition of `SHIPPING_CENTS` and `FREE_SHIPPING_CENTS` | Their values and type (e.g., dict, constant) are not shown; we assume a dict for the `KeyError` risk, but it could be a function that handles unknown methods gracefully. |
| `percentage` helper rounding behavior | The tax rule requires “rounded half up to the nearest cent”. If `percentage` uses floor or bankers rounding, tax could be off by a cent. The helper’s implementation is not provided. |
| `payload_hash` and `request.fingerprint()` consistency | Checkout deduplication relies on these hashes matching; we cannot verify they are deterministic across retries. |
| Transaction isolation level of `self.db.transaction()` | If the DB uses a serializable isolation level, the race condition may be prevented; otherwise it may be vulnerable. |

## Next checks  

1. **Inspect `Quote` construction** – Verify that `line_total_cents` is used for subtotal (`sum(line.line_total_cents …)`). Adjust tax, discount, and total calculations accordingly.  

2. **Review `shipping_cost` logic** – Change the free‑shipping condition to `if method == "standard" and (subtotal - discount) >= FREE_SHIPPING_CENTS:` (or pass the already‑computed taxable amount).  

3. **Add validation for unknown shipping methods** – Either raise a `Conflict`/`ServiceError` with a clear message or default to a safe value before indexing `SHIPPING_CENTS`.  

4. **Examine `_reserve_line` and DB transaction settings** – Ensure the stock check and reservation happen atomically (e.g., `SELECT … FOR UPDATE` or an `UPDATE … WHERE stock >= qty` that fails atomically).  

5. **Confirm `percentage` rounding** – Check that it implements “round half up” as required for tax calculations.  

6. **Look at `low_stock` consumer** – Determine whether the secondary ordering by SKU is acceptable or if a deterministic tie‑breaker (e.g., `ORDER BY stock ASC, name ASC`) is preferred.  

7. **Run unit tests covering multi‑quantity carts, discount‑eligible free shipping, and unknown shipping methods** to catch the identified high‑severity bugs.  