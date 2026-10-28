# Source verification assessments

These are individual batch assessments, not a final verdict across all evidence. A batch marked unresolved does not invalidate supporting evidence in another batch. Human validation remains required.

# Finding 1, batch 1/2

Claim: | **High** | Subtotal may ignore quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The provided source excerpts do **not** contain the `PricingService.quote` implementation.  
- The claim references line 0523: `subtotal = sum(line.unit_price_cents for line in lines)`, but this line is absent from the displayed code blocks.

## Explanation and limits  
The finding asserts that `PricingService.quote` computes the subtotal by summing only `unit_price_cents`, thereby ignoring each line’s `quantity`. Because the relevant function body is not included in the retrieved source, we cannot verify whether the implementation indeed performs `sum(line.unit_price_cents for line in lines)` or correctly multiplies by `line.quantity`. No contradictory code is present that would refute the claim, and no helper calls are shown that might adjust the subtotal elsewhere. Consequently, the claim remains **unresolved** for this batch; further inspection of the full `PricingService.quote` source is required.

## Next check  
- Retrieve the full definition of `PricingService.quote` (including surrounding lines) to confirm whether the subtotal calculation incorporates `quantity`.  
- If the function delegates to another helper for subtotal computation, examine that helper as well.

---

# Finding 1, batch 2/2

Claim: | **High** | Subtotal may ignore quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.quote` – line 0523:  

  ```python
  subtotal = sum(line.unit_price_cents for line in lines)
  ```

- `PricingService.price_lines` creates each `PricedLine` with both `unit_price_cents` and `line_total_cents` (line 0489‑0490), but the quote calculation does **not** use `line_total_cents`.

## Explanation and limits  
The `quote` method computes the order subtotal by summing only the `unit_price_cents` field of each priced line. Because `unit_price_cents` represents the price of a single unit, any quantity greater than 1 is ignored. Consequently, for a cart line of 3 mugs at $10 each (1000 cents), the subtotal will be `1000` cents instead of the correct `3000` cents. This directly explains the user’s observation of a $10 subtotal (and $11 total after tax and shipping) when $30 before tax was expected.

The source code shows no later adjustment that would incorporate `line_total_cents`; the subtotal is returned directly in the `Quote`. Therefore, within this batch the claim is verified.

**Limitations:**  
- The assessment is limited to the shown functions. If another layer later recomputes the subtotal using `line_total_cents`, it is not visible here.  
- Caller behavior (e.g., a wrapper that corrects the subtotal) cannot be examined because caller retrieval is disabled per the retrieval limitations.

## Next check  
Verify whether any downstream code (e.g., order creation or reporting) recomputes or overrides the subtotal, which could mitigate the issue. If such logic exists, the impact on final totals may be reduced.

---

# Finding 2, batch 1/2

Claim: | **Medium** | Free‑shipping rule checks pre‑discount subtotal, not post‑discount as required. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The retrieved source does **not** contain the implementation of `PricingService.shipping_cost`.  
- The only lines shown for that function are referenced in the finding (`lines 0514‑0515`), but the actual code is absent from the provided context.  

## Explanation and limits  
The claim states that the free‑shipping check uses the *pre‑discount* subtotal:

```python
if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
```

To verify this, we would need to see the definition of `PricingService.shipping_cost` and determine whether the `subtotal` argument represents the pre‑discount or post‑discount merchandise amount. The supplied source excerpt stops at line 0039 (module constants) and later shows unrelated database methods; it never includes the `shipping_cost` function body. Consequently, we have no direct evidence to confirm that the condition uses the pre‑discount subtotal, nor any counter‑evidence showing it uses the post‑discount amount.

Because the required code is missing from this batch, we cannot support or refute the claim based on the available evidence. A later batch that includes the `PricingService.shipping_cost` implementation would be needed for a definitive assessment.  

## Next check  
- Retrieve the `PricingService.shipping_cost` implementation (including the lines around 0514‑0515) to see how `subtotal` is computed and passed.  
- Verify whether the subtotal passed to this function is the merchandise subtotal before discounts or after discounts.  
- If the function uses a pre‑discount subtotal, the claim is supported; if it uses a post‑discount subtotal, the claim is refuted.  

---

# Finding 2, batch 2/2

Claim: | **Medium** | Free‑shipping rule checks pre‑discount subtotal, not post‑discount as required. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.shipping_cost` implementation (lines 0514‑0515):  

  ```python
  0514:         if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
  0515:             return 0
  ```

  The condition uses only `subtotal`; the `discount` argument is never referenced.

## Explanation and limits  
The business rule states that standard shipping is free **when merchandise *after* discount is at least 10,000 cents**. The function receives both `subtotal` (pre‑discount amount) and `discount`, yet the free‑shipping check compares only `subtotal` to `FREE_SHIPPING_CENTS`. Because `discount` is ignored, the function applies free shipping based on the pre‑discount subtotal, contradicting the rule that requires the post‑discount amount.  

Thus, the claim that the free‑shipping rule checks pre‑discount subtotal, not post‑discount as required, is directly supported by the source code.  

Limitations: This assessment is confined to the `PricingService.shipping_cost` method. We cannot verify how callers compute or pass `subtotal` and `discount`; however, the method itself does not incorporate the discount in its free‑shipping decision, which is sufficient to support the claim for this batch.

## Next check  
Further verification could examine callers of `PricingService.shipping_cost` to see whether they pre‑adjust `subtotal` to reflect discounts before invoking the method. If callers already pass a post‑discount subtotal, the rule might be satisfied indirectly. However, based solely on the examined function, the free‑shipping logic does not use the discount parameter.

---

# Finding 3, batch 1/3

Claim: | **Medium** | Cancel can be executed repeatedly, potentially inflating stock (restocks without status check). | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |

## Assessment  
**UNRESOLVED**

## Source evidence  
The supplied source excerpt contains module‑level constants, schema definitions, demo data, and utility functions, but **does not include the implementation of `OrderService.cancel` or any code around lines 0622‑0636 of `checkout.py`** that the claim references.  

Relevant excerpts:  

- Constants and schema (lines 0016‑0039, 0234‑0322) – no cancellation logic.  
- Demo data (lines 0815‑0832) – unrelated.  
- Helper `timestamp` (lines 0068‑0071) and `nonempty` (lines 0081‑0082) – unrelated.  

No code showing a “stock‑restock loop” or status checks is present in the provided batch.

## Explanation and limits  
The claim asserts that the cancel operation can be invoked repeatedly and will restock inventory each time because it lacks a status check. Verifying this requires examining the `cancel` method (or related cancellation handling) to see whether it:

1. Checks the order’s current status before adjusting stock, and  
2. Prevents multiple restocks for the same order.

Since the relevant portion of `checkout.py` (lines 0622‑0636) is **absent** from the retrieved source, we cannot confirm whether such a check exists or is missing. The absence of this code in the current batch does not prove it is absent elsewhere, nor does it demonstrate that the implementation correctly guards against repeated cancellations.

Therefore, based solely on the available source, the claim remains **unresolved**. Further inspection of the `OrderService.cancel` implementation (or the referenced lines in `checkout.py`) is needed to determine whether repeated cancellations can inflate stock.

---

# Finding 3, batch 2/3

Claim: | **Medium** | Cancel can be executed repeatedly, potentially inflating stock (restocks without status check). | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |

## Assessment  
**UNRESOLVED**

## Source evidence  
The batch only includes excerpts from `checkout.py` covering validation helpers, `Database` methods, `CatalogService.restock`, `PricingService.quote`, `OrderService.view`, and the beginning of `OrderService.checkout` (up to line 0585). No code for a `cancel` method or any stock‑restock logic appears in the provided excerpts.

## Explanation and limits  
The claim concerns the **cancellation** workflow: that invoking cancel repeatedly could restock inventory without verifying the order’s current status, leading to inflated stock. To refute this, we would need to see a `cancel` implementation that either (a) lacks a status check before calling `CatalogService.restock`/`Database.inventory_event`, or (b) explicitly restocks unconditionally. The supplied source does not contain such a method, nor does it show any calls to `CatalogService.restock` from a cancellation path. Consequently, we have no direct evidence to confirm or deny the claim within this batch.

Because the verification plan disables caller‑level retrieval, we cannot infer behavior from callers of `cancel` or from higher‑level logic. Therefore the claim remains **unresolved** pending inspection of the portion of the codebase that implements order cancellation. Human review of the missing `cancel` implementation is required.

---

# Finding 3, batch 3/3

Claim: | **Medium** | Cancel can be executed repeatedly, potentially inflating stock (restocks without status check). | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The batch only contains `OrderService._insert_order` (lines 0592‑0603) and `OrderService._reserve_line` (lines 0612‑0620).  
- No code related to order cancellation, stock‑restock loops, or status checks appears in the provided excerpt.  

## Explanation and limits  
The claim concerns the cancellation workflow: that a cancellation can be invoked repeatedly and would restock inventory without verifying the order’s current status, potentially inflating stock. The source excerpt does not include any cancellation method, nor any logic that updates stock on cancellation. Consequently, we have no direct evidence to **support** the claim, nor any code that **refutes** it (e.g., a guard that checks order status before restocking).  

Because the retrieval limitations state that callers and additional helpers are not shown, it is possible that cancellation logic exists elsewhere in the codebase. However, within this batch we cannot determine whether such a guard is present or absent. Therefore the claim remains **unresolved** for this batch.

## Next check  
To resolve the claim, locate the implementation of the cancellation operation (e.g., `OrderService.cancel` or similar) and examine whether it:

1. Checks the order’s current status before adjusting inventory, and  
2. Prevents multiple restocks for the same order.  

If such checks exist, the claim would be **refuted**; if not, it would be **supported**.

---

# Finding 4, batch 1/2

Claim: | **Medium** | Refund logic lacks a non‑negative amount guard; a negative refund could increase order balance. | Refund handling section – no explicit `amount_cents > 0` guard (exact lines not quoted) |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- **Refund table definition** – line 0314:  
  ```sql
  amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
  ```

## Explanation and limits  
The database schema for the `refunds` table includes a `CHECK(amount_cents > 0)` constraint, which enforces that every stored refund amount must be strictly positive. This prevents a negative `amount_cents` value from being persisted, eliminating the possibility of a negative refund being applied to an order and thereby increasing the order’s balance.

Because the claim asserts that “Refund logic lacks a non‑negative amount guard; a negative refund could increase order balance,” the presence of the explicit `CHECK(amount_cents > 0)` directly contradicts it. Even if the Python refund‑handling code omitted an explicit runtime guard, the database constraint guarantees non‑negative amounts at the point of persistence.

No additional code for `OrderService.refund` was retrieved in this batch, but the schema evidence alone is sufficient to refute the claim.  

## Next check  
Further review of the `OrderService.refund` implementation could confirm that it correctly propagates the amount to the database and respects the constraint, but the current batch already provides decisive counter‑evidence.

---

# Finding 4, batch 2/2

Claim: | **Medium** | Refund logic lacks a non‑negative amount guard; a negative refund could increase order balance. | Refund handling section – no explicit `amount_cents > 0` guard (exact lines not quoted) |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- Call to validator in `OrderService.refund`:  

  ```
  0661: integer(amount_cents, "amount_cents", 1, 100_000_000)
  ```  

- Definition of `integer` validator (enforces minimum):  

  ```
  0090: def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
  0092:     if isinstance(value, bool) or not isinstance(value, int):
  0093:         raise ServiceError(f"{name} must be an integer")
  0094:     if not minimum <= value <= maximum:
  0095:         raise ServiceError(f"{name} must be between {minimum} and {maximum}")
  ```

## Explanation and limits  
`OrderService.refund` validates `amount_cents` with `integer(amount_cents, ..., 1, ...)`. The `integer` helper requires the value to be an `int` and to satisfy `minimum <= value`, where `minimum` is `1`. Consequently any `amount_cents` ≤ 0 (including negative values) triggers a `ServiceError` before any refund logic runs. This directly prevents a negative refund amount, which would otherwise increase the order’s balance.  

Thus the claim that the refund logic lacks a non‑negative guard is **incorrect** for this batch. No further evidence in the provided source suggests an alternate path that bypasses this validation.

## Next check  
The current batch confirms a positive‑only guard for refund amounts. Any claim about other missing validations (e.g., maximum refund amount, duplicate request handling) should be examined with their respective code sections.

---

# Finding 5, batch 1/2

Claim: | **Medium** | `export_orders` propagates raw `FileExistsError` instead of a domain `ServiceError`. | `def export_orders(...):` – lines 778‑800 (opens file with mode `"x"` and does not catch `FileExistsError`) |

## Assessment  
**UNRESOLVED**

## Source evidence  
The provided source excerpts contain module imports, constants, schema definitions, demo data, and the `Database.all` and `Database.lines` methods (lines 0351‑0393).  
No code for `ReportingService.export_orders` (or any handling of `FileExistsError`) appears in the supplied blocks (e.g., lines 778‑800 are not included).

## Explanation and limits  
The claim concerns the behavior of `export_orders` when opening a file with mode `"x"` and whether it catches `FileExistsError` and raises a domain‑specific `ServiceError`. Because the function’s implementation is absent from the retrieved context, we cannot verify:

* Whether `export_orders` opens the file with `"x"` and lets `FileExistsError` bubble up.  
* Whether it catches the exception and re‑raises a `ServiceError`.  

Without the relevant code, there is no direct evidence to **support** the claim, nor is there evidence that contradicts it. Consequently, the assessment must remain **UNRESOLVED** for this batch.

## Next check  
A later batch may contain the missing `export_orders` implementation. If it shows a `try/except FileExistsError` converting to `ServiceError`, the claim would be supported; if it lacks such handling, the claim would be refuted. Until then, the status stays unresolved.

---

# Finding 5, batch 2/2

Claim: | **Medium** | `export_orders` propagates raw `FileExistsError` instead of a domain `ServiceError`. | `def export_orders(...):` – lines 778‑800 (opens file with mode `"x"` and does not catch `FileExistsError`) |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `ReportingService.export_orders` opens the output file with exclusive‑create mode:  

  ```text
  0786: if not path.parent.is_dir():
  0787:     raise ServiceError("Export directory does not exist")
  0796: with path.open("x", encoding="utf-8", newline="") as stream:
  ```  

  The `"x"` mode raises a built‑in `FileExistsError` when the target file already exists. No `try/except` block surrounds this call, and there is no conversion to `ServiceError`.

## Explanation and limits  
The function validates the export directory (line 0786‑0787) and then attempts to create the file exclusively (line 0796). Because the code does **not** catch `FileExistsError` nor re‑raise a `ServiceError` in that case, the raw exception will propagate to the caller. This directly confirms the claim that `export_orders` propagates a raw `FileExistsError` instead of translating it into the domain‑specific `ServiceError`.

Limitations: the assessment is confined to the shown source block. It is possible that a higher‑level caller catches `FileExistsError` and wraps it, but such behavior is outside the retrieved context (caller retrieval is disabled). Within this batch, the evidence unequivocally supports the claim.

## Next check  
- Verify whether any upstream caller of `export_orders` handles `FileExistsError` and converts it to `ServiceError`. If such handling exists, the overall service behavior may still meet the domain error contract, but that is unresolved in this batch.

---

# Finding 6, batch 1/2

Claim: | **Medium** | `import_orders` stops processing after the line‑limit is reached, discarding later rejections. | `def import_orders(...):` – lines 857‑870 (`break` when `number > 1000`) |

## Assessment  
**UNRESOLVED**

## Source evidence  
The supplied source excerpt does not contain the definition of `import_orders`. The highest line numbers shown are in the 800‑range for demo data (e.g., lines 0815‑0832) and the `CartLine.from_dict` method (lines 0170‑0176). No code for `def import_orders(...):` or any `break` statement around a line‑limit check appears in the provided block.

## Explanation and limits  
Because the `import_orders` function is absent from the retrieved source, we cannot verify whether it contains a `break` when a line count exceeds 1000, nor can we confirm that later rejections are discarded. The claim therefore cannot be supported or refuted with the current batch of code.  

The limitation note states that caller retrieval is disabled, so any behavior that depends on callers or external helpers cannot be examined here. Consequently, the assessment must remain **UNRESOLVED** until a batch that includes the `import_orders` implementation is reviewed.

---

# Finding 6, batch 2/2

Claim: | **Medium** | `import_orders` stops processing after the line‑limit is reached, discarding later rejections. | `def import_orders(...):` – lines 857‑870 (`break` when `number > 1000`) |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0864: for number, line in enumerate(stream, 1):
0867:     if number > 1000:
0868:         rejected.append({"line": number, "error": "Import line limit reached"})
0869:         break
```

## Explanation and limits  
The `import_orders` function iterates over each line of the input file. When the line counter exceeds 1000, it records a single rejection for that line (the one that crossed the limit) and then executes `break`, exiting the loop entirely. Consequently, any lines after the 1000‑th are never examined, and any errors they might contain are not added to the `rejected` list. This matches the claim that the function “stops processing after the line‑limit is reached, discarding later rejections.”  

No additional helper calls or surrounding logic alter this behavior within the provided batch, so the claim is directly supported by the source.  

## Next check  
None needed for this claim; the evidence is conclusive for this batch.

---

# Finding 7, batch 1/2

Claim: | **Low** | `seed_demo` may raise an exception when the `metadata` table is empty. | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` – lines 836‑839 |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The provided source excerpt contains the definition of `Database.execute` (lines 0345‑0346) but does **not** include the implementation of `Database.one` or the `seed_demo` function.  
- No lines numbered 836‑839 appear in the supplied context, so the quoted `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` statement is not present for verification.

## Explanation and limits  
The claim that `seed_demo` may raise an exception when the `metadata` table is empty hinges on two pieces of code:

1. **`Database.one` behavior** – whether it raises an exception when the query returns no rows. This implementation is absent from the retrieved source, so we cannot confirm its error‑handling policy.  
2. **`seed_demo` logic** – the presence of the `if db.one(...):` check at lines 836‑839. Those lines are not included in the batch, so we cannot see whether the call is guarded, whether a default value is supplied, or whether the result is used safely.

Because the necessary code is missing from this batch, we lack direct evidence to either support or refute the claim. A helper (`Database.one`) could internally return `None` instead of raising, or `seed_demo` might catch the exception; without seeing those definitions, the risk cannot be determined here.

## Next check  
To resolve the claim, retrieve the implementation of `Database.one` and the full `seed_demo` function (including lines 836‑839). Verify whether `Database.one` raises on an empty result set and whether `seed_demo` handles that case appropriately. Until that code is examined, the assessment remains **UNRESOLVED**.

---

# Finding 7, batch 2/2

Claim: | **Low** | `seed_demo` may raise an exception when the `metadata` table is empty. | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` – lines 836‑839 |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `Database.one` implementation returns the result of `fetchone()` which yields `None` when no rows match:  
  `0348: def one(self, sql: str, parameters: tuple = ()) -> sqlite3.Row | None:`  
  `0349:     return self.execute(sql, parameters).fetchone()`  

- `seed_demo` checks the result of that call in a conditional:  
  `0837: if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):`  
  `0838:     return {"seeded": False, "message": "Demo data already exists"}`  

## Explanation and limits  
`db.one` does **not** raise an exception when the `metadata` table exists but contains no rows; it simply returns `None`. The `if` statement in `seed_demo` treats a falsy result (`None`) as “not seeded” and proceeds to insert demo data. Therefore the claim that `seed_demo` may raise an exception when the `metadata` table is empty is unsupported by the provided code.  

The only way an exception could arise here is if the `metadata` table itself were missing or the `execute` method raised, neither of which is indicated in the shown source. Consequently, within this batch the claim is refuted.

---

# Finding 8, batch 1/2

Claim: | **Info** | Quantity parsing and bounds checking appear correct. | `CheckoutRequest.from_dict` – lines 0189‑0194 |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The provided source excerpts contain module‑level constants, table schemas, demo data, and the `nonempty` helper (lines 0081‑0087).  
- No excerpt includes the definition of `CheckoutRequest.from_dict`, nor lines 0189‑0194 that the claim references.

## Explanation and limits  
The claim states that “Quantity parsing and bounds checking appear correct” in `CheckoutRequest.from_dict` (lines 0189‑0194). Because the relevant code is **not present** in the retrieved batch, we cannot verify whether the function parses the `quantity` field, enforces it as an integer, and checks it against `MAX_LINE_QUANTITY` (or any other bounds).  

Without seeing the implementation, we lack direct evidence to either support or refute the claim. A helper such as `nonempty` is shown, but it does not relate to quantity handling. Consequently, the assessment must remain **unresolved** for this batch. Further batches containing the `CheckoutRequest.from_dict` implementation would be needed to reach a definitive conclusion.

---

# Finding 8, batch 2/2

Claim: | **Info** | Quantity parsing and bounds checking appear correct. | `CheckoutRequest.from_dict` – lines 0189‑0194 |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `integer` helper validates type and range:  

  ```python
  0090: def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
  0091:     if isinstance(value, bool) or not isinstance(value, int):
  0092:         raise ServiceError(f"{name} must be an integer")
  0093:     if not minimum <= value <= maximum:
  0094:         raise ServiceError(f"{name} must be between {minimum} and {maximum}")
  ```

- `CartLine.from_dict` uses the helper with proper bounds:  

  ```python
  0175: quantity = integer(value.get("quantity"), "quantity", 1, MAX_LINE_QUANTITY)
  ```

- `CheckoutRequest.from_dict` builds the cart lines, invoking the above parsing for each item:  

  ```python
  0189: customer_id = nonempty(value.get("customer_id"), "customer_id", 40)
  0190: request_id = nonempty(value.get("request_id"), "request_id", 80)
  0191: raw_lines = value.get("items")
  0192: if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= MAX_CART_LINES:
  0193:     raise ServiceError(f"Cart must contain 1 to {MAX_CART_LINES} lines")
  0194: lines = tuple(CartLine.from_dict(item) for item in raw_lines)
  ```

## Explanation and limits  
The `integer` helper (lines 0090‑0094) enforces that a value is an integer and lies within the inclusive bounds supplied. `CartLine.from_dict` (line 0175) calls this helper with a minimum of 1 and a maximum of `MAX_LINE_QUANTITY`, ensuring that each cart‑line quantity is a positive integer and does not exceed the allowed maximum.  

`CheckoutRequest.from_dict` (lines 0189‑0194) validates that the `items` field is a non‑empty list of acceptable length and then constructs each `CartLine` via `CartLine.from_dict`. Consequently, every quantity in the checkout request passes through the `integer` validation, confirming that quantity parsing and bounds checking are performed correctly for the code paths shown.

No source in this batch contradicts this behavior; there is no alternative parsing or missing validation shown. The assessment is limited to the presented functions; callers or other modules not retrieved could affect overall behavior, but within this batch the claim holds.

---

# Finding 9, batch 1/2

Claim: | **Info** | Duplicate‑SKU validation rejects duplicates instead of combining them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |

## Assessment  
**UNRESOLVED**

## Source evidence  
The provided source excerpts include module‑level constants, the database schema, demo data, and the `nonempty` helper (lines 0081‑0087). No code for `CheckoutRequest.from_dict` or any duplicate‑SKU handling appears in the retrieved blocks (e.g., lines 0195‑0196 are not present).

## Explanation and limits  
The claim concerns the behavior of `CheckoutRequest.from_dict`—specifically that it *rejects* duplicate SKUs instead of *combining* them. Because the function’s implementation is absent from the current batch, we cannot verify whether it performs a rejection, a combination, or something else. The lack of the relevant lines means we have no direct counter‑evidence (e.g., a check that merges quantities) nor supporting evidence (e.g., a `raise ServiceError` on duplicate SKUs).  

Given the retrieval limitations (only one level of callers/helpers is included, and the caller code for `CheckoutRequest.from_dict` is not among the retrieved snippets), the claim cannot be confirmed nor refuted based on this batch alone.

## Next check  
To resolve the claim, retrieve the source of `CheckoutRequest.from_dict` (especially lines 0195‑0196) and examine how it processes repeated SKUs. Look for logic that either raises an error on duplicates or aggregates quantities into a single `CartLine`. This additional context is required to determine whether the implementation aligns with the business rule that duplicate SKUs should be combined.

---

# Finding 9, batch 2/2

Claim: | **Info** | Duplicate‑SKU validation rejects duplicates instead of combining them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `CheckoutRequest.from_dict` lines 0195‑0196:  

  ```python
  0195: if len({line.sku for line in lines}) != len(lines):
  0196:     raise ServiceError("Combine duplicate SKUs into one cart line")
  ```

## Explanation and limits  
The code builds a set of SKUs from the parsed cart lines and compares its size to the number of lines. If they differ, a `ServiceError` is raised with the message *“Combine duplicate SKUs into one cart line”*. This behavior **rejects** a request that contains duplicate SKUs instead of automatically merging them into a single line. No logic in this block combines duplicates; it only detects and aborts.  

Thus the claim that “Duplicate‑SKU validation rejects duplicates instead of combining them” is directly supported by the source.  

Limitations: The assessment is confined to the shown `CheckoutRequest.from_dict` implementation. Other parts of the codebase (outside this batch) might perform SKU combination elsewhere, but within this batch the validation is clearly a rejection.  

## Next check  
- Verify whether any higher‑level caller or helper later combines duplicate SKUs before invoking `CheckoutRequest.from_dict`. Since caller retrieval is disabled for this batch, that question remains **UNRESOLVED** here.

---

# Finding 10, batch 1/2

Claim: | **Info** | Shipping‑method validation maps `"pickup"` to a free method. | `CheckoutRequest.from_dict` – lines 0197‑0199 |

## Assessment  
**UNRESOLVED**

## Source evidence  
- `SHIPPING_CENTS = {"standard": 500, "express": 1200, "pickup": 0}` ( line 0038 )

## Explanation and limits  
The source defines a dictionary that assigns a cost of 0 cents to the shipping method `"pickup"`, which is consistent with the idea that pickup is free. However, the claim refers specifically to *validation* performed inside `CheckoutRequest.from_dict` at lines 0197‑0199, mapping the string `"pickup"` to a free method. Those lines are not present in the provided batch, so we cannot verify whether the method actually validates the input and uses the dictionary to set a free shipping cost.  

Because we lack the relevant function body, we cannot confirm nor refute the claim. The constant alone does not prove that the validation logic exists or behaves as described. Therefore the assessment remains **UNRESOLVED** for this batch.  

*Next check*: Obtain the implementation of `CheckoutRequest.from_dict` (especially lines 0197‑0199) to see whether it references `SHIPPING_CENTS` and enforces the free‑shipping rule for `"pickup"`.

---

# Finding 10, batch 2/2

Claim: | **Info** | Shipping‑method validation maps `"pickup"` to a free method. | `CheckoutRequest.from_dict` – lines 0197‑0199 |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
```python
0197: shipping = value.get("shipping", "standard")
0198: if not isinstance(shipping, str) or shipping not in SHIPPING_CENTS:
0199:     raise ServiceError("Shipping must be standard, express or pickup")
```

## Explanation and limits  
The `CheckoutRequest.from_dict` method only **validates** that the supplied `shipping` field is a string and that its value appears in the `SHIPPING_CENTS` mapping. It does **not** perform any mapping of `"pickup"` to a free‑shipping cost; the actual cost lookup (e.g., `SHIPPING_CENTS["pickup"] == 0`) would occur elsewhere, but that code is not present in the provided block. Therefore the claim that “shipping‑method validation maps `\"pickup\"` to a free method” is not supported by the evidence in this batch.

The absence of a cost‑assignment statement here does not prove that such a mapping does not exist elsewhere, but the specific lines cited do not contain it, so the claim is refuted for this batch.

## Next check  
Further investigation of the `SHIPPING_CENTS` definition or any function that computes the order total would be needed to confirm how `"pickup"` is priced. This batch alone does not provide that information.

---

# Finding 11, batch 1/2

Claim: | **Info** | Catalog price updates are persisted correctly. | `CatalogService.update_price` – lines 0428‑0436 |

## Assessment  
**UNRESOLVED**

## Source evidence  
- The provided source excerpt contains only module‑level imports, constants, schema definitions, demo data, and utility functions.  
- No definition of `CatalogService.update_price` appears in the excerpt; lines 0428‑0436 are not present.  

## Explanation and limits  
The claim states that “Catalog price updates are persisted correctly” and points to `CatalogService.update_price` (lines 0428‑0436). Because the excerpt does not include the implementation of `CatalogService.update_price`, we have no direct evidence that the method writes the new price to the database, updates the `products` table, or otherwise persists the change.  

Without seeing the code, we cannot confirm whether the method:
1. Executes an `UPDATE` statement on the `products` table,  
2. Commits the transaction, or  
3. Handles errors that might prevent persistence.  

A helper function could perform the persistence, but caller retrieval is disabled for this verification plan, so any indirect validation remains unknown. Consequently, the claim cannot be supported nor refuted based on the current batch.

## Next check  
To resolve this claim, locate the implementation of `CatalogService.update_price` (lines 0428‑0436) and verify that it executes a database update and commits the change. If the method calls another helper that performs the persistence, that helper must also be examined. Until that code is reviewed, the claim remains **UNRESOLVED**.

---

# Finding 11, batch 2/2

Claim: | **Info** | Catalog price updates are persisted correctly. | `CatalogService.update_price` – lines 0428‑0436 |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `CatalogService.update_price` validates the input and runs a transaction:  

  ```python
  0428: def update_price(self, sku: str, price_cents: int, now: datetime) -> dict:
  0429:     integer(price_cents, "price_cents", 0, 10_000_000)
  0430:     with self.db.transaction():
  0431:         product = self.db.product(sku)
  0432:         self.db.execute("UPDATE products SET price_cents = ?, updated_at = ? "
  0433:                         "WHERE sku = ?", (price_cents, timestamp(now), sku))
  0434:         self.db.audit("product", sku, "price_changed",
  0435:                       {"old": product.price_cents, "new": price_cents}, now)
  0436:     return asdict(self.db.product(sku))
  ```

- The `Database.execute` helper (lines 0345‑0346) forwards the SQL to SQLite, persisting the change.

## Explanation and limits  
The function explicitly issues an `UPDATE` statement against the `products` table, wrapped in a transaction, and then reads the product back (`self.db.product(sku)`) to return the fresh state. This demonstrates that a price change is written to the database and can be retrieved, satisfying the claim that “catalog price updates are persisted correctly” for this method.

Limitations:  
- The assessment is confined to the `update_price` method; other code paths that might modify product prices are not examined.  
- Persistence relies on the underlying `Database.execute` correctly committing the transaction; the provided snippet shows the transaction commit logic (lines 0362‑0363).  
- No runtime verification is performed; the claim is judged solely on static code evidence.

## Next check  
Further batches should verify that callers of `CatalogService.update_price` handle errors appropriately and that subsequent reads (e.g., order line pricing) indeed reflect the updated price. Also confirm that audit logging does not interfere with persistence.