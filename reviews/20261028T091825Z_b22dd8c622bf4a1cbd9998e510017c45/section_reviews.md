# Section review results

Run outcome: sections_complete

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

---

# Section 3: original lines 333-475

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Low** | **`restock` does not guard against overflow of the `stock` column** | `0450‑0455` – `self.db.execute("UPDATE products SET stock = stock + ?, …", (quantity, …))` |
| **Low** | **`inventory_event` signature is easy to misuse – the `order_id` argument is the *last* positional parameter** | `0395‑0401` – `def inventory_event(self, sku: str, delta: int, reason: str, now: datetime, order_id: str | None = None)` |
| **Low** | **`audit` may raise an exception if `detail` cannot be JSON‑encoded, causing the whole transaction (including stock changes) to roll back** | `0365‑0371` – `canonical_json(detail)` |
| **Low** | **`transaction` uses a plain `BEGIN IMMEDIATE` and will raise if a nested transaction is attempted** | `0354‑0364` – `self.execute("BEGIN IMMEDIATE")` |

### What the code demonstrably does  

* **`restock`** adds the supplied `quantity` to the `stock` column without checking the resulting value against any upper bound that the database schema might impose (e.g., an `INTEGER` column with a maximum). If a very large `quantity` is passed, the `UPDATE` could fail with an overflow error, leaving the stock unchanged while the caller believes it succeeded.  

* **`inventory_event`** expects `order_id` as the *fifth* argument. Calls that omit `order_id` (as `restock` does) work, but a future caller that supplies arguments positionally could unintentionally pass the `order_id` value as `now` and the datetime as `order_id`, leading to a malformed event record.  

* **`audit`** serialises `detail` with `canonical_json`. If `detail` contains a non‑JSON‑serialisable object (e.g., a `datetime` that wasn’t converted to a string), `canonical_json` will raise, aborting the surrounding transaction. The stock update performed just before the audit would then be rolled back, potentially leaving the caller with a false‑positive “restocked” response.  

* **`transaction`** starts a *single* SQLite transaction with `BEGIN IMMEDIATE`. If any code that runs inside the context manager tries to start another transaction (directly or via another `Database.transaction()` call), SQLite will raise `OperationalError`. The exception is caught, a `ROLLBACK` is issued, and the original exception is re‑raised – the outer caller sees the error, but the abrupt rollback could be surprising if the caller expected nested atomicity.  

## Uncertainty  

| Area | Why the evidence is incomplete | What is needed |
|------|-------------------------------|----------------|
| **Negative‑stock protection** | The fragment does not contain the code that *decrements* stock when an order is placed or reserved. It is unknown whether those paths enforce `stock >= quantity` before subtraction. | Review the order‑placement / reservation functions that call `self.db.execute("UPDATE products SET stock = stock - …")` and any validation that precedes them. |
| **Maximum‑stock limits** | The database schema (`products.stock` column type, constraints, triggers) is not shown. It is unclear whether the schema already enforces an upper bound that would cause the `UPDATE` in `restock` to fail safely. | Inspect the `SCHEMA` constant (the `CREATE TABLE products …` statement) for any `CHECK` constraints or triggers on `stock`. |
| **`canonical_json` implementation** | The behaviour of `canonical_json` (how it handles non‑serialisable values) is not provided. It may already coerce `datetime` objects to strings, mitigating the audit‑exception risk. | Look at the definition of `canonical_json` (or the utility module that provides it). |
| **Nested transaction usage** | No other parts of the codebase are shown. It is unknown whether any service method invokes `Database.transaction()` while already inside another transaction. | Search the whole project for `with self.db.transaction():` patterns and verify they are never nested. |
| **Error handling in `restock`** | The method returns `asdict(self.db.product(sku))` after the transaction commits. If the `UPDATE` succeeded but the subsequent `SELECT` fails (e.g., due to a schema change), the caller could receive an exception after the stock was already changed. | Confirm that `self.db.product(sku)` cannot raise under normal circumstances after a successful `UPDATE`. |

## Next checks  

1. **Inspect order‑placement / reservation logic** – ensure it checks `stock >= requested_quantity` *before* decrementing, and that it rolls back the transaction on shortage.  

2. **Review the `products` table definition** – look for `CHECK (stock >= 0)` or an upper‑bound `CHECK (stock <= …)`. If none exists, consider adding one to protect against overflow/underflow.  

3. **Examine `canonical_json`** – verify it safely serialises all audit `detail` structures used throughout the codebase (e.g., timestamps, Decimal objects). If it can raise, wrap the audit call or pre‑process the data to guarantee JSON‑compatibility.  

4. **Search for nested `transaction` usage** – if any service method may be called from within another transaction, refactor to use a single transaction scope or implement a re‑entrant transaction helper.  

5. **Add unit tests for extreme `restock` values** – test with a very large `quantity` (near the SQLite integer limit) and with a negative `quantity` (should be rejected by the `integer` validator). Verify that the database either updates correctly or raises a clear, caught exception without leaving the system in an inconsistent state.  

6. **Consider adding explicit overflow handling in `restock`** – after the `UPDATE`, fetch the new `stock` value and raise a domain‑specific error if it exceeds a business‑defined maximum (e.g., 1 000 000 units).  

These steps will give you confidence that stock adjustments cannot silently corrupt totals or inventory levels, and that audit logging will not unintentionally undo legitimate stock changes.

---

# Section 4: original lines 463-591

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

---

# Section 5: original lines 591-699

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancel is not idempotent – repeated cancellations restock inventory** | `cancel` (lines 0622‑0637) – the loop `for line in self.db.lines(order_id): … self.db.execute("UPDATE products SET stock = stock + ?, …")` runs **every** time `cancel` is called, even when the order is already in status *cancelled*. The only guard is `if order["status"] == "shipped": raise Conflict`, so a second call on a cancelled order will add the same quantities back to `products.stock` and write another audit entry. |
| **Medium** | **Missing guard against cancelling an already‑cancelled order** | Same function as above – after the first cancellation the order status is set to `'cancelled'` (line 0634). A subsequent call finds `order["status"] == "cancelled"` (which is *not* `"shipped"`), so it proceeds to restock again. |
| **Low** | **Potential double‑stock adjustment if the same SKU appears on multiple order lines** | `_reserve_line` (lines 0612‑0619) decrements stock per line, while `cancel` adds back per line (lines 0629‑0633). If earlier code does not collapse duplicate SKUs into a single line (business rule says it should), the net stock change is still correct, but the *idempotency* problem above could cause the same quantity to be added back multiple times. |
| **Low** | **`_insert_order` stores the raw `quote.coupon` object** | Line 0600 passes `quote.coupon` directly into the `orders` table. If the column expects a scalar (e.g., coupon code string) the DB driver may serialize the object implicitly or raise an error, potentially corrupting the stored coupon data and affecting later discount calculations. The fragment does not show the table schema, so the impact is uncertain. |

## Uncertainty  

| Area | Why the evidence is insufficient | What to verify |
|------|----------------------------------|----------------|
| **Idempotency of `cancel`** – The fragment does not show any outer guard (e.g., a request‑ID deduplication layer) that might prevent a second call from reaching the function. If such a guard exists, the double‑stock issue would be mitigated. | Need to inspect the public `cancel` endpoint or any wrapper that records request IDs. |
| **Schema of `orders.coupon` column** – Without the table definition we cannot know whether storing the whole `quote.coupon` object is valid. | Look at the `CREATE TABLE orders …` statement and the type of `quote.coupon`. |
| **Transaction handling for `_reserve_line` and the whole checkout flow** – The fragment shows `_reserve_line` alone; we do not see whether the caller wraps all line reservations in a single DB transaction. If not, a partial reservation could leave stock inconsistent. | Examine the checkout implementation that calls `_reserve_line` for each line. |
| **Whether duplicate SKUs are already collapsed before reaching `_reserve_line`** – The business rule requires consolidation, but the fragment does not show the code that builds `quote.lines`. | Review the code that builds the `Quote` object from the cart. |

## Next checks  

1. **Cancel idempotency** – Search for a higher‑level cancel API that validates a `request_id` or checks `order["status"]` before invoking `cancel`. If none exists, add a guard: `if order["status"] == "cancelled": return self.view(order_id)` (or raise a specific error).  
2. **Database schema for `orders.coupon`** – Verify the column type and ensure only a serializable value (e.g., coupon code string or JSON) is stored. If an object is being persisted, adjust the insertion to store a primitive representation.  
3. **Checkout transaction** – Locate the method that creates an order (likely `checkout`) and confirm that it:  
   * Begins a DB transaction,  
   * Calls `_reserve_line` for **all** lines before inserting the order, and  
   * Rolls back if any reservation fails.  
   If any step is missing, add proper transaction handling to avoid partial stock reservation.  
4. **SKU deduplication before reservation** – Review the code that builds `Quote.lines` from the cart to ensure repeated SKUs are merged into a single `PricedLine`. If not, add that step to prevent unnecessary multiple stock updates.  
5. **Audit of inventory events** – Check whether `self.db.inventory_event` enforces uniqueness (e.g., by request ID). If not, a duplicated cancel could create duplicate inventory events, making later reconciliation harder. Consider adding a unique constraint or idempotency token.  

Addressing the high‑severity cancel‑idempotency issue will stop stock from inflating when a cancellation request is retried, directly protecting the correctness of inventory totals. The other items are lower‑risk but still important for maintaining accurate financial totals and robust reporting.

---

# Section 6: original lines 694-828

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are included in sales totals** | `ReportingService.sales` – lines 0710‑0724. The query `SELECT … FROM orders WHERE created_at >= ? AND created_at < ?` does **not** filter out `status = 'cancelled'`. Business rules explicitly state *“Exclude cancelled orders from order counts and gross sales.”* Consequently `order_count`, `gross_cents`, `discount_cents`, `tax_cents`, `shipping_cents`, and the derived `average_order_cents` and `net_cents` can be inflated by cancelled orders. |
| **High** | **Refunds from cancelled orders are counted** | `ReportingService.sales` – lines 0720‑0725. The refund query joins `refunds r` to `orders o` but also lacks a `status != 'cancelled'` condition. If a cancelled order somehow has a refund record (or a refund is mistakenly linked), the `refunded_cents` will be subtracted from a gross that already includes the cancelled order, producing an incorrect net figure. |
| **Medium** | **`date_bounds` may allow a 367‑day inclusive range that exceeds the rule** | `ReportingService.date_bounds` – lines 0700‑0706. The rule says *“Report range must not exceed 367 days.”* The code checks `(last - first).days > 366`. For a non‑leap‑year, `first = 2023‑01‑01`, `last = 2024‑01‑01` gives a difference of **366** days, which passes the test and yields a 367‑day inclusive range (Jan 1 2023 … Jan 1 2024). This matches the rule, but the comment “must not exceed 367 days” is ambiguous; the implementation should be reviewed to confirm the intended inclusive/exclusive semantics. |
| **Low** | **`status_counts` silently drops unknown statuses** | `ReportingService.status_counts` – lines 0736‑0740. The result dict is pre‑filled with keys from `VALID_STATUSES`. If the `orders` table ever contains a status not listed there, the count for that status is omitted rather than reported as zero or flagged. This could hide data quality problems that affect stock‑related reporting (e.g., a stray “returned” status). |
| **Low** | **`export_orders` does not verify that the target path is a file, not a directory** | `ReportingService.export_orders` – lines 0784‑0799. The code only checks `path.parent.is_dir()`. If `path` itself points to an existing directory, `path.open("x")` will raise an exception, but the error message is not user‑friendly. This does not affect totals directly but could interrupt a reporting workflow. |

## Uncertainty  

| Area | Why the evidence is insufficient | What needs clarification |
|------|----------------------------------|--------------------------|
| **Definition of `total_cents`** in the `orders` table | The snippet does not show how `total_cents` is calculated when an order is created (whether it already includes discount, tax, shipping). Without that, we cannot be 100 % sure that the sales query’s omission of cancelled orders is the only problem affecting totals. | Inspect the order‑creation logic (e.g., `OrderService.place_order`) to confirm the composition of `total_cents`. |
| **Presence of a `status = 'cancelled'` row in the `refunds` join** | The refunds query joins on `orders` but we do not know whether the schema enforces that refunds can only reference non‑cancelled orders (e.g., via a foreign‑key constraint or application‑level check). | Review the refund‑creation code and any database constraints that prevent refunds on cancelled orders. |
| **Behavior of `parse_day`** | The date‑parsing helper is not shown; it could return a timezone‑aware `datetime` or a plain `date`. The string formatting with `+00:00` assumes UTC; mismatched types could cause off‑by‑one‑day errors in the report range. | Look at the implementation of `parse_day` and the storage format of `orders.created_at`. |
| **`VALID_STATUSES` definition** | We do not see the full list; it may already include all possible statuses, making the “unknown status” risk moot. | Examine the constant `VALID_STATUSES`. |

## Next checks  

1. **Order creation / total calculation** – Verify that `orders.total_cents` already reflects the full order total (subtotal − discount + tax + shipping). Ensure that cancelled orders are still stored with a total that should be ignored in reports.  

2. **Refund creation rules** – Confirm that the system prevents refunds on cancelled orders, either via application logic or a DB constraint. If such protection exists, the refund query may be safe; otherwise add `AND o.status != 'cancelled'` to the refunds SELECT.  

3. **`date_bounds` semantics** – Clarify the intended inclusive range. If the rule truly caps the *inclusive* span at 367 days, the current check is correct; otherwise adjust the comparison to `(last - first).days >= 367`.  

4. **`VALID_STATUSES` completeness** – Review the definition to ensure no legitimate status is omitted, or add a fallback to count unknown statuses for diagnostic purposes.  

5. **`parse_day` and timestamp storage** – Ensure that the ISO‑8601 strings produced by `date_bounds` match the format stored in `orders.created_at`. Mismatched timezones could cause orders to be excluded from a report unintentionally.  

6. **Export error handling** – Consider adding an explicit check that `path` is not an existing directory and provide a clearer error message.  

Addressing the high‑severity findings (excluding cancelled orders from the sales aggregates and from the refunds aggregate) will bring the reporting service in line with the business rules that directly affect totals and, indirectly, stock‑related decision‑making.

---

# Section 7: original lines 814-881

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Unexpected exceptions abort the whole import, leaving partially‑processed orders and possibly inconsistent stock** | `import_orders` (lines 857‑879) – the `try` block only catches `ServiceError` and `json.JSONDecodeError`. Any other exception (e.g., `KeyError`, database error, `AttributeError`) propagates out of the loop, terminating the function before the remaining lines are processed. If a previous line has already called `service.checkout`, stock may have been reserved while the import stops abruptly, violating the “checkout must reserve the requested quantities and create the order together, or do neither” rule. |
| **Low** | **No explicit transaction that groups the whole import; each successful checkout is committed independently** | `import_orders` (lines 857‑879) – the function creates an `OrderService` instance and calls `service.checkout` for each line, but there is no surrounding `db.transaction()` (or equivalent) that would roll back all changes if the import later fails. This can lead to a mixture of accepted and rejected orders in the same import run, which may be undesirable for reporting or for a bulk‑import operation. |
| **Low** | **Duplicate request‑ID handling is delegated to `OrderService.checkout` but not guarded here** | `import_orders` (lines 857‑879) – the loop does not check whether the same `request_id` appears on multiple lines. If the service implementation does not correctly enforce the “repeating the same checkout request ID with the same input returns the existing order; different input with the same ID is rejected”, the import could unintentionally reserve stock twice or raise an uncaught error. The current code cannot guarantee the business rule without seeing `OrderService.checkout`. |

## Uncertainty  

| Area | Why the impact is unclear | What is needed |
|------|---------------------------|----------------|
| **Exact behaviour of `OrderService.checkout`** – Whether it internally wraps the reservation‑and‑order‑creation steps in a single atomic transaction determines if a partially‑processed line can leave stock reserved without an order record. | The provided fragment does not include `checkout` implementation, nor does it show whether it raises only `ServiceError` for all validation failures. | Review the `checkout` method (and any helper it calls) to confirm that it either commits both reservation and order creation together or rolls back on any failure, and that it only raises `ServiceError` for expected validation problems. |
| **`db.inventory_event` side‑effects** – The seed function records an opening‑stock event, but we do not see the implementation of `inventory_event`. If it writes to a ledger without also updating the `products.stock` column, the initial stock could be out of sync. | No code for `inventory_event` is supplied. | Inspect `Database.inventory_event` to verify that it updates the product’s current stock (or that the stock column is otherwise kept consistent). |
| **Idempotency of the “seeded” flag** – The check `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` assumes the presence of a row means the demo data is already loaded, but it does not verify the row’s *value* (timestamp). If the row exists but the demo tables were cleared, the function would incorrectly skip seeding. | Not enough context about how the `metadata` table is used elsewhere. | Look at any code that may delete or truncate demo tables without clearing the metadata flag. |

## Next checks  

1. **`OrderService.checkout` implementation** – Verify that it:  
   * Performs reservation and order creation inside a single transaction.  
   * Rolls back the reservation if any validation (e.g., stock shortage, coupon misuse) fails.  
   * Raises only `ServiceError` for business‑logic failures so that the `import_orders` catch‑block handles them.  

2. **Database transaction handling in `import_orders`** – Decide whether the import should be all‑or‑nothing. If so, wrap the whole loop in `with db.transaction():` and ensure any exception triggers a rollback.  

3. **Idempotency of request IDs** – Confirm that `checkout` checks the request ID against prior orders and that duplicate IDs with differing payloads raise a `ServiceError`.  

4. **`Database.inventory_event` consistency** – Ensure that the opening‑stock event updates the product’s `stock` column (or that another mechanism keeps the ledger and the stock column in sync).  

5. **Error‑path coverage** – Test the import with malformed JSON, missing fields, and unexpected runtime errors (e.g., database connection loss) to see whether the function leaves the system in a consistent state.  

Addressing the points above will reduce the risk of incorrect totals or stock levels when bulk‑importing orders.

---

# Section 8: original lines 880-980

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

---

# Section 9: original lines 979-1060

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Negative quantity allowed in `restock` command** | `dispatch` – lines 1008‑1010: <br>`return catalog.restock(args.sku.upper(), args.quantity, args.reason, now)` |
| **High** | **Negative price allowed in `set-price` command** | `dispatch` – lines 1014‑1015: <br>`return catalog.update_price(args.sku.upper(), money_to_cents(args.amount), now)` |
| **Medium** | **Export command may overwrite existing CSV file** | `dispatch` – lines 1022‑1023: <br>`return reports.export_orders(args.output, args.start, args.end)` |
| **Medium** | **No explicit validation of request‑ID idempotency for checkout** | `dispatch` – lines 0990‑0994: <br>`request = CheckoutRequest.from_dict(read_json(args.request))`<br>`return orders.checkout(request, now)` |
| **Low** | **`args.sku.upper()` called without checking that `sku` is provided** | Several branches (e.g., lines 1009, 1011, 1015, 1017) use `args.sku.upper()` directly. If the CLI is invoked without `--sku`, `AttributeError` will be raised before the service can return a proper error. |

### What the code demonstrably does  

* The `dispatch` function simply forwards CLI arguments to service methods. It does **not** perform any range or sign checks on numeric arguments (`quantity`, `amount`).  
* For `restock` it passes the raw `args.quantity` value straight to `CatalogService.restock`.  
* For `set-price` it converts the supplied `args.amount` with `money_to_cents` and passes the result to `CatalogService.update_price`.  
* The `export` command forwards the output path to `ReportingService.export_orders` without any pre‑flight existence test.  
* Checkout requests are read from a JSON file and handed to `OrderService.checkout` without any local verification of request‑ID handling.  

### How that behavior could affect totals or stock  

* **Negative quantity** – If a user (malicious or mistaken) supplies a negative `quantity` to `restock`, the service will receive a negative delta and may **decrease** the inventory ledger, effectively “unstocks” items and can cause later order totals to be computed on a wrong stock level.  
* **Negative price** – Supplying a negative `amount` to `set-price` results in a negative price being stored. Subsequent order calculations will multiply quantity by this negative price, **reducing merchandise subtotals** and potentially producing a total that is lower than it should be (or even negative).  
* **CSV overwrite** – The business rule requires that an export must **not overwrite an existing file**. If `export_orders` does not guard against this, an existing report could be silently replaced, losing historical data that may be needed for audit or reconciliation of totals.  
* **Missing SKU check** – Calling `.upper()` on a missing `sku` raises an exception before the service can return a controlled error, potentially aborting a batch operation and leaving the system in an inconsistent state (e.g., a partially‑processed checkout that already reserved stock).  
* **Idempotency of checkout** – The CLI does not enforce the rule that a repeated checkout request ID with the same input must return the existing order without reserving more stock. If `OrderService.checkout` relies on the CLI to enforce this, duplicate reservations could occur, inflating reserved stock and causing later “stock‑shortage” errors.  

## Uncertainty  

* **Service‑level validation** – The implementations of `CatalogService.restock`, `CatalogService.update_price`, and `ReportingService.export_orders` are not shown. They may already reject negative values or check for file existence. Without that code we cannot definitively label the lack of CLI‑side checks as a bug; we can only note the risk.  
* **Argument parsing constraints** – The `argparse` configuration (not included) might define `type=int` with `choices=range(0, …)` or a custom `type=positive_int`. If such constraints exist, the negative‑value risk is mitigated.  
* **Checkout idempotency** – The idempotency rule may be fully enforced inside `OrderService.checkout`. The CLI’s lack of explicit handling is not necessarily a defect, but we need to verify that the service checks the request ID against stored orders.  

## Next checks  

1. **Inspect `CatalogService.restock`** – Verify that it validates `quantity` is a non‑negative integer and rejects negative deltas.  
2. **Inspect `CatalogService.update_price`** – Ensure it enforces `price >= 0` and that `money_to_cents` raises on negative inputs.  
3. **Inspect `ReportingService.export_orders`** – Confirm it checks `os.path.exists(output_path)` and refuses to overwrite, raising a clear error.  
4. **Review the `argparse` setup** – Look for `type=int` validators, `choices`, or custom `type=positive_int` for `quantity` and `amount`.  
5. **Examine `OrderService.checkout`** – Confirm it implements request‑ID idempotency and does not double‑reserve stock on repeated identical calls.  
6. **Check handling of missing `sku` arguments** – Ensure the CLI parser marks `--sku` as required for commands that need it, preventing the `AttributeError`.  

Addressing the above will close the most likely pathways that could corrupt order totals or inventory levels.