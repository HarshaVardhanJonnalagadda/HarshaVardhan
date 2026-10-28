## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Missing command‑handler for `export` and `top-products`** | `dispatch()` – lines 1018‑1020. The parser adds sub‑commands `export` and `top-products` (lines 0930‑0937) but `dispatch()` never branches on them. The function will fall through and return `None`, so the CLI will silently do nothing instead of generating a CSV export or a product‑ranking report. |
| **Medium** | **`write_invoice` assumes all monetary fields are present** | `write_invoice()` – lines 0966‑0973. The code accesses `order['subtotal_cents']`, `order['discount_cents']`, `order['shipping_cents']`, `order['tax_cents']`, `order['total_cents']`, and `order['refunded_cents']` without any guard. If `OrderService.view()` ever omits one of these keys (e.g., an order that has never been refunded may not contain `refunded_cents`), a `KeyError` will abort invoice generation, potentially leaving the user without a record of the total amount. |
| **Medium** | **No validation of restock quantity sign** | `dispatch()` – line 1009 → `catalog.restock(args.sku.upper(), args.quantity, …)`. The CLI accepts any integer (`type=int, required=True`). If a negative number is supplied, the underlying `CatalogService.restock()` could subtract stock instead of adding it, corrupting inventory counts. The same applies to `--quantity` for the `restock` command. |
| **Medium** | **No validation of price amount sign** | `dispatch()` – line 1015 → `catalog.update_price(args.sku.upper(), money_to_cents(args.amount), …)`. A user could pass a negative amount (e.g., “‑5.00”), which `money_to_cents` will convert to a negative integer. If `CatalogService.update_price()` does not reject negative prices, future order totals could become negative or otherwise incorrect. |
| **Low** | **Potential `KeyError` on missing `refunded_cents`** | `write_invoice()` – line 0972. See the “Missing monetary fields” finding; the specific risk is that the `refunded_cents` entry may be omitted for orders that have never been refunded. |
| **Low** | **Directory existence check but not file‑type check** | `write_invoice()` – line 0974. The code raises `ServiceError` if the parent directory does not exist, but it does not verify that `path` itself is not a directory. Attempting to open a directory with mode `"x"` would raise an `IsADirectoryError`, which is less user‑friendly. |

### Why these matter for totals or stock  

* **Missing command handling** – Users cannot generate the CSV export or the “top‑products” ranking, which are the primary ways the system reports totals and product performance. The absence of these features defeats the business rule that reports must be accurate and available.  
* **Assumed monetary fields** – If an invoice crashes because a field is missing, the user may not see the final total, leading to confusion or manual recalculation that could introduce errors.  
* **Unvalidated restock quantity** – A negative quantity would reduce the inventory ledger without a corresponding sale, causing the system to think stock is lower than it actually is. Subsequent checkout attempts could be incorrectly rejected for “out‑of‑stock”.  
* **Unvalidated price amount** – Setting a negative unit price would make the merchandise subtotal (price × quantity) negative, which would flow through discount, tax, and total calculations, potentially producing a negative order total. This directly violates the rule that each cart line quantity is positive and that totals are expressed in cents.  

## Uncertainty  

| Area | What is unknown | Why it matters |
|------|----------------|----------------|
| **`CatalogService.restock` implementation** | Does it guard against negative `quantity` values? Does it treat a negative number as a subtraction? | Without seeing the method, we cannot confirm whether the CLI’s lack of validation actually leads to stock corruption. |
| **`CatalogService.update_price` implementation** | Does it reject negative `price_cents` or clamp to zero? | If the service already validates, the CLI’s omission is harmless; otherwise, negative prices could break total calculations. |
| **Structure of the dict returned by `OrderService.view`** | Does it always contain the six monetary keys used in `write_invoice` (including `refunded_cents`)? | If the service guarantees these keys (e.g., defaulting to 0), the KeyError risk is mitigated. |
| **Behavior of `money_to_cents`** | Does it raise on negative inputs or malformed strings? | If it raises, the CLI will abort before reaching the service layer, which may be acceptable; if it silently returns a negative integer, the bug propagates. |
| **Error handling for unknown commands** | Does the surrounding CLI framework (argparse) already catch unknown sub‑commands before reaching `dispatch`? | If argparse raises a usage error for `export`/`top-products`, the missing branches may never be exercised; however, the parser *does* accept those commands, so the missing branches are reachable. |

## Next checks  

1. **Inspect `CatalogService.restock`** – Verify that it validates `quantity > 0` and raises a clear error for non‑positive values.  
2. **Inspect `CatalogService.update_price`** – Ensure it rejects negative `price_cents` (or at least prevents setting a price ≤ 0).  
3. **Inspect `OrderService.view`** – Confirm that the returned order dictionary always includes `subtotal_cents`, `discount_cents`, `shipping_cents`, `tax_cents`, `total_cents`, and `refunded_cents` (with a default of 0 when no refunds exist).  
4. **Inspect `money_to_cents`** – Determine its behavior on negative strings and malformed inputs; add CLI‑level validation if needed.  
5. **Add missing branches in `dispatch()`** – Implement handling for the `export` and `top-products` commands (or remove them from the parser if they are not supported).  
6. **Consider adding a guard in `write_invoice`** – Before opening the file, check `if path.is_dir(): raise ServiceError("Invoice path is a directory")` to give a clearer error message.  
7. **Add unit tests** that deliberately pass negative quantities, negative prices, and orders without refunds to confirm that the system raises appropriate errors and does not corrupt totals or inventory.  

Addressing the items above will eliminate the demonstrated defects and reduce the risk of incorrect totals or stock levels.