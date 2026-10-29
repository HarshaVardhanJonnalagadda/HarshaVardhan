# Section review results

Run outcome: failed

These are separate model reviews of source sections. They are not a consolidated assessment. Cross-section behavior may be unresolved and duplicate findings may appear. Human validation is pending.

# Section 1: original lines 1-186

## Findings

| Severity | Title | Evidence | What the code does | Why it may affect totals / stock |
|----------|-------|----------|--------------------|---------------------------------|
| **Medium** | **`read_json` does not handle a missing file** | Lines **126‑133**:<br>`def read_json(path: Path) -> dict[str, Any]:`<br>`    if path.stat().st_size > 100_000:`<br>`        raise ServiceError(\"Request file exceeds 100000 bytes\")`<br>`    try:`<br>`        value = json.loads(path.read_text(encoding=\"utf-8\"))`<br>`    except (UnicodeError, json.JSONDecodeError) as exc:`<br>`        raise ServiceError(\"Request must be a UTF‑8 JSON document\") from exc` | The function calls `path.stat()` and `path.read_text()` **without** first checking that the file exists. If the supplied path does not exist, Python raises `FileNotFoundError`, which propagates out of `read_json` as an unhandled exception. | A checkout, catalog import, or any command that reads a JSON request will abort with a traceback instead of returning a controlled `ServiceError`. The caller will not get a chance to roll back a transaction, release any reserved stock, or compute a total. This can leave the database in an inconsistent state (e.g., a partially‑created order) and break the “stock must not be partially reserved” rule. |

## Uncertainty

| Issue | Reason |
|-------|--------|
| **Validation of `shipping` values** – The `CheckoutRequest` dataclass stores a raw `shipping` string, but this fragment does not show any validation against the allowed keys (`"standard"`, `"express"`, `"pickup"`). If later code indexes `SHIPPING_CENTS[request.shipping]` without validation, a `KeyError` could abort the checkout and affect totals. | The validation (or lack thereof) may be performed in code that is not included in this section. Without seeing that code we cannot definitively label it a defect. |
| **Coupon field validation** – Similar to `shipping`, the `coupon` field is stored unchanged. If later logic assumes a particular format or existence in the `coupons` table, an unexpected value could cause a database error that aborts total calculation. | The relevant logic is outside the supplied fragment. |

## Next checks

1. **Inspect callers of `read_json`** – Verify that they either catch `FileNotFoundError` or that the function is wrapped in a higher‑level handler that converts it to a `ServiceError`. If not, add an explicit existence check (`if not path.is_file(): raise ServiceError(...)`) before `path.stat()`.

2. **Search for the use of `CheckoutRequest.shipping`** – Locate the function that computes the order total and creates the order record. Confirm that it validates the shipping method against `SHIPPING_CENTS` (or handles a missing key gracefully). If validation is missing, add a check similar to `if shipping not in SHIPPING_CENTS: raise ServiceError(...)`.

3. **Search for the use of `CheckoutRequest.coupon`** – Ensure that coupon IDs are validated (existence, format, expiry, usage limits) before they are applied to the merchandise subtotal. Missing validation could cause the checkout to fail mid‑transaction, leaving stock reserved.

4. **Review transaction handling around checkout** – Confirm that any exception raised while reading the request or during total calculation triggers a rollback of any stock reservations, preserving the “no partial reserve” rule.

5. **Run a test where the JSON request file is absent** – Observe whether the program exits with a traceback or returns a user‑friendly error message. This will confirm whether the defect identified in (1) is present in practice.

---

# Section 2: original lines 177-344

## Findings
**No supported defects were found in the supplied fragment that can directly cause incorrect order totals or stock handling.**  

All validation that is present (cart line count, duplicate‑SKU check, shipping method validation, non‑empty string checks, coupon normalisation) is implemented in the shown code.  The calculations of subtotals, discounts, tax, shipping, and the reservation of product stock are performed elsewhere, so this section does not contain evidence of a bug that would change totals or stock.

## Uncertainty
| Area | Why it is uncertain | What is needed |
|------|---------------------|----------------|
| `CartLine.from_dict` | Quantity positivity and SKU existence are validated there, but the code is not included in this fragment. | Review the implementation of `CartLine.from_dict` to confirm that it enforces a positive integer quantity and that the SKU refers to an existing product. |
| Total‑calculation logic (`Quote`, order creation, stock reservation) | The snippet defines the data structures (`PricedLine`, `Quote`) but does not contain the functions that compute `subtotal_cents`, `discount_cents`, `tax_cents`, `shipping_cents`, or that update inventory. | Examine the functions that build a `Quote` from a `CheckoutRequest` and the code that writes order lines and inventory events to the database. |
| Transaction handling | `Database.__init__` opens the SQLite connection with `isolation_level=None` (autocommit). If later code relies on explicit transactions for atomic stock reservation, this setting could interfere. | Check the surrounding code that performs stock reservation and order insertion to see whether it starts explicit transactions (`BEGIN`, `COMMIT`) and whether the autocommit mode is appropriate. |
| `Database.initialize` – missing `SCHEMA_VERSION` definition | The fragment references `SCHEMA_VERSION` but its value is not shown. If the constant is incorrect or missing, schema‑version checks could behave unexpectedly. | Verify the definition of `SCHEMA_VERSION` and ensure it matches the version stored in the `metadata` table. |

## Next checks
1. **Inspect `CartLine.from_dict`** – confirm it validates that `quantity` is a positive integer and that the SKU exists in the `products` table.
2. **Locate the pricing routine** that creates a `Quote` (or similar) from a `CheckoutRequest`. Verify:
   * Subtotal is computed as `unit_price_cents * quantity` for each line.
   * Discount is applied correctly respecting coupon rules.
   * Tax is calculated as 10 % of the discounted merchandise, rounded half‑up.
   * Shipping cost logic (free over 10 000 cents, standard vs. express vs. pickup) follows the business rules.
3. **Review stock‑reservation code** that runs inside the checkout flow. Ensure:
   * All requested quantities are reserved in a single atomic operation.
   * No partial reservation occurs on failure.
   * Re‑using the same `request_id` with identical input returns the existing order without additional reservation.
4. **Examine transaction boundaries** around order creation, inventory events, and coupon‑use updates. Confirm that the autocommit mode (`isolation_level=None`) does not allow intermediate states that could leave stock inconsistent.
5. **Check cancellation and refund paths** for proper idempotency (stock is returned only once, refunds cannot exceed total paid). These sections are not in the current fragment but are critical for total‑accuracy.

---

# Section 3: original lines 333-475

## Findings
**No supported defects were found in the supplied fragment.**  
All statements that affect totals or stock (price updates, restocking, low‑stock queries, and the transaction helper) contain the expected validation calls and are wrapped in a transaction that either commits or rolls back on error. The code shown does not contain any logic that could mis‑calculate a monetary total or corrupt the inventory quantity.

## Uncertainty
| Area | Why it is uncertain | What is needed |
|------|---------------------|----------------|
| `integer(...)`, `nonempty(...)`, `canonical_json(...)`, `timestamp(...)` | These helper functions are called to validate numeric ranges, non‑empty strings, JSON canonicalisation and datetime → integer conversion, but their implementations are not included. A bug in any of them could let an invalid price, quantity, or timestamp slip through and affect totals or stock. | The source of each helper function (or its contract) to confirm that it enforces the required bounds and formats. |
| Order‑related logic (checkout, reservation, cancellation, refunds, shipping) | The business‑critical rules for reserving stock, preventing partial reservations, handling duplicate request IDs, and ensuring refunds do not exceed paid amounts are implemented elsewhere. This fragment only provides low‑level DB helpers; a defect in those higher‑level services could still corrupt totals or inventory. | The sections that implement `OrderService` (or equivalent) – especially the methods that create, cancel, ship, and refund orders – and any code that calls `Database.transaction()`, `Database.audit()`, or `Database.inventory_event()` from those services. |
| Concurrency handling for stock updates | The `restock` method runs inside a SQLite `BEGIN IMMEDIATE` transaction, which acquires a write lock, but the rest of the system may perform stock deductions (e.g., during checkout) without the same locking strategy. Without seeing those paths we cannot be sure that race conditions cannot lead to negative stock or double‑counted reservations. | The code that decrements `products.stock` when an order is placed/reserved, and the surrounding transaction/locking strategy. |

## Next checks
1. **Validate helper functions** – locate the definitions of `integer`, `nonempty`, `canonical_json`, and `timestamp` and verify that they enforce the ranges and formats required by the business rules (e.g., price ≥ 0, quantity ≥ 1, timestamps in UTC).  
2. **Review order‑processing flow** – examine the service that creates orders, reserves inventory, applies coupons, calculates tax/shipping, and records the order lines. Ensure that:
   * The merchandise subtotal is computed as `unit_price * quantity` for each line.
   * Discounts, tax (10 % rounded half‑up), and shipping rules are applied exactly as specified.
   * Stock is only decremented after a successful reservation and that the reservation is rolled back on any failure.
   * Duplicate checkout request IDs are handled idempotently.
3. **Check cancellation and refund logic** – confirm that:
   * Cancelled orders restore the exact quantity that was reserved, and that repeated cancellations do not add stock again.
   * Refunds cannot exceed the total amount paid and that repeated refund request IDs are ignored.
4. **Inspect concurrency controls** – verify that any code that modifies `products.stock` (checkout, cancellation, restock) uses the same `BEGIN IMMEDIATE` transaction pattern or another mechanism that prevents overlapping writes from producing inconsistent stock levels.  
5. **Audit event consistency** – ensure that every stock‑changing operation records an `inventory_event` with the correct `delta` and optional `order_id`, so that later reports can reconstruct the ledger accurately.  

By following these steps you can confirm that the parts of the system not shown here do not introduce bugs that would alter monetary totals or inventory quantities.

---

# Section 4: original lines 463-591

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

---

# Section 5: original lines 591-699

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancel is not idempotent – repeated cancellations restock inventory** | `cancel` method, lines **0622‑0637**<br>`for line in self.db.lines(order_id): … self.db.execute("UPDATE products SET stock = stock + ?, …")` |
| **Medium** | **`_insert_order` stores raw `quote.coupon` object in DB column `coupon`** | `_insert_order`, lines **0592‑0602**<br>`(order_id, request.customer_id, request.request_id, request.fingerprint(), "placed", request.shipping, quote.coupon, …)` |

### 1. Cancel is not idempotent – repeated cancellations restock inventory  
**Evidence (SUPPORTED IN SUPPLIED CODE)**  

- The method begins by validating `reason` and opening a transaction (lines 0624‑0625).  
- It fetches the order (`order = self.db.order(order_id)`).  
- It only blocks cancellation when the order status is **`"shipped"`** (lines 0626‑0627).  
- If the status is anything else (including `"cancelled"`), the code proceeds to **add the line quantities back to product stock** (lines 0628‑0632) and records an inventory event.  
- Finally it updates the order status to `"cancelled"` (lines 0634‑0635).  

**What the code demonstrably does**  
When `cancel` is called on an order whose status is `"cancelled"` (i.e., a second cancellation request), the guard does **not** stop execution. The loop over `self.db.lines(order_id)` runs again, executing `stock = stock + line.quantity` for each line, thereby **inflating the product stock**. The audit record is also written a second time.

**How that behavior could change totals or stock**  
- Stock levels become higher than the true physical inventory, breaking the business rule *“Repeating cancellation must not add stock again.”*  
- Subsequent checkout attempts could succeed because the system believes more items are available than actually are, leading to overselling.

**Assumptions / Missing cross‑function evidence**  
- The snippet does not show any higher‑level guard that might prevent a second call to `cancel`. If such a guard exists elsewhere, the bug would be mitigated, but based solely on the supplied code the method itself is unsafe.  

**What should be checked next**  
- Search the codebase for any wrapper or service that calls `cancel` and ensures it is only invoked once per order.  
- Verify whether the `orders` table has a unique constraint or trigger that prevents multiple rows with status `"cancelled"` for the same `order_id`.  
- Add a check `if order["status"] == "cancelled": raise Conflict("Order already cancelled")` (or make the operation a no‑op) to guarantee idempotency.

### 2. `_insert_order` stores raw `quote.coupon` object in the `coupon` column  
**Evidence (SUPPORTED IN SUPPLIED CODE)**  

- In the `INSERT INTO orders` statement (lines 0595‑0602) the seventh placeholder receives `quote.coupon`.  
- The column name is `coupon`, which in a typical relational schema would be a **string or foreign‑key identifier**, not a Python object.

**What the code demonstrably does**  
It attempts to bind whatever Python value `quote.coupon` holds (likely a `Coupon` dataclass or `None`) directly to the SQLite parameter. SQLite will store the Python object's string representation, which may be opaque or inconsistent.

**How that behavior could change totals or stock**  
- Later queries that expect a coupon code (e.g., to enforce “maximum uses” or “expiry”) may read an unexpected value, causing the coupon logic to be bypassed or applied incorrectly.  
- Mis‑recorded coupon data can affect discount calculations in reports, leading to inaccurate gross‑sales totals.

**Assumptions / Missing cross‑function evidence**  
- The definition of the `orders` table and the type of the `coupon` column are not shown. If the column is declared as `BLOB` and the code elsewhere serialises/deserialises the object, this may be intentional.  
- The `Quote` class’s `coupon` attribute type is unknown; it could already be a string identifier.

**What should be checked next**  
- Inspect the database schema for the `orders.coupon` column type.  
- Review the `Quote` class to see what `quote.coupon` contains.  
- Confirm that any later code that reads `orders.coupon` correctly interprets the stored value.  
- If the column is meant to store a coupon code, change the insertion to `quote.coupon.code` (or similar) and ensure `None` is stored when no coupon is applied.

## Uncertainty
- **Idempotency of `cancel`** – It is unclear whether external logic prevents a second call. Until the surrounding call‑graph is examined, we cannot definitively label this as a guaranteed defect, but the method itself is unsafe.  
- **Type of `orders.coupon` column** – Without the schema or `Quote` definition, we cannot assert that storing `quote.coupon` is wrong; it may be intentional serialization.

## Next checks
1. **Search for other usages of `cancel`** – Look for service‑level wrappers, API endpoints, or higher‑level transaction code that might enforce a single‑cancellation rule.  
2. **Review the database schema** – Confirm the data type of `orders.coupon` and whether it expects a scalar value.  
3. **Inspect the `Quote` and `Coupon` classes** – Determine the exact type/value of `quote.coupon`.  
4. **Audit inventory event handling** – Ensure that `self.db.inventory_event` correctly records the source of stock changes and that no other path can double‑count a cancellation.  
5. **Run static analysis for other idempotency patterns** – Check `ship` and `refund` for similar repeat‑request handling (e.g., duplicate request IDs).  

Addressing the cancellation idempotency issue will prevent stock inflation, which is the most critical bug related to totals and inventory in the provided fragment.

---

# Section 6: original lines 694-828

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are included in sales totals** | `ReportingService.sales` (lines 0710‑0734) – the query<br>`SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS gross_cents, … FROM orders WHERE created_at >= ? AND created_at < ?` does **not** filter out orders whose `status = 'cancelled'`. The business rules state: *“Exclude cancelled orders from order counts and gross sales.”* The function later computes `net_cents = gross_cents - refunded_cents`, so the inflated `gross_cents` propagates to the reported net sales. |
| **Medium** | **Average order amount uses Python’s bankers‑rounding, not “round half up”** | `ReportingService.sales` (line 0732) – `result["average_order_cents"] = round(result["gross_cents"] / count) if count else 0`<br>Python’s built‑in `round` implements “round‑to‑even”. The specification for tax rounding (and generally for monetary values) requires *half‑up* rounding. If the average is expected to be presented with the same rounding rule, the current implementation may produce a value that is off by one cent for .5 cases. |
| **Low** | **`date_bounds` builds ISO‑8601 strings by concatenating a suffix** | `ReportingService.date_bounds` (lines 0700‑0708) – `return first.isoformat() + "T00:00:00+00:00", after.isoformat() + "T00:00:00+00:00"`<br>`first` and `after` are `date` objects; `isoformat()` yields `"YYYY‑MM‑DD"`. Concatenating the suffix works, but it relies on the caller never passing a `datetime` object. If the implementation of `parse_day` were to change to return a `datetime`, the resulting string would contain an extra time component (e.g., `"2023‑01‑01T00:00:00+00:00T00:00:00+00:00"`). This could break date filtering in all reporting queries. |
| **Low** | **`export_orders` does not validate that the requested date range is non‑empty** | `ReportingService.export_orders` (lines 0784‑0800) – after calling `date_bounds`, the function proceeds even if `start` and `end` represent the same day (resulting in an empty result set). While not a correctness error per se, the business rule for reports expects a *valid* range; an empty export may be surprising to callers. |

### Evidence status
All findings are **SUPPORTED IN SUPPLIED CODE** – the problematic statements are present in the excerpt.

## Uncertainty

| Issue | Reason |
|-------|--------|
| Definition of `VALID_STATUSES` | Not shown in this fragment; we assume it contains `'cancelled'` among other statuses, but the exact set is unknown. |
| Behaviour of helper functions (`parse_day`, `integer`, `ServiceError`) | Their implementations are outside the provided section, so we cannot confirm they enforce the required validation (e.g., date format, limit bounds). |
| Database schema for `orders.total_cents` | We assume `total_cents` already includes discount, tax, and shipping as per the business rules, but the schema is not visible here. |
| Whether refunds are ever linked to cancelled orders | The refund query joins `orders` without a status filter; if the system ever creates refunds for cancelled orders, the current logic would double‑count them. This cannot be verified without seeing the refund creation code. |

## Next checks

1. **Verify sales query filtering** – Confirm that cancelled orders must be excluded from the `sales` report and adjust the SQL to `WHERE created_at >= ? AND created_at < ? AND status != 'cancelled'`.  
2. **Confirm rounding policy for averages** – If the specification requires half‑up rounding for monetary values, replace `round(...)` with a helper that implements that rule (e.g., `Decimal(...).quantize(Decimal('1'), rounding=ROUND_HALF_UP)`).  
3. **Inspect `parse_day` implementation** – Ensure it always returns a `date` object; if it may return a `datetime`, refactor `date_bounds` to build the timestamp using `datetime.combine` instead of string concatenation.  
4. **Check `export_orders` edge cases** – Determine whether an empty result set is acceptable or if the function should raise an error when `lower == upper`.  
5. **Review refund creation flow** – Ensure refunds cannot be issued for orders whose status is `'cancelled'`, or add a status filter to the refunds query in `sales`.  
6. **Validate `VALID_STATUSES` includes all expected statuses** – Especially `'cancelled'`, to guarantee `status_counts` reports correctly.  

Addressing the high‑severity inclusion of cancelled orders will bring the sales totals in line with the business rules and prevent overstated revenue figures. The other items are lower‑severity but may affect monetary rounding consistency and robustness of date handling.

---

# Section 7: original lines 814-881

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Partial import may leave the system in an inconsistent state** | `import_orders` – lines 857‑879<br>```python\n857: def import_orders(db: Database, path: Path, now: datetime) -> dict:\n858:     if path.stat().st_size > 1_000_000:\n859:         raise ServiceError(\"Import exceeds 1000000 bytes\")\n860:     service = OrderService(db)\n861:     accepted = []\n862:     rejected = []\n863:     with path.open(encoding=\"utf-8\") as stream:\n864:         for number, line in enumerate(stream, 1):\n865:             ...\n874:             try:\n875:                 value = json.loads(line)\n876:                 ...\n877:                 order = service.checkout(request, now)\n878:                 accepted.append({\"line\": number, \"order_id\": order[\"order_id\"]})\n879:             except (ServiceError, json.JSONDecodeError) as exc:\n880:                 rejected.append({\"line\": number, \"error\": str(exc)})\n```<br>**What the code does** – The function reads a line‑by‑line JSON‑L file, calls `OrderService.checkout` for each line, and records the result. Only `ServiceError` and `json.JSONDecodeError` are caught; any other exception (e.g., `KeyError`, database errors, programming bugs) propagates out of the loop and aborts the import.<br>**Why this can affect totals/stock** – `checkout` creates an order and reserves stock. If an unexpected exception occurs after some orders have been successfully processed, the function stops processing the remaining lines, leaving the earlier orders committed. The caller receives a partially‑filled result dict, but the import operation is considered “failed” from the caller’s perspective, which may lead to duplicate re‑imports or manual retries that double‑reserve stock and inflate totals.<br>**Assumptions / missing context** – We assume `OrderService.checkout` commits its changes inside its own transaction (common pattern). The surrounding code does not start a surrounding transaction that could roll back all processed lines on failure.<br>**What to check next** – Verify whether `OrderService.checkout` runs in its own transaction and whether the import routine is expected to be atomic. If atomicity is required, wrap the whole loop in a transaction or catch a broader set of exceptions and roll back any partial work. |

| **Medium** | **`seed_demo` treats any existing metadata row as “already seeded”** | `seed_demo` – lines 835‑839<br>```python\n835: def seed_demo(db: Database, now: datetime) -> dict:\n836:     with db.transaction():\n837:         if db.one(\"SELECT value FROM metadata WHERE key = 'seeded'\"):\n838:             return {\"seeded\": False, \"message\": \"Demo data already exists\"}\n```<br>**What the code does** – It queries the `metadata` table for a row with key `'seeded'`. If the query returns any truthy value, the function aborts seeding and reports that demo data already exists.<br>**Why this can affect totals/stock** – The check does not verify the *value* of the row (e.g., a timestamp). If a previous run inserted the row but failed part‑way (e.g., only some customers were added), a subsequent call will think the demo data is fully present and skip inserting the missing products or coupons. This can leave the database with incomplete product rows and therefore incorrect initial stock levels, which later order calculations will use.<br>**Assumptions / missing context** – We assume `db.one` returns `None` when no row exists and a non‑`None` value otherwise. The exact schema of `metadata` is not shown, but the code only cares about existence, not content.<br>**What to check next** – Inspect the `metadata` table schema and the semantics of the `'seeded'` key. Consider storing a flag that indicates successful completion (e.g., a boolean) or performing a more robust “already seeded” detection (e.g., count of expected rows). |

## Uncertainty
*None* – All identified issues are directly supported by the supplied fragment.

## Next checks
1. **Transaction scope for `import_orders`** – Look at `OrderService.checkout` and the surrounding database handling to see whether each checkout is committed independently. If the import is required to be all‑or‑nothing, add a top‑level transaction around the loop or catch a broader exception set and roll back on failure.
2. **Error handling policy** – Determine whether other exception types (e.g., `IntegrityError`, custom validation errors) can be raised during checkout. If so, extend the `except` clause or add a generic `except Exception` that records the failure and aborts safely.
3. **`seed_demo` completion flag** – Review the `metadata` table definition and any code that clears or updates the `'seeded'` entry. Decide whether a simple existence check is sufficient or if a more explicit “seed completed” marker is needed to avoid partial seeding.
4. **Idempotency of demo seeding** – Verify that repeated calls to `seed_demo` do not create duplicate rows (e.g., unique constraints on `customer_id`, `sku`, `code`). If duplicates are possible, the early‑return may mask integrity violations.

---

# Section 8: original lines 880-980

## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Missing validation of restock quantity sign** | `0915‑0918` –<br>`restock = commands.add_parser(\"restock\")`<br>`restock.add_argument(\"sku\")`<br>`restock.add_argument(\"--quantity\", type=int, required=True)`<br>`restock.add_argument(\"--reason\", required=True)` |

**Evidence status:** SUPPORTED IN SUPPLIED CODE.  

**What the supplied code demonstrably does**  
The CLI parser defines a `restock` sub‑command that requires a `--quantity` argument of type `int`. No further constraints (e.g., `choices`, `type=lambda x: int(x) if int(x) > 0 else argparse.ArgumentTypeError`) are applied, so any integer – positive, zero, or negative – will be accepted by the parser.

**How that behavior could cause the reported problem**  
The business rule *“Checkout must reserve the requested quantities and create the order together, or do neither. A stock shortage must not partially reserve a cart.”* and the related inventory rules assume that a **restock** operation only **adds** stock. If a caller supplies a negative quantity, the downstream handler (not shown in this fragment) will likely add the supplied value to the current inventory count, effectively **subtracting** stock. This can corrupt inventory totals, allow overselling, and produce incorrect order‑fulfilment decisions.

**Assumptions / missing cross‑function evidence**  
* The implementation of the `restock` command (the function that receives the parsed arguments and updates the database) is not present in the supplied fragment. The finding assumes that the handler uses the parsed `quantity` value directly to adjust inventory (e.g., `stock += quantity`). If the handler contains its own guard against negative values, the bug would be mitigated, but that guard is not visible here.

**What should be checked next**  
1. Locate the function that processes the `restock` command (likely something like `def restock(db, sku, quantity, reason): …`). Verify whether it validates that `quantity > 0` before applying the change.  
2. If the validation is missing there, add a check either in the parser (e.g., `type=lambda x: int(x) if int(x) > 0 else argparse.ArgumentTypeError('quantity must be positive')`) or in the command handler, raising a clear `ServiceError` for non‑positive values.  
3. Add unit tests that attempt to restock with `--quantity -5` (or `0`) and assert that the operation is rejected and that inventory levels remain unchanged.  

---

## Uncertainty

| Area | Why uncertain |
|------|----------------|
| **Restock implementation** | The fragment does not include the code that actually updates inventory. Without seeing that code we cannot definitively state that a negative quantity will be applied to stock. |
| **Other commands that accept numeric input** (e.g., `set-price --amount`, `refund --amount`) | The parser accepts strings for these arguments; validation may occur later. Their correctness with respect to totals cannot be confirmed from this section alone. |

These items should be examined in the surrounding sections of the source file.

---

## Next checks

1. **Inspect the restock handler** – confirm it does not accept negative quantities or, if it does, that it explicitly rejects them.  
2. **Review other numeric‑argument commands** (`set-price`, `refund`, `order`‑related commands) for similar missing positivity checks that could affect monetary totals or inventory.  
3. **Run integration tests** that simulate a full checkout‑cancel‑restock cycle, verifying that inventory never goes below zero and that order totals remain consistent after each operation.  

If the restock handler already validates the sign, the immediate risk is mitigated; otherwise, add the validation as described above.