# Section review results

Run outcome: failed

These are separate model reviews of source sections. They are not a consolidated assessment. Cross-section behavior may be unresolved and duplicate findings may appear. Human validation is pending.

# Section 1: original lines 1-186

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Low** | **`percentage` does not validate `basis_points` sign** | `0122‑0125` – `def percentage(cents: int, basis_points: int) -> int:`<br>```python\nreturn int((Decimal(cents) * basis_points / 10000).quantize(\n    Decimal(\"1\"), rounding=ROUND_HALF_UP,\n))\n``` |
| **Low** | **`MAX_CART_LINES` is defined but never enforced in this fragment** | `0034` – `MAX_CART_LINES = 40` (no later reference) |
| **Low** | **`money_to_cents` accepts any type that `Decimal` can parse, not only strings** | `0098‑0105` – `def money_to_cents(value: str) -> int:`<br>```python\namount = Decimal(value)\n``` |
| **Low** | **`read_json` will raise `FileNotFoundError` before it can raise a `ServiceError`** | `0126‑0135` – `def read_json(path: Path) -> dict[str, Any]:`<br>```python\nif path.stat().st_size > 100_000:\n    raise ServiceError(...)\nvalue = json.loads(path.read_text(...))\n``` |

### What the code demonstrably does  

* `percentage` simply multiplies a cent amount by a basis‑point factor and rounds half‑up. It does **not** check that `basis_points` is non‑negative or within a sensible range (e.g., 0‑10 000 for a 0‑100 % discount). Supplying a negative value would produce a negative “percentage” that could be used to *increase* a total or *reduce* tax incorrectly.  

* `MAX_CART_LINES` is a constant that matches the business rule *“Maximum 40 lines per cart”*, but the fragment contains no logic that checks the number of `CartLine` objects supplied in a `CheckoutRequest`. If the check is missing elsewhere, a cart with >40 lines could be accepted, potentially leading to inflated totals or unexpected stock reservations.  

* `money_to_cents` is documented to take a **string** representation of money, yet the implementation will also accept `int`, `float`, or `Decimal` because `Decimal()` can construct from those types. If a caller passes a floating‑point value (e.g., `12.34`) the conversion will go through the `Decimal` constructor, but the subsequent `quantize(..., ROUND_HALF_UP)` will round *after* the binary‑float has already introduced a tiny error, possibly yielding an off‑by‑one cent result.  

* `read_json` calls `path.stat()` before opening the file. If the path does not exist, a `FileNotFoundError` bubbles up as an uncaught exception, bypassing the intended `ServiceError` handling that the rest of the CLI expects. This can cause the command to abort with a traceback rather than a clean user‑facing error message.  

### How the behavior could affect totals or stock  

* A **negative `basis_points`** passed to `percentage` could be used (later in the code) to compute a *negative* discount or tax, inflating the order total or causing the system to think stock should be released when it should not.  

* **Missing cart‑line count validation** could allow a malicious or malformed request to contain many more lines than intended, potentially exhausting memory or causing the order‑total calculation to overflow or mis‑behave.  

* **Floating‑point money inputs** that slip through `money_to_cents` could introduce rounding errors that accumulate across many lines, leading to a total that is off by a few cents per line – a noticeable discrepancy in financial reports.  

* **Uncaught `FileNotFoundError`** in `read_json` does not directly change totals, but it can abort the checkout flow before any stock reservation occurs, leaving the system in an inconsistent state if the caller assumes the request was processed.  

## Uncertainty  

* Whether `percentage` is ever called with user‑supplied basis‑point values (e.g., coupon percentages) is unknown from this fragment. The missing validation may be performed elsewhere.  

* The enforcement of `MAX_CART_LINES` could be implemented in a higher‑level function that builds a `CheckoutRequest`. Without seeing that code we cannot say definitively that the rule is violated.  

* The codebase may already ensure that `money_to_cents` is only called with string literals from JSON payloads; if so, the floating‑point path is never exercised.  

* The CLI entry point may wrap `read_json` in a `try/except FileNotFoundError` block; the fragment alone does not show that.  

## Next checks  

1. **Locate the function that builds a `CheckoutRequest`** (likely a `checkout` command handler). Verify that it:  
   * Counts the number of `CartLine` objects and raises a `ServiceError` if it exceeds `MAX_CART_LINES`.  
   * Deduplicates repeated SKUs and combines quantities as required by the business rules.  

2. **Search for all calls to `percentage`** (discount calculation, tax calculation, etc.). Ensure that:  
   * The `basis_points` argument is validated to be non‑negative and not larger than the maximum allowed (e.g., 10 000 for 100 %).  
   * Any negative result is explicitly rejected before being applied to totals.  

3. **Inspect where `money_to_cents` is invoked** (catalog loading, coupon parsing, order creation). Confirm that the source data is always a string from JSON and that no floating‑point values are passed. If floats are possible, add a type check or convert to string first.  

4. **Review the CLI command that calls `read_json`** (e.g., the `checkout` sub‑command). Ensure that a missing file is caught and re‑raised as a `ServiceError` so the user receives a clean error message.  

5. **Check the order‑total calculation logic** (subtotal, discount, tax, shipping). Verify that it uses the validated helpers (`money_to_cents`, `percentage`, `format_money`) and that rounding follows the “half‑up to nearest cent” rule consistently.  

6. **Examine stock‑reservation code** (likely in a transaction context manager). Confirm that it:  
   * Reserves the exact quantity from each `Product.stock`.  
   * Rolls back the reservation if any line fails (atomicity).  
   * Enforces the “no partial reservation” rule.  

7. **Look for any place where coupon usage counters are updated**. Ensure that cancelled orders do not decrement the counter and that the same `request_id` is idempotent.  

By focusing on these areas you can confirm whether the low‑severity issues identified above actually manifest in the live logic, and you can catch any hidden bugs that would affect order totals or inventory levels.

---

# Section 2: original lines 177-344

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Shipping method case‑sensitivity** | `CheckoutRequest.from_dict` – lines 0197‑0199  <br>```python\nshipping = value.get(\"shipping\", \"standard\")\nif not isinstance(shipping, str) or shipping not in SHIPPING_CENTS:\n    raise ServiceError(\"Shipping must be standard, express or pickup\")\n``` |
| **Medium** | **Coupon string is upper‑cased but not validated for existence** | `CheckoutRequest.from_dict` – lines 0200‑0203  <br>```python\ncoupon = value.get(\"coupon\")\nif coupon is not None:\n    coupon = nonempty(coupon, \"coupon\", 40).upper()\n``` |
| **Low** | **Potential missing transaction handling for stock‑affecting operations** (not shown in this fragment) | `Database.__init__` – line 0330 (sets `isolation_level=None`) and `Database.initialize` – lines 0337‑0343. The fragment does not show any explicit `BEGIN`/`COMMIT` around operations that reserve stock or write order totals, so callers may rely on autocommit. If a checkout routine performs several separate writes (reserve inventory, create order, write order lines) without an explicit transaction, a failure part‑way could leave stock reduced while the order is not persisted, corrupting totals/stock. |
| **Low** | **`Database.initialize` uses helper methods (`self.one`, `self.execute`) that are not defined in the shown code** | Lines 0338‑0343. If those helpers do not wrap their calls in a transaction or do not raise on failure, the schema‑initialisation step could silently succeed while later code assumes the metadata row exists, potentially causing later calculations (e.g., discount limits that depend on a stored schema version) to behave incorrectly. |

### What the code demonstrably does  

* **Shipping validation** – Accepts only values that exactly match a key in `SHIPPING_CENTS`. The default is the literal string `"standard"`. If a client sends `"Standard"` (capital “S”) or any other case variation, the check fails and a `ServiceError` is raised, even though the business rule treats shipping as case‑insensitive. This aborts the checkout before any totals or stock are touched, but it also prevents legitimate orders from being processed.  

* **Coupon handling** – When a coupon code is supplied, it is stripped/validated for length (`nonempty`) and forced to upper‑case, but the code does **not** verify that the coupon actually exists or is active. Down‑stream code that calculates the discount will receive a string that may not correspond to a row in the `coupons` table, potentially resulting in a `None` discount (i.e., no discount applied) or, if the downstream code assumes existence, a `KeyError`/`IntegrityError`. Either outcome can cause the final `total_cents` to be wrong.  

* **Database initialization** – The `Database` constructor opens the SQLite connection with `isolation_level=None`, which puts the connection in *autocommit* mode. `initialize` runs the schema script and then queries/updates the `metadata` table via helper methods that are not shown. Because autocommit is on, each statement is committed immediately. If later checkout logic performs multiple writes (stock decrement, order insert, order‑line insert) without an explicit transaction, a failure after the stock decrement will leave the inventory ledger inconsistent with the order total.  

## Uncertainty  

* **`CartLine.from_dict` validation** – The fragment does not show `CartLine`. If that class does not enforce `quantity > 0` or price positivity, the subtotal could be mis‑computed elsewhere.  

* **Implementation of `self.one` / `self.execute`** – Without seeing these helpers we cannot be certain whether they start a transaction, raise on errors, or perform additional validation.  

* **How coupon codes are later looked up** – The fragment only upper‑cases the code; we do not know whether the lookup is case‑insensitive or whether missing coupons are handled gracefully.  

* **Whether downstream code explicitly starts a transaction** – The fragment does not include the checkout service that writes inventory events and order rows. If that code does start a transaction (e.g., `BEGIN; … COMMIT;`), the autocommit setting may be overridden, mitigating the low‑severity risk.  

## Next checks  

1. **Inspect the checkout workflow** (the function that receives a `CheckoutRequest` and creates an order). Verify that:  
   * It opens a transaction (`BEGIN`/`COMMIT` or `with connection:`) that encloses **all** stock reservations, order row inserts, and order‑line inserts.  
   * It rolls back on any exception, ensuring stock is not decremented without a matching order.  

2. **Review `CartLine.from_dict`** to confirm that:  
   * `quantity` is required and must be a positive integer.  
   * `sku` exists in the `products` table and the product is active.  

3. **Examine coupon validation** in the order‑pricing code:  
   * Does it query the `coupons` table and verify `active`, `expires_on`, `max_uses`, etc.?  
   * Does it handle the case where the supplied code does not exist (should raise a clear error, not silently ignore the discount)?  

4. **Check the definition of `SHIPPING_CENTS`** – ensure the keys are lower‑case and that the API documentation (or client code) either normalises input or that the validation is case‑insensitive. If not, consider normalising (`shipping.lower()`) before the membership test.  

5. **Locate the implementations of `Database.one` and `Database.execute`**:  
   * Confirm they raise on failure and that they do not silently swallow errors.  
   * Verify they are used consistently for all write‑heavy operations (stock updates, order creation).  

6. **Confirm that the `metadata` table is populated correctly** after `initialize`. The code expects a row with key `"schema"`; ensure that the helper methods create it if missing and that the stored `SCHEMA_VERSION` matches the constant used elsewhere.  

Addressing the items above will reduce the risk of incorrect order totals, misplaced discounts, and inventory inconsistencies.