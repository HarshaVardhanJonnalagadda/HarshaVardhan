# Section review results

Run outcome: failed

These are separate model reviews of source sections. They are not a consolidated assessment. Cross-section behavior may be unresolved and duplicate findings may appear. Human validation is pending.

# Section 1: original lines 1-188

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **`read_json` does not handle a missing file** | `0136‑0135` – `def read_json(path: Path) -> dict[str, Any]:`<br>`if path.stat().st_size > 100_000:` |
| **Low** | **`timestamp` discards sub‑second precision** | `0068‑0071` – `def timestamp(value: datetime) -> str:`<br>`return value.astimezone(timezone.utc).isoformat(timespec="seconds")` |
| **Low** | **`parse_time` silently accepts a “Z” that appears anywhere in the string** | `0058‑0065` – `def parse_time(value: str) -> datetime:`<br>`result = datetime.fromisoformat(value.replace("Z", "+00:00"))` |

### What the code demonstrably does  

1. **`read_json`** – Calls `path.stat()` before opening the file. If the supplied path does not exist (or the process lacks permission), `Path.stat()` raises `FileNotFoundError` / `PermissionError`. Those exceptions are not caught, so the program aborts with a traceback instead of raising a `ServiceError` that the CLI expects.  

2. **`timestamp`** – Converts a timezone‑aware `datetime` to UTC and formats it with `timespec="seconds"`. Any microsecond component is dropped, so two events that differ only by sub‑second timing will be stored with identical timestamps. This can affect ordering of events that rely on precise ordering (e.g., stock‑reservation race conditions).  

3. **`parse_time`** – Replaces every occurrence of the character `Z` with `+00:00` before feeding the string to `datetime.fromisoformat`. If a user supplies a malformed ISO string that contains a stray `Z` in the date part (e.g., `"2026-0Z-01T12:00:00+00:00"`), the replace will produce an invalid offset but `fromisoformat` will raise a `ValueError`, which is caught and re‑raised as a `ServiceError`. The replace is therefore overly permissive and may mask other format errors.  

### How the behavior could affect totals or stock  

* **Missing‑file handling** – Checkout, cancellation, or report commands read JSON request files. If a user accidentally points to a non‑existent file, the service crashes instead of returning a clean error. In a production‑like script that is wrapped in a transaction, an unexpected exception could leave a database transaction open, potentially causing partial stock reservations or duplicate order IDs.  

* **Timestamp precision loss** – Stock‑reservation and order‑shipping events are stored with timestamps. If two reservations occur within the same second, they will have identical timestamps. Later logic that orders events by timestamp (e.g., “process the earliest reservation first”) may treat them as simultaneous, which could lead to nondeterministic stock allocation and, consequently, incorrect stock counts.  

* **Over‑permissive `Z` replacement** – While unlikely to change totals directly, accepting malformed timestamps could let an attacker craft a request that bypasses the “must include a timezone” check, leading to ambiguous UTC conversion and possibly mis‑applied tax/shipping calculations that depend on the exact moment of checkout.  

### Assumptions / Missing cross‑function evidence  

* The snippet does **not** include the functions that actually compute merchandise subtotals, apply coupons, calculate tax, or update stock. Therefore we cannot confirm whether the rounding rules (half‑up) are applied consistently throughout the service.  

* We assume that later code stores timestamps produced by `timestamp()` and relies on their ordering for stock reservation; if timestamps are only used for display, the precision loss may be harmless.  

* The impact of the missing‑file exception depends on whether the caller wraps `read_json` in a `try/except ServiceError` block. If it does, the uncaught `FileNotFoundError` will still bubble up.  

## Uncertainty  

* **Whether the service wraps `read_json` calls in a generic `except Exception` block** – If it does, the crash may be caught and transformed into a user‑friendly error, mitigating the issue.  

* **How timestamps are used elsewhere** – If timestamps are never used for ordering or concurrency control, the loss of sub‑second precision may be irrelevant.  

* **Whether any later validation re‑checks the ISO‑format after `parse_time`** – The permissive `replace("Z", "+00:00")` could be harmless if all callers already provide well‑formed strings.  

## Next checks  

1. **Inspect all callers of `read_json`** – Look for `try/except` blocks that catch only `ServiceError`. Verify that missing‑file or permission errors are turned into `ServiceError` with a clear message.  

2. **Search for code that orders or compares events by the timestamp string** – If any logic depends on chronological ordering (e.g., stock reservation queue, report generation), evaluate whether second‑level granularity is sufficient.  

3. **Review the implementation of `CheckoutRequest.from_dict` and any functions that compute order totals** – Ensure they:  
   * Combine duplicate SKUs before calculating the merchandise subtotal.  
   * Apply the 10 % tax rounding rule exactly as specified.  
   * Enforce free‑shipping thresholds *after* discount.  
   * Use `percentage()` for tax and coupon discount calculations consistently.  

4. **Check the transaction handling around stock reservation** – Confirm that a failure (including unexpected exceptions) rolls back any partial updates to the `stock` column.  

5. **Validate that all monetary calculations use integer cents throughout** – Look for any accidental conversion to `float` that could introduce rounding errors.  

Addressing the above points will reduce the risk of incorrect totals or stock inconsistencies.

---

# Section 2: original lines 174-342

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Database opened in autocommit mode – no explicit transaction for checkout** | `Database.__init__` (lines 0325‑0332) – `sqlite3.connect(..., isolation_level=None, timeout=5)` |
| **Medium** | **`initialize()` does not insert a schema‑version record** | `Database.initialize` (lines 0337‑0342) – after creating tables it reads `metadata` but never writes the current `SCHEMA_VERSION` when the row is missing. |
| **Low** | **`CheckoutRequest.from_dict` silently accepts an unknown coupon code** | `CheckoutRequest.from_dict` (lines 0200‑0203) – the code is only upper‑cased; existence/validity is not checked here. |
| **Low** | **`Quote.to_dict` does not include a formatted representation of the subtotal, discount, tax, or shipping** | `Quote.to_dict` (lines 0228‑0231) – only `formatted_total` is added; other monetary fields are left as raw cents. This is not a bug per‑se, but downstream code that expects the same keys as the dataclass may mis‑display amounts. |

### What the code demonstrably does  

* **Autocommit mode** – By passing `isolation_level=None` to `sqlite3.connect`, each individual `execute`/`executemany` is committed immediately. No `BEGIN`/`COMMIT` block is started automatically.  
* **Schema version handling** – `initialize()` runs the schema script, then queries `metadata` for a key named `"schema"`. If the key is absent (`current` is `None`) the function simply returns; it never inserts a row with the current `SCHEMA_VERSION`.  
* **Coupon handling in request parsing** – The request parser upper‑cases the supplied coupon string but does **not** verify that the coupon exists, is active, or has remaining uses. Validation is presumably deferred to later business‑logic code.  
* **Quote dictionary conversion** – The `to_dict()` method builds a plain `dict` from the dataclass via `asdict(self)` and then adds a single extra key `formatted_total`. All other monetary fields remain as integer cents.  

### How the behavior could affect totals or stock  

| Finding | Potential impact on totals / stock |
|---------|------------------------------------|
| **Autocommit** – Checkout must *reserve stock* **and** *create the order* atomically. If the code that performs these steps issues two separate `INSERT/UPDATE` statements, a failure after the first statement (e.g., coupon validation, payment processing) will leave the stock reduced while no order record exists, or vice‑versa. This violates the rule “checkout must reserve the requested quantities **and** create the order together, or do neither.” |
| **Missing schema‑version row** – Later code that checks the stored version (e.g., during migrations or health checks) may treat the database as un‑initialized and refuse to run, potentially causing the service to reject all checkout attempts. While not directly altering totals, it can lead to a situation where the system falls back to a stale or inconsistent state. |
| **Unchecked coupon code** – If an invalid or expired coupon string passes the request parser, downstream discount logic might treat it as a valid coupon (e.g., applying a 0% discount) or raise an exception later. Inconsistent handling could cause the *discount* amount to be wrong, which directly changes the order total. |
| **Partial Quote dict** – Consumers of `Quote.to_dict()` that expect formatted strings for each monetary component might display the wrong values (e.g., showing the raw subtotal while the UI expects a formatted string). This is a presentation issue, not a calculation error, but could mislead users about the amount they are paying. |

### Assumptions / Missing cross‑function evidence  

* The checkout service code that actually updates `products.stock` and inserts rows into `orders` / `order_lines` is **not** shown in this excerpt. We assume it uses the `Database` wrapper’s `execute`/`executemany` methods without an explicit transaction block.  
* Coupon validation (existence, expiry, usage limits) is likely performed elsewhere; we cannot confirm whether the omission here leads to a double‑validation bug.  
* The `SCHEMA_VERSION` constant is defined elsewhere; we assume it is an integer. The impact of the missing metadata row depends on later code that reads it.  

## Uncertainty  

* **Atomicity of checkout** – Without seeing the checkout implementation, we cannot be certain that the autocommit setting actually results in a non‑atomic operation. The code may explicitly start a transaction (`BEGIN`) before the critical steps, which would mitigate the risk.  
* **Coupon validation location** – It is possible that coupon existence checks are performed *before* `CheckoutRequest.from_dict` is called, making the lack of validation here harmless.  
* **Quote formatting expectations** – If all callers use the raw cents fields and only need the formatted total, the missing formatted fields are benign.  

## Next checks  

1. **Inspect the checkout workflow** – Look for the function that:  
   * Retrieves product stock,  
   * Decrements `products.stock` (or inserts `inventory_events`), and  
   * Inserts the new order and its lines.  
   Verify whether it wraps these statements in an explicit `BEGIN … COMMIT` transaction or relies on the autocommit mode.  

2. **Search for explicit `BEGIN`/`COMMIT` usage** in the codebase (e.g., `Database.execute("BEGIN")`). If none exist around checkout, the autocommit setting is a definite bug.  

3. **Locate coupon validation logic** – Find where the coupon code from `CheckoutRequest` is looked up in the `coupons` table and its constraints (minimum spend, max discount, expiry, usage count) are enforced. Ensure that an invalid/expired coupon cannot slip through to the discount calculation.  

4. **Check any code that consumes `Quote.to_dict()`** – Determine whether UI or API layers expect formatted strings for `subtotal_cents`, `discount_cents`, `tax_cents`, and `shipping_cents`. If they do, add the missing formatted fields or adjust the consumer.  

5. **Verify schema‑version handling** – Search for code that reads the `"schema"` key from `metadata`. If it expects the row to exist, add an `INSERT OR REPLACE` of the current `SCHEMA_VERSION` in `Database.initialize()` when the key is missing.  

6. **Review any other database‑write paths** (order cancellation, shipment, refunds) to ensure they also respect atomicity and do not rely on autocommit for multi‑step updates.  

Addressing the high‑severity autocommit issue and confirming transaction boundaries will directly protect stock consistency and correct order totals. The lower‑severity items should be verified to avoid subtle presentation or version‑management problems.

---

# Section 3: original lines 328-466

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **`low_stock` returns the full product list instead of only low‑stock items** | `CatalogService.low_stock` – lines 0464‑0466 (excerpt):<br>`rows = self.db.all("SELECT sku, name, stock FROM products " )` |
| **Medium** | **`stock_history` may ignore the caller‑supplied `limit` on some SQLite versions** | `CatalogService.stock_history` – lines 0458‑0462 (excerpt):<br>`integer(limit, "limit", 1, 500)`<br>`rows = self.db.all("SELECT * FROM inventory_events WHERE sku = ? ORDER BY event_id DESC LIMIT ?", (sku, limit))` |
| **Low** | **`inventory_event` signature includes an optional `order_id` but many callers (e.g., `restock`) omit it, relying on the default** – if other code later expects a non‑NULL `order_id` for certain event types, the missing value could break downstream reporting. | `Database.inventory_event` – lines 0395‑0401; call site in `CatalogService.restock` – line 0453. |

### What the code demonstrably does  

1. **`low_stock`** builds a SQL string that selects *all* rows from `products` and never adds a `WHERE stock < ?` clause. The method therefore returns the complete product catalogue, not just those whose `stock` is below the supplied `threshold`.  

2. **`stock_history`** passes the `limit` value as a bound parameter to SQLite’s `LIMIT` clause. SQLite accepts a parameter for `LIMIT` in recent versions, but older releases (or certain PRAGMA settings) treat the `LIMIT` argument as a literal, causing the bound value to be ignored and the query to return *all* matching rows.  

3. **`inventory_event`** records an inventory change with columns `(sku, order_id, delta, reason, created_at)`. The `order_id` argument defaults to `None`. `restock` calls it without providing an `order_id`, so the column is populated with `NULL`. If later logic assumes that every inventory event tied to an order has a non‑NULL `order_id`, those assumptions could be violated.  

### How the behavior could affect totals or stock  

* **`low_stock`** is likely used by UI or automated alerts to warn when inventory is running low. Returning the full catalogue masks real shortages, leading to missed replenishment and eventual stock‑outs that affect order fulfillment and revenue.  

* **`stock_history`** is used for audit trails and reporting. If the `limit` is ignored, callers may receive far more rows than expected, potentially overwhelming UI components or causing performance regressions. Conversely, a caller that expects *exactly* `limit` rows may mis‑interpret the data, e.g., calculating average daily changes on an unintended larger set.  

* **`inventory_event`** with a missing `order_id` means that stock adjustments made by `restock` cannot be linked to a specific order (which is correct for a pure restock) but also means that any generic “inventory‑by‑order” report that groups on `order_id` will treat these rows as “unassociated”. If such a report is later used to reconcile stock levels, the discrepancy could be interpreted as a loss or ghost stock, skewing totals.  

## Uncertainty  

* The snippet ends at line 466; the remainder of `low_stock` is not shown. It is possible that a `WHERE` clause is appended in the missing lines, or that the method applies additional filtering after the query.  

* The exact SQLite version used by the application is unknown. If it is a modern version (≥ 3.25), the parameterized `LIMIT` works correctly; otherwise the `stock_history` limit may be ignored.  

* No call‑sites for `inventory_event` other than `restock` are visible in this excerpt. It is unclear whether other parts of the system (e.g., order reservation, cancellation) always supply an `order_id`.  

## Next checks  

1. **Inspect the rest of `CatalogService.low_stock`** (lines 466 +). Verify whether a `WHERE stock < ?` clause is added later or if the method filters the result in Python.  

2. **Determine the SQLite version bundled with the service** and confirm that bound parameters are allowed in the `LIMIT` clause. If older, consider rewriting the query to embed the limit as a literal (`... LIMIT {limit}`) after proper sanitisation.  

3. **Search the codebase for all calls to `Database.inventory_event`** and confirm that every event type that must be linked to an order supplies a non‑NULL `order_id`. Add validation or documentation if needed.  

4. **Review any reporting or alerting code that consumes `low_stock` and `stock_history`** to ensure they handle unexpected row counts gracefully and do not rely on the `limit` being honoured.  

5. **Run static analysis or unit‑test coverage for stock‑related paths** (order creation, reservation, cancellation, refund) to confirm that stock adjustments are always performed inside a `transaction` and that the `stock` column is never allowed to become negative or exceed any business‑defined maximum.  

Addressing the confirmed `low_stock` issue (adding the missing `WHERE stock < ?` clause) is the most critical step to prevent misleading stock alerts that could directly impact order fulfillment and revenue.

---

# Section 4: original lines 452-588

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

---

# Section 5: original lines 574-681

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancel is not idempotent – repeated cancellations inflate stock** | `cancel` (lines 0622‑0637) – the loop that adds back stock (`UPDATE products SET stock = stock + …`) is executed every time the method is called, even when the order is already in status **`cancelled`**. The only guard is `if order["status"] == "shipped": raise Conflict`, so a second call on a cancelled order will **add the same quantities again** and record another inventory event. |
| **Medium** | **Potential stock‑inconsistent order creation if a reserve fails after the order row is inserted** | `checkout` (lines 0575‑0590) inserts the order (`_insert_order`) **before** reserving each line (`_reserve_line`). If a later `_reserve_line` raises `Conflict`, the transaction should roll back, but this depends on the implementation of `self.db.transaction()`. If the transaction does **not** roll back on an exception, the order row would remain while stock was not fully reserved, leaving the system in an inconsistent state. |
| **Medium** | **Order‑ID collision risk** | `checkout` (line 0585) builds the public order identifier from the first 12 hex characters of `payload_hash(request.request_id)`. Two different request IDs could theoretically produce the same 12‑character prefix, causing a primary‑key conflict or overwriting an existing order. |
| **Low** | **No explicit check for empty cart** | `checkout` (line 0584) calls `self.pricing.quote(request, now)`. The business rule says an empty cart is invalid, but the snippet does not show any validation that `request.cart` contains at least one line before proceeding. If `quote` silently returns a zero‑subtotal, an order with zero totals could be created. |
| **Low** | **No verification that `request.fingerprint()` is stable** | `checkout` (lines 0580‑0581) compares the stored `request_hash` with `request.fingerprint()`. If the fingerprint includes non‑deterministic data (e.g., a timestamp), a repeat of the same logical request could be rejected as a conflict. |

### Why these behaviours matter for totals or stock  

* **Cancel idempotency** – Adding stock twice inflates the available inventory, allowing future orders to be fulfilled with more items than were ever purchased. This directly corrupts stock counts.  
* **Partial reserve after order insert** – If the order row persists while stock was not fully reserved, the order could later be shipped (or refunded) even though the inventory never existed, leading to negative stock or over‑selling.  
* **Order‑ID collision** – Two distinct orders could share the same `order_id`, causing later updates (e.g., shipments, refunds) to affect the wrong order, which would corrupt totals and stock accounting.  
* **Empty‑cart acceptance** – Creating an order with zero subtotal bypasses the “empty cart is invalid” rule and could generate spurious order records that affect reports and stock‑event logs.  
* **Unstable fingerprint** – Mis‑identifying a repeat request as a conflict could block a legitimate retry, forcing the client to create a new request ID and potentially double‑reserve stock.  

## Uncertainty  

| Area | What we don’t know from the supplied snippet | Why it matters |
|------|----------------------------------------------|----------------|
| **`self.db.transaction()` semantics** | Whether it automatically rolls back on any exception, and whether it commits only after the `with` block exits. | Determines if the “order‑insert‑then‑reserve” sequence is safe. |
| **Implementation of `self.pricing.quote`** | Whether it validates an empty cart, applies discounts, tax, and free‑shipping rules correctly, and whether it returns a deterministic `Quote` object. | Affects total calculations and the free‑shipping threshold. |
| **Definition of `request.fingerprint()`** | Which fields are included and whether any are non‑deterministic (e.g., timestamps). | Impacts repeat‑request handling and idempotency. |
| **Uniqueness constraints on `orders.order_id`** | Whether the database schema enforces a primary‑key/unique constraint on `order_id`. | Determines the real impact of a possible hash collision. |
| **Behavior of `self.db.audit` and `self.db.inventory_event`** | Whether they can raise exceptions that would abort the transaction. | Could affect the atomicity of the checkout flow. |

## Next checks  

1. **Inspect the transaction manager** (`self.db.transaction`) to confirm it rolls back on any exception and that the commit occurs only after the block finishes.  
2. **Review `cancel` logic** – add a guard that skips the restocking loop when `order["status"]` is already `"cancelled"` (or raise a conflict).  
3. **Validate order‑ID generation** – ensure the hash prefix length is sufficient for uniqueness or add a database‑level uniqueness check and a fallback on collision.  
4. **Examine `Quote` creation** – verify that it rejects an empty cart, correctly applies the 10 % tax rounding rule, and implements the free‑shipping threshold (≥ 10 000 cents after discount).  
5. **Check `request.fingerprint()` implementation** – confirm it only uses immutable request data (customer ID, cart contents, shipping method, coupon, etc.) and not timestamps or other volatile fields.  
6. **Confirm database schema** – ensure `orders.order_id` is a primary key/unique column and that `order_lines` have a foreign‑key to `orders`.  
7. **Run a scenario test** where an order is placed, cancelled, and then cancelled again to see whether stock is double‑added.  
8. **Simulate a checkout where the second line fails reservation** (e.g., insufficient stock) and verify that no order row remains after the exception.  

Addressing the high‑severity cancel‑idempotency issue and confirming the transaction atomicity will eliminate the most dangerous stock‑inconsistency bugs. The medium‑severity concerns should be verified next to ensure totals and identifiers remain reliable.

---

# Section 6: original lines 667-791

## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Cancelled orders are counted in sales totals** | `ReportingService.sales` – lines **0712‑0719** and **0720‑0725**. The `SELECT … FROM orders` query does **not** filter `status != 'cancelled'`, so cancelled orders contribute to `order_count`, `gross_cents`, `discount_cents`, `tax_cents`, and `shipping_cents`. The business rules explicitly state *“Exclude cancelled orders from order counts and gross sales.”* |
| **Medium** | **Refunds can be created with a non‑positive amount** | `ReportingService.refund` – line **0674‑0675** only checks that the requested amount does not exceed the remaining order total. There is no validation that `amount_cents` is **> 0**. A zero or negative amount would be recorded, altering the order’s financial history and potentially inflating net totals. |
| **Medium** | **Export may overwrite an existing CSV file** | `ReportingService.export_orders` – line **0786‑0788** checks that the *parent* directory exists but never checks whether `path` already points to an existing file. The specification requires *“must not overwrite an existing file.”* |
| **Low** | **Potential refund‑ID collision** | `ReportingService.refund` – line **0676** builds `refund_id` from `payload_hash(request_id)[:12]`. If two different `request_id`s happen to produce the same 12‑character prefix, the `INSERT` will raise a DB‑level conflict (or silently overwrite depending on schema). The code does not detect or handle this case. |

### What the code demonstrably does  

* **Sales query** – pulls *all* rows from `orders` within the date window, regardless of status.  
* **Refund creation** – accepts any integer `amount_cents` (including 0 or negative) as long as it does not exceed the remaining order total.  
* **Export** – proceeds to read orders and (presumably) write them to `path` without checking if the file already exists.  
* **Refund ID** – deterministically derives a 12‑character ID from the request ID; collisions are possible but not guarded against.

### How the behavior could change totals or stock  

* Including cancelled orders inflates `gross_cents`, `order_count`, and derived metrics (average order value, tax, shipping, etc.), giving a misleading picture of revenue.  
* A zero‑ or negative‑valued refund would *increase* the reported net sales (because `net_cents = gross_cents - refunded_cents` would subtract a non‑positive number).  
* Overwriting an existing export file could cause loss of previously generated reports, making audits impossible and potentially hiding discrepancies in stock or financial data.  
* A refund‑ID collision could either abort the refund (raising an integrity error) or, if the DB silently replaces the row, double‑count a refund and distort totals.

## Uncertainty  

| Area | Why the evidence is incomplete | What is assumed |
|------|--------------------------------|-----------------|
| **Idempotency of refunds** – The code returns the existing refund when the same `request_id` is reused *and* the `order_id` and `amount_cents` match. It is unclear whether the surrounding system guarantees that `request_id` is globally unique across all orders; if not, a duplicate `request_id` for a different order would raise a `Conflict`, which may be intended. | Need to see how `payload_hash` is defined and whether `request_id` is scoped per order. |
| **Export implementation** – The snippet stops after fetching rows; the actual CSV‑writing logic is not shown. It may already contain a check for existing files. | Assume the missing part does not perform an existence check. |
| **Database schema constraints** – We do not see the table definitions (e.g., UNIQUE constraints on `refund_id`). The collision risk for refund IDs depends on those constraints. | Assume `refund_id` is a primary key, so a collision would raise an error. |
| **Negative amount handling elsewhere** – There may be higher‑level validation before calling `refund`. | Assume the service method is the sole gatekeeper for the amount. |

## Next checks  

1. **Inspect the `sales` query** – Verify whether cancelled orders should be excluded elsewhere (e.g., a view or trigger). If not, add `WHERE status != 'cancelled'` to the SELECT.  
2. **Validate refund amount** – Look for any pre‑validation of `amount_cents`. If none, add a check `if amount_cents <= 0: raise Conflict("Refund amount must be positive")`.  
3. **Review export implementation** – Locate the code that writes the CSV file after line 7890. Ensure it checks `if path.exists(): raise ServiceError("File already exists")` before opening for write.  
4. **Examine `payload_hash` and DB schema** – Confirm the length and uniqueness guarantees of `refund_id`. If collisions are possible, consider using a longer hash or a UUID.  
5. **Search for other reporting functions** – Ensure that any other reports (e.g., inventory value, top products) also respect the “exclude cancelled orders” rule where appropriate.  
6. **Run unit tests** that create cancelled orders, issue refunds of zero/negative amounts, and attempt to export to an existing file to confirm the defects manifest.  

Addressing the high‑severity sales‑totals issue first will bring the financial reports back in line with the stated business rules. The medium‑severity items should be fixed next to prevent subtle data‑integrity problems.