**## Findings**

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Uncaught `KeyError` when order or customer is missing** | `write_invoice` – lines 0951‑0953  <br>```python\norder = OrderService(db).view(order_id)\ncustomer = db.customer(order[\"customer_id\"])\n``` |
| **Medium** | **Assumes all expected fields are present in the order dict** | `write_invoice` – lines 0966‑0972  <br>```python\nf\"Subtotal: {format_money(order['subtotal_cents'])}\"\n... f\"Total: {format_money(order['total_cents'])}\"```
| **Low** | **`build_parser` does not validate that the `--request` file exists** | `build_parser` – line 0894  <br>```python\ncommand.add_argument(\"--request\", type=Path, required=True)\n``` |
| **Low** | **`build_parser` uses `required=True` on `add_subparsers` (Python 3.6‑3.7 incompatibility)** | `build_parser` – line 0887  <br>```python\ncommands = parser.add_subparsers(dest=\"command\", required=True)\n``` |

### What the code demonstrably does
* `write_invoice` fetches an order via `OrderService(db).view(order_id)` and then immediately accesses `order["customer_id"]` and a series of monetary fields (`subtotal_cents`, `discount_cents`, …).  
* It builds a list of text lines and writes them to a new file (`path.open("x")`).  
* `build_parser` constructs an `argparse.ArgumentParser` with sub‑commands and arguments, but it does **not** perform any existence checks on the paths supplied to `--request` or other file‑related arguments.

### How the behavior could affect totals or stock
* **Uncaught `KeyError`** – If an invalid `order_id` is supplied (or the order record is corrupted and missing any of the expected keys), the function will raise a `KeyError` and abort the CLI command. In a larger workflow this could leave a transaction half‑completed (e.g., a stock reservation already performed but the invoice never written), causing inventory counts to diverge from recorded sales totals.
* **Assumed presence of monetary fields** – If any of the fields (`subtotal_cents`, `discount_cents`, `shipping_cents`, `tax_cents`, `total_cents`, `refunded_cents`) are `None` or omitted, the same `KeyError` will be raised, again potentially interrupting a process that should be atomic (checkout → invoice → confirmation).  
* **Missing file‑existence validation** – Supplying a non‑existent request JSON file to `quote` or `checkout` will cause later code (outside this fragment) to attempt to read the file and likely raise an `IOError`. While this does not directly change totals, it can stop the checkout flow before stock is reserved, which may be acceptable, but the lack of early validation makes the error surface later and harder to diagnose.
* **`required=True` on subparsers** – On Python versions that do not support the `required` parameter (≤ 3.6), the parser will raise a `TypeError` at start‑up, preventing any command from running. This would block the entire service, indirectly affecting all order‑related operations, including stock updates.

### Assumptions / Missing Cross‑Function Evidence
* We assume `OrderService(db).view` returns a dictionary with the exact keys used. The implementation of `view` is not shown; it might already raise a custom exception for missing orders, in which case the `KeyError` risk is mitigated.  
* The `format_money` helper is assumed to accept an integer number of cents; if it expects a different type, a `TypeError` could be raised.  
* The rest of the CLI workflow (e.g., how `--request` files are parsed) is not present, so we cannot confirm whether missing‑file errors are already caught elsewhere.  
* The `Database` object's `customer` method may raise its own exception for unknown customers; we do not see that code.

**## Uncertainty**
* Whether `OrderService.view` validates the existence of the order and returns a well‑structured dict or raises a domain‑specific exception.  
* Whether the order dict is guaranteed (by a schema or ORM) to contain all monetary fields; if a migration introduced a new field, older rows might lack it.  
* The exact Python version targeted by the project; the `required=True` on `add_subparsers` may be intentional for Python 3.7+.

**## Next checks**
1. **Inspect `OrderService.view`** – Verify it raises a clear, caught exception for missing/invalid orders and that it always returns a dict containing all monetary keys. If it can return incomplete data, add defensive checks in `write_invoice`.  
2. **Validate order dict schema** – Ensure the database layer enforces non‑null constraints for `subtotal_cents`, `discount_cents`, `shipping_cents`, `tax_cents`, `total_cents`, and `refunded_cents`. Add fallback handling or explicit error messages if any are missing.  
3. **Review `format_money`** – Confirm it safely handles `None` or unexpected types; otherwise guard the calls.  
4. **Add early file existence validation** – In `build_parser` (or the command handlers), check that `args.request` points to an existing readable file before proceeding.  
5. **Confirm Python version compatibility** – If the project must run on Python 3.6, replace `required=True` on `add_subparsers` with a manual post‑parse check (`if not args.command: parser.error(...)`).  
6. **Test error paths** – Write unit tests that invoke `write_invoice` with a non‑existent `order_id`, with an order missing one of the monetary fields, and with a missing invoice directory to ensure the raised `ServiceError` is handled gracefully by the CLI entry point.  

Addressing the high‑severity missing‑order/customer validation will prevent the most dangerous scenario where stock is reserved but the invoice (and thus the final accounting) fails, leading to mismatched totals and inventory counts.