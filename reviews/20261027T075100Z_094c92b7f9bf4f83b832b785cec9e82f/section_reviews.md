   # Section review results

   Run outcome: sections_complete

   These are separate model reviews of source sections. They are not a consolidated assessment. Cross-section behavior may be unresolved and duplicate findings may appear. Human validation is pending.

   # Section 1: original lines 1-188

   ## Findings  

   | Severity | Title | Location & Code |
   |----------|-------|-----------------|
   | **Info** | No subtotal‑related logic in this section | Lines 1‑188 (the whole excerpt) – the file only defines utility helpers, data classes (`Customer`, `Product`, `CartLine`, `CheckoutRequest`) and validation functions. No function that *calculates* merchandise subtotal, tax, shipping or total appears here. |
   | **Info** | Potential source of later bugs – `CheckoutRequest.from_dict` not shown | Lines 0187‑0188 start the `from_dict` class‑method but the implementation is cut off. If that method mishandles the `lines` field (e.g., keeps only the first line, drops the `quantity`, or stores a single `CartLine` instead of a collection), the later order‑creation code could compute a wrong subtotal. |
   | **Info** | Quantity validation is correct but may be silently ignored later | `CartLine.from_dict` (lines 0171‑0176) validates `quantity` with `integer(..., 1, MAX_LINE_QUANTITY)`. The validation itself is fine; however, nothing in this excerpt shows that the validated `quantity` is actually used when the order total is computed. |

   **What the supplied code demonstrably does**  

   * Parses and validates JSON request files (`read_json`).  
   * Provides helpers for timestamps, money conversion, percentage calculation, and JSON canonicalisation.  
   * Defines immutable data classes for customers, products, cart lines, and checkout requests.  
   * Validates each `CartLine`’s `sku` (non‑empty, upper‑cased) and `quantity` (integer 1‑100).  

   **How that behavior could cause the reported problem**  

   If the missing implementation of `CheckoutRequest.from_dict` (or a later function that consumes the `lines` tuple) drops or collapses the three `CartLine` entries into a single line, the order‑creation logic would see only **one** MUG instead of three. That would produce a merchandise subtotal of `$10` (one unit at $10) and, after adding the 10 % tax (rounded up), a total of `$11`. This matches the user’s observed numbers.

   **Assumptions / Missing cross‑function evidence**  

   * The actual subtotal, tax, and total calculations are located in a later section of the source file (not provided).  
   * The bug, if any, resides in those later functions or in the incomplete `CheckoutRequest.from_dict`.  
   * No evidence in the current excerpt shows any arithmetic error, rounding mistake, or shipping‑cost mis‑application.

   ## Uncertainty  

   * **Exact cause of the $10 subtotal** – without seeing the order‑creation routine we cannot confirm whether the quantity is being ignored, whether the product price is read incorrectly, or whether a different part of the code (e.g., coupon handling) is mistakenly applied.  
   * **Whether the request JSON is being parsed correctly** – the shape of the incoming JSON (`lines` array) and how `CheckoutRequest.from_dict` transforms it are unknown.  
   * **Potential side‑effects from other modules** – inventory reservation, coupon lookup, or shipping‑method handling could also influence the final total, but those sections are not present.

   ## Next checks  

   1. **Locate the implementation of `CheckoutRequest.from_dict`** (the rest of the method after line 0188). Verify that it:  
      * Reads the `"lines"` array from the request JSON.  
      * Calls `CartLine.from_dict` for **each** element and stores the results in a tuple/list preserving all entries.  
      * Does **not** inadvertently keep only the first line or overwrite later lines.  

   2. **Find the function(s) that compute the order monetary values** – likely named something like `calculate_subtotal`, `apply_coupon`, `compute_tax`, `compute_total`, or similar. Examine:  
      * How the merchandise subtotal is summed (`price_cents * quantity`).  
      * Whether the loop iterates over **all** `CartLine`s.  
      * Whether the product price is fetched correctly from the `Product` table (no hard‑coded fallback).  

   3. **Check the tax calculation** – ensure it uses `TAX_BASIS_POINTS = 1000` (10 %) and rounds half‑up as required.  

   4. **Inspect shipping‑cost logic** – confirm that the `"pickup"` key maps to a zero‑cost entry in `SHIPPING_CENTS`.  

   5. **Run a mental test** (or add unit tests) with a request containing three identical lines for the same SKU, no coupon, and `"shipping": "pickup"` to see whether the subtotal becomes `3 * price_cents`.  

   6. **Review any deduplication or line‑combining code** – the business rules say “Combine repeated SKUs into one line.” Verify that such combination multiplies the quantity correctly rather than discarding extra units.  

   By examining those sections we can determine whether the observed $10 subtotal is due to a quantity‑handling bug, a price‑lookup error, or another mis‑implementation. Once the relevant code is inspected, a concrete defect (if any) can be identified and fixed.

   ---

   # Section 2: original lines 174-342

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

   ---

   # Section 3: original lines 328-466

   ## Findings
   **None in this section** – the code you provided (the `Database` class and `CatalogService` methods) does not contain any logic that computes an order’s merchandise subtotal, tax, shipping, or total. Those calculations are performed elsewhere (e.g., an `OrderService` or checkout routine), which is not part of the excerpt you shared. Consequently, no defect that could explain a subtotal of $10 for three $10 mugs can be demonstrated from the lines 328‑466.

   ## Uncertainty
   * The order‑creation path will read product data via `Database.product(sku)` (lines 0379‑0383) and will likely use `product.price_cents`.  
   * If the checkout code mistakenly uses the *stock* field or a cached price instead of `price_cents`, the subtotal could be wrong, but that code is not visible here.  
   * The `CatalogService.update_price` method (lines 0428‑0436) correctly updates `price_cents`, so the price stored in the DB should be accurate – the problem must lie in how the order service reads or aggregates that price.

   ## Next checks
   1. **Order/checkout implementation** – locate the function that:
      * Retrieves the product (`db.product(sku)`) for each cart line.
      * Multiplies `price_cents` by the line `quantity`.
      * Sums those values into the merchandise subtotal.
   2. **Quantity handling** – verify that the quantity supplied by the client is stored and used unchanged (no accidental truncation to 1, no integer‑division bug, etc.).
   3. **Tax calculation** – confirm the 10 % tax is applied to the *post‑discount* merchandise amount and rounded “half‑up” as specified.
   4. **Shipping cost logic** – ensure the “pickup” method sets shipping cost to 0 (the code that maps the shipping method to a cost is not in this excerpt).
   5. **Coupon/discount path** – even though no coupon was used, check that a default‑zero discount is applied and does not inadvertently reduce the subtotal.
   6. **Order‑line snapshot** – make sure the price saved on each `order_lines` row is the price at checkout, not a later catalog price.

   Inspect the modules that create orders, compute totals, and generate the order‑summary response. Those are the places where the $10‑subtotal bug is most likely to originate.

   ---

   # Section 4: original lines 452-588

   ## Findings  

   | Severity | Title | Location & Code |
   |----------|-------|-----------------|
   | **High** | **Subtotal calculated from unit price instead of line total** | `PricingService.quote` – line 0523: <br>`subtotal = sum(line.unit_price_cents for line in lines)` |
   | **Medium** | **Free‑shipping rule uses pre‑discount subtotal** | `PricingService.shipping_cost` – line 0514‑0515: <br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` |

   ### Subtotal mis‑calculation  
   *What the code does*  
   - `price_lines` (lines 0476‑0490) creates a `PricedLine` that contains both `unit_price_cents` and `line_total_cents` (price × quantity).  
   - `quote` (lines 0518‑0536) then computes the order subtotal by **summing only `unit_price_cents`** of each line (line 0523).  

   *Why this causes the reported problem*  
   - For three mugs priced at 1 000 cents each, `price_lines` produces a line with `unit_price_cents = 1000` and `line_total_cents = 3000`.  
   - The subtotal is calculated as `1000` (the unit price) instead of `3000`.  
   - Tax (10 %) is applied to the wrong subtotal, yielding `tax = 100` and a total of `1 100` cents ($11) – exactly the numbers the user observed.

   *Assumptions / missing cross‑function evidence*  
   - The `Quote` object is later persisted unchanged (no other code in this section rewrites `subtotal_cents`).  
   - No later adjustment of `subtotal_cents` is performed elsewhere in the codebase (outside the supplied section).  

   ### Shipping‑cost free‑shipping condition  
   *What the code does*  
   - `shipping_cost` checks `if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` (line 0514).  
   - The business rule states free standard shipping applies when **merchandise after discount** is ≥ 10 000 cents.  

   *Why this could be a problem*  
   - If a discount reduces the subtotal below the free‑shipping threshold, the current implementation may still grant free shipping because it looks at the pre‑discount subtotal.  

   *Assumptions / missing evidence*  
   - The rest of the system may compensate for this elsewhere (e.g., by passing a discounted subtotal), but within this file the condition is clearly based on the wrong value.

   ## Uncertainty  

   - Whether any later processing step (outside the provided section) overwrites `subtotal_cents` with the correct `line_total_cents`. The current evidence shows no such step, but the full file is not present.  
   - Whether the free‑shipping rule is intentionally simplified for this exercise; the code comment does not clarify the intended behavior beyond the rule excerpt.  

   ## Next checks  

   1. **Inspect order‑creation persistence** – locate where the `Quote` returned by `PricingService.quote` is written to the `orders` table. Verify that `subtotal_cents` is stored directly from the `Quote` without further modification.  

   2. **Search for any post‑quote adjustments** – look for functions that might recompute or replace `subtotal_cents` after `quote` is generated (e.g., in `OrderService._insert_order` or elsewhere).  

   3. **Validate free‑shipping logic** – find any callers of `PricingService.shipping_cost` and confirm whether they pass the discounted subtotal or the raw subtotal. If the rule is meant to use the post‑discount amount, adjust the condition accordingly.  

   4. **Run unit tests (if present)** – especially tests that cover multiple‑quantity cart lines and free‑shipping thresholds, to see if they currently fail or pass unexpectedly.  

   Addressing the subtotal bug will resolve the user’s immediate discrepancy (subtotal $10 → $30, total $11 → $33). The shipping‑cost check should be reviewed to ensure compliance with the documented business rule.

   ---

   # Section 5: original lines 574-681

   ## Findings  

   | Severity | Title | Location & Code |
   |----------|-------|-----------------|
   | **Medium** | **Cancel can be executed repeatedly, inflating stock** | `checkout.py` lines **0622‑0636** – the `cancel` method restores product stock for every line **without first verifying that the order is not already cancelled**. <br>```python\nfor line in self.db.lines(order_id):\n    self.db.execute(\"UPDATE products SET stock = stock + ?, updated_at = ? \"\n                    \"WHERE sku = ?\",\n                    (line[\"quantity\"], timestamp(now), line[\"sku\"]))\n    self.db.inventory_event(...)\n```<br>If `cancel` is called a second time on the same order (e.g., a client retries the request), the same quantities are added back to `products.stock` again, leaving the inventory ledger inconsistent. The order status is later set to `'cancelled'`, but the stock adjustment has already been performed. |

   ### Why this matters for the reported problem  

   The user’s complaint is about an **incorrect order subtotal/total**, not about inventory. The bug above does **not** affect pricing, but it is a concrete defect that can surface in the same service (e.g., a UI that retries a cancellation). It is therefore a *supported finding* in the supplied code.

   ## Uncertainty  

   | Area | Why the evidence is insufficient | What is unknown |
   |------|----------------------------------|-----------------|
   | **Subtotal of $10 instead of $30** | The code that computes the subtotal lives in `self.pricing.quote(request, now)`, which is **not included** in this section. The logic that aggregates repeated SKUs, multiplies unit price by quantity, and applies coupons is missing, so we cannot confirm whether the subtotal error originates here. | Whether `quote` correctly sums `line.quantity * line.unit_price_cents` for each line, and whether it merges duplicate SKUs as required by the business rules. |
   | **Tax calculation** | Tax is derived from `quote.tax_cents`, also produced by the missing `quote` implementation. | Whether the 10 % tax (rounded half‑up) is applied to the merchandise subtotal *after* discount, as the rules state. |
   | **Shipping cost for pickup** | The shipping method is stored in `request.shipping` and later copied into `quote.shipping_cents`. The mapping from shipping method to cost is not shown. | Whether the “pickup” method is correctly mapped to a zero‑cent shipping charge. |
   | **Idempotent checkout** | Checkout checks `existing[\"request_hash\"] != request.fingerprint()`. The definition of `request.fingerprint()` (which fields are hashed) is not provided. | Whether two semantically identical checkout requests (same cart, same shipping, no coupon) always produce the same hash, guaranteeing true idempotency. |

   ## Next checks  

   1. **Pricing / Quote logic** – Open the file(s) that define `Pricing.quote`. Verify:  
      * Repeated SKUs are combined into a single `PricedLine` with the summed quantity.  
      * `line_total_cents` = `quantity * unit_price_cents`.  
      * `quote.subtotal_cents` is the sum of all `line_total_cents`.  
      * No coupon is applied (coupon fields should be `None`/`0`).  

   2. **Tax computation** – Ensure the tax is calculated as `round_half_up(merchandise_after_discount * 0.10)`. Confirm the rounding rule matches “half up to the nearest cent”.

   3. **Shipping cost mapping** – Locate the function that translates `request.shipping` (e.g., `"pickup"`) to `quote.shipping_cents`. Confirm that `"pickup"` yields `0` and that free‑shipping thresholds are respected for other methods.

   4. **Request fingerprint** – Review `CheckoutRequest.fingerprint()` implementation. Check that it includes all fields that affect order pricing (cart contents, shipping method, coupon) and excludes volatile data (timestamps) so that identical requests generate identical hashes.

   5. **Cancel idempotency** – Add a guard in `cancel` to skip the stock‑restock loop when `order[\"status\"] == \"cancelled\"`, or otherwise make the operation idempotent.

   6. **Audit trail consistency** – Verify that `self.db.audit` records snapshots of the quote *before* any mutable state (e.g., price changes) could affect the stored order.

   Addressing the points above will let us confirm whether the subtotal discrepancy is due to a bug in the quote calculation, and will also fix the identified inventory‑stock bug.

   ---

   # Section 6: original lines 667-791

   ## Findings
   **None in this section** – The code you provided deals with refunds, audit‑history retrieval, and reporting (sales, status counts, product rankings, inventory, and CSV export). None of the examined statements compute a cart’s merchandise subtotal, apply tax, or add shipping for a newly‑placed order. Therefore, based on the supplied lines there is no demonstrable defect that could cause an order’s subtotal to be recorded as $10 instead of $30.

   ## Uncertainty
   - The problem you observe (subtotal $10, total $11 for three $10 mugs) must originate in the part of the code that **creates an order** – i.e., the checkout/ordering service that:
   1. Parses the incoming cart,
   2. Merges duplicate SKUs,
   3. Looks up product unit prices,
   4. Calculates `subtotal_cents = sum(unit_price * quantity)`,
   5. Applies any coupon discount,
   6. Computes tax (10 % of discounted merchandise) and shipping (free for pickup).

   - Because that portion of the source file is not included in the current excerpt, we cannot confirm whether the subtotal is being truncated, whether the quantity field is ignored, or whether a default quantity of 1 is being forced somewhere.

   - There is also a small, unrelated risk in the **refund** logic:
   - The code does not explicitly validate that `amount_cents` is non‑negative. A malicious caller could request a negative refund, which would *increase* the order’s remaining balance. This does not explain the current subtotal issue but is a potential integrity problem.

   ## Next checks
   1. **Locate the checkout / order‑creation service** (likely a class named `CheckoutService`, `OrderService`, or similar). Examine:
      - How the incoming request payload is parsed into cart lines.
      - Whether the `quantity` field is read and multiplied by the product’s `price_cents`.
      - The SQL `INSERT` that stores `subtotal_cents`, `discount_cents`, `tax_cents`, `shipping_cents`, and `total_cents` in the `orders` table.

   2. **Verify the `order_lines` handling**:
      - Ensure that duplicate SKUs are combined correctly (`quantity` summed) rather than overwritten.
      - Confirm that `line_total_cents` is calculated as `unit_price * quantity`.

   3. **Check tax and shipping calculations** for the “pickup” shipping method:
      - Shipping should be `0` cents.
      - Tax should be `round(0.10 * merchandise_after_discount)` (half‑up). For $30 merchandise with no discount, tax should be $3 (300 cents), giving a total of $33 (3300 cents).

   4. **Inspect any default values** that might be applied when a field is missing or malformed (e.g., defaulting `quantity` to `1` if the client omits it).

   5. **Review input validation** for the checkout endpoint:
      - Are required fields (`sku`, `quantity`) enforced?
      - Is there any code that silently drops extra items from the cart?

   6. **Run a targeted unit test** (or manually invoke the checkout API) with a payload that orders three mugs at $10 each, using the “pickup” shipping method and no coupon. Compare the stored `orders` row with the expected calculations.

   7. **Optional – audit the refunds path** for the negative‑amount risk identified above, adding a check that `amount_cents > 0` before proceeding.

   By focusing on the order‑creation logic, you should be able to pinpoint why the system records only a single unit’s price instead of the full quantity. Once that code is examined, any discrepancy with the business rules can be corrected.

   ---

   # Section 7: original lines 777-902

   **## Findings**

   | Severity | Title | Location & Code |
   |----------|-------|-----------------|
   | **Medium** | **`export_orders` raises a raw `FileExistsError` instead of a `ServiceError`** | `def export_orders(self, path: Path, start: str, end: str) -> dict:` (lines 778‑800) – the file is opened with mode **`"x"`** (exclusive‑create). If the target CSV already exists the interpreter raises `FileExistsError`, which is not caught and therefore leaks an unexpected exception type to the caller. The business rule states *“CSV export must not overwrite an existing file.”* The implementation should translate the OS‑level error into a domain‑specific `ServiceError` with a clear message. |
   | **Low** | **`import_orders` silently stops processing after the line‑limit is reached** | `def import_orders(db: Database, path: Path, now: datetime) -> dict:` (lines 857‑870) – when `number > 1000` the code appends a rejection entry and executes `break`. The loop ends, but the function still returns the partially‑filled `accepted` list. If the caller expects *all* lines up to the limit to be processed, the early `break` is fine, but the wording of the rule (*“Import line limit reached”*) suggests the function should continue scanning the rest of the file to collect *all* rejections rather than aborting the whole import. |
   | **Info** | **`seed_demo` may raise an exception when the `metadata` table is empty** | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` (lines 836‑839) – `db.one` likely returns `None` when no row matches, which is falsy and works, but if the helper raises `IndexError` or a custom exception for “no rows”, the seeding process would fail. The code assumes `db.one` returns a falsy value for “not seeded”. |

   **## Uncertainty**

   - **Root cause of the user’s subtotal mismatch** – The supplied snippet does **not** contain the checkout/quote logic that calculates `subtotal_cents`, `discount_cents`, `tax_cents`, etc. The problem (“subtotal is $10 instead of $30”) is most likely in a function that:
   1. **Aggregates cart lines** (combines repeated SKUs) or
   2. **Multiplies unit price by quantity**.
   
   Without seeing those functions we cannot definitively say whether the bug is in:
   * `OrderService.checkout` / `OrderService.quote`,
   * `Cart` handling,
   * or a database trigger that stores the wrong `subtotal_cents`.

   - **Whether the tax calculation follows the “round half up” rule** – The code for tax computation is not present, so we cannot verify compliance with the 10 % tax rule.

   - **Potential off‑by‑one in inventory reconciliation** – `health()` calls `self.reconcile_inventory()` and then filters `item["matches"]`. The structure of the returned items is not shown; if `reconcile_inventory` returns a list of tuples instead of dicts, the list‑comprehension would raise a `KeyError`. This is an assumption based on the surrounding code.

   **## Next checks**

   1. **Inspect the checkout/quote implementation** (likely in `OrderService`):
      - Verify that cart lines are correctly grouped and that `subtotal_cents` is computed as `price_cents * quantity` for *each* line.
      - Look for any early `break` or `return` that might stop after the first line.

   2. **Review the tax calculation** to ensure it uses **10 %**, rounds **half‑up**, and adds it to the total correctly.

   3. **Add error handling to `export_orders`**:
      ```python
      try:
         with path.open("x", encoding="utf-8", newline="") as stream:
            …
      except FileExistsError as exc:
         raise ServiceError(f"Export file already exists: {path}") from exc
      ```

   4. **Consider revising `import_orders`** to continue scanning after the line‑limit is hit, collecting *all* rejections, or at least document that processing stops intentionally.

   5. **Confirm the behavior of `Database.one`** when the query returns no rows; ensure `seed_demo` does not raise an unexpected exception on a fresh database.

   6. **Run a unit test** that creates a cart with three identical SKUs (e.g., three `MUG`s) and checks that the resulting order’s `subtotal_cents` equals `3 × 1000 = 3000`. This will directly expose the discrepancy reported by the user.

   ---

   # Section 8: original lines 888-1019

   ## Findings
   **None in this section** – The code you supplied (argument parsing, `write_invoice`, and the top‑level `dispatch` dispatcher) does not contain any of the arithmetic that computes a cart’s merchandise subtotal, tax, shipping, discount, or total. Consequently, there is no evidence here of a bug that would cause a three‑item order of $10‑each to be recorded as a $10 subtotal and $11 total.

   ## Uncertainty
   - The incorrect subtotal you observed must be produced by logic that is **not** included in the excerpt you posted.  
   - The relevant calculations are likely located in one (or more) of the following components, which are referenced but not shown:
   * `PricingService.quote(...)`
   * `OrderService.checkout(...)`
   * `OrderService.view(...)` (used by `write_invoice`)
   * Data‑model helpers such as `CheckoutRequest.from_dict`, `format_money`, or any utility that aggregates line items.

   Without seeing those functions we cannot confirm whether the problem stems from:
   1. **Quantity handling** – e.g., ignoring the `quantity` field or defaulting it to 1.
   2. **Unit‑price lookup** – e.g., fetching the wrong price from the catalog.
   3. **Subtotal aggregation** – e.g., summing only the first line item.
   4. **Rounding or tax‑shipping logic** – though the symptom (subtotal $10 instead of $30) points more directly to a quantity‑related issue.

   ## Next checks
   1. **`PricingService.quote` implementation** – Verify that it multiplies `unit_price_cents` by `quantity` for each cart line and that it correctly aggregates the results into `subtotal_cents`.
   2. **`OrderService.checkout`** – Ensure it stores the quoted values unchanged (order line snapshots) and that it does not inadvertently overwrite the subtotal with a single‑item value.
   3. **`CheckoutRequest.from_dict`** – Confirm that the JSON request schema includes a `quantity` field and that the parser correctly populates it.
   4. **Data model for order items** – Look at how `order["items"]` is built and persisted; check that `line_total_cents` = `unit_price_cents * quantity`.
   5. **Any helper that normalises or validates cart lines** – Search for code that “combines repeated SKUs into one line” and make sure it sums quantities rather than discarding them.
   6. **Unit tests (if any)** – Run tests that create a cart with multiple identical SKUs and verify the resulting `subtotal_cents`.

   Inspecting those modules will reveal whether the subtotal is being truncated to a single unit price, which would explain the $10 subtotal you observed. Once the relevant code is examined, any mis‑calculation can be pinpointed and corrected.

   ---

   # Section 9: original lines 1005-1060

   ## Findings
   **None in this section.**  
   The lines you supplied (1005‑1060) only contain the command‑dispatch logic, the `main()` entry point, and the program‑termination guard. They do not include any of the order‑creation, pricing, tax, or shipping calculations that would affect the subtotal or total shown to the user. Consequently, no defect can be demonstrated from the provided code.

   ## Uncertainty
   - The behaviour you observed (subtotal $10 for three $10 mugs, total $11 with pickup) must be produced somewhere else in the codebase – most likely in the functions that:
   - Parse the cart line(s) and combine quantities (`orders.create`, `cart.add_line`, etc.).
   - Look up product prices (`catalog.get_price` or similar).
   - Compute the merchandise subtotal, discounts, tax, and shipping (`orders.calculate_total`, `order.compute_totals`, etc.).
   - Without seeing those implementations we cannot confirm whether the problem is due to:
   - Ignoring the quantity field.
   - Using the wrong price (e.g., a discounted or promotional price).
   - Mis‑applying the shipping‑cost‑free‑for‑pickup rule.
   - Rounding or tax‑calculation errors.

   ## Next checks
   1. **Order creation path** – locate the function that builds an `Order` object from the CLI arguments (likely called from `dispatch` when the command is `"checkout"` or similar). Verify that it:
      - Reads the `quantity` argument correctly.
      - Multiplies `unit_price * quantity` for each line.
      - Handles repeated SKUs by consolidating them.

   2. **Price lookup** – inspect `catalog.get_price` (or whatever function supplies the unit price). Ensure it returns the current catalog price in cents and that the price for SKU “MUG” is indeed `1000` (i.e., $10).

   3. **Subtotal / total calculation** – examine the routine that:
      - Sums line totals to produce the merchandise subtotal.
      - Applies coupons (none in this case, but confirm the path is bypassed correctly).
      - Calculates tax (10 % of the post‑discount subtotal, rounded half‑up).
      - Adds shipping cost (should be `0` for pickup).

   4. **CLI argument parsing** – review the `argparse` configuration for the checkout command to confirm that the quantity argument is defined as an integer and that the default is not silently set to `1`.

   5. **Tests / examples** – if a test suite exists, run the scenario “3 MUGs, pickup, no coupon” and compare the computed JSON output with the expected values (`subtotal: 3000`, `tax: 300`, `shipping: 0`, `total: 3300`). This will pinpoint which step diverges.

   By focusing on the modules that actually perform the monetary calculations, you’ll be able to locate the root cause of the $10 subtotal instead of the expected $30. The dispatch and `main()` code shown here appear to be functioning as intended.