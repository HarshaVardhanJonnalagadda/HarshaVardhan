# Source verification assessments

Outcome: verification_incomplete

Model assessments require human validation. Blocked, failed, and unprocessed tasks are unresolved. No runtime reproduction or fix verification was performed.

Unprocessed tasks: []

# Finding 1, batch 1/1

Claim: | **Medium** | **`read_json` does not handle a missing file** | Lines **126‑133**:<br>`def read_json(path: Path) -> dict[str, Any]:`<br>`    if path.stat().st_size > 100_000:`<br>`        raise ServiceError(\"Request file exceeds 100000 bytes\")`<br>`    try:`<br>`        value = json.loads(path.read_text(encoding=\"utf-8\"))`<br>`    except (UnicodeError, json.JSONDecodeError) as exc:`<br>`        raise ServiceError(\"Request must be a UTF‑8 JSON document\") from exc` | The function calls `path.stat()` and `path.read_text()` **without** first checking that the file exists. If the supplied path does not exist, Python raises `FileNotFoundError`, which propagates out of `read_json` as an unhandled exception. | A checkout, catalog import, or any command that reads a JSON request will abort with a traceback instead of returning a controlled `ServiceError`. The caller will not get a chance to roll back a transaction, release any reserved stock, or compute a total. This can leave the database in an inconsistent state (e.g., a partially‑created order) and break the “stock must not be partially reserved” rule. |

## Assessment
UNRESOLVED

No model call was made. Reason: The complete evidence exceeds the configured local token budget.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 10893 tokens; token limit: 8000.


---

# Finding 2, batch 1/1

Claim: | **High** | **Subtotal calculated from unit price instead of line total** | `quote` method (lines 0522‑0524):<br>`lines = self.price_lines(request.lines)`<br>`subtotal = sum(line.unit_price_cents for line in lines)` | `price_lines` creates a `PricedLine` that contains both `unit_price_cents` **and** `line_total_cents` (line 0489). The subtotal of an order must be the sum of *line totals* (price × quantity). Summing only the unit price ignores the quantity, so any line with `quantity > 1` under‑states the merchandise subtotal, which in turn reduces the computed discount, tax, and final total. This directly violates the business rule “Merchandise subtotal is the sum of unit price multiplied by quantity for every cart line.” |

## Assessment
UNRESOLVED

No model call was made. Reason: The complete evidence exceeds the configured local token budget.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 9108 tokens; token limit: 8000.


---

# Finding 3, batch 1/1

Claim: | **Medium** | **Free‑shipping check uses pre‑discount subtotal** | `shipping_cost` method (lines 0511‑0516):<br>`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:` | The rule states that standard shipping is free **when merchandise *after discount* is at least 10 000 cents**. The implementation checks `subtotal` (pre‑discount) and completely ignores the `discount` argument that is passed in. Orders that qualify for free shipping after a coupon will still be charged shipping, and conversely orders that do not qualify after discount could incorrectly receive free shipping if the pre‑discount subtotal is high enough. |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0511: def shipping_cost(self, method: str, subtotal: int, discount: int) -> int:
0512:     if method == "pickup":
0513:         return 0
0514:     if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
0515:         return 0
0516:     return SHIPPING_CENTS[method]
```
*Lines 0511‑0516 of `PricingService.shipping_cost`*  

## Explanation and limits  
The business rule states that **standard shipping is free when the merchandise *after discount* is ≥ 10 000 cents**.  
The implementation receives both `subtotal` (pre‑discount) and `discount` (the coupon amount) but the conditional on line 0514 checks only `subtotal` against `FREE_SHIPPING_CENTS`. The `discount` argument is never used, so the free‑shipping eligibility is calculated on the pre‑discount amount.  

Consequences:  

* An order whose discounted subtotal reaches 10 000 cents but whose original subtotal is lower will be incorrectly charged the standard shipping fee.  
* Conversely, an order whose original subtotal exceeds 10 000 cents but falls below that threshold after applying a coupon will incorrectly receive free shipping.  

The bug is directly visible in the `shipping_cost` method; no other helper in the provided code adjusts this logic. The `quote` method (lines 0518‑0535) passes both `subtotal` and `discount` to `shipping_cost`, but the latter ignores `discount`, confirming the mismatch.

## Next check  
* Verify whether any other part of the code (e.g., a wrapper around `shipping_cost` or a later adjustment) compensates for this omission.  
* Ensure that tests cover scenarios where a coupon brings the post‑discount subtotal below/above the free‑shipping threshold.  
* Consider adding unit tests that assert free shipping is granted only when `subtotal - discount >= FREE_SHIPPING_CENTS`.  

---

# Finding 4, batch 1/1

Claim: | **Low** | **`shipping_cost` signature includes an unused `discount` parameter** | Same method (lines 0511‑0516) – the `discount` argument is never referenced. | While not a functional bug by itself, the presence of an unused parameter suggests a missing implementation (the free‑shipping rule) and can lead to future maintenance errors. |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- Method signature (lines 0511‑0512):  
  ```python
  0511: def shipping_cost(self, method: str, subtotal: int, discount: int) -> int:
  ```
- Method body (lines 0512‑0516):  
  ```python
  0512:     if method == "pickup":
  0513:         return 0
  0514:     if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
  0515:         return 0
  0516:     return SHIPPING_CENTS[method]
  ```

The `discount` parameter is never referenced inside the function.

## Explanation and limits  
The claim that the `discount` argument is unused is directly supported by the source: the function only checks `method` and `subtotal`. The parameter is passed from `PricingService.quote` (line 0525) but has no effect on the calculation.

**Implications**  
- Business rule: *“Standard shipping is free when merchandise **AFTER discount** is at least 10,000 cents.”*  
- Implementation: free‑shipping condition checks `subtotal >= FREE_SHIPPING_CENTS`, i.e., **before** any discount.  
- Because `discount` is ignored, orders that should pay for shipping (when the discounted subtotal is below the threshold but the pre‑discount subtotal is above) will incorrectly receive free standard shipping, potentially reducing revenue and violating the specification.

The unused parameter itself is not a functional bug, but it signals a missing implementation of the free‑shipping rule and can lead to maintenance errors or future misuse.

## Next check  
- Verify whether any helper (e.g., a wrapper around `shipping_cost`) applies the discount logic elsewhere.  
- Confirm test coverage for free‑shipping scenarios both before and after discount.  
- Consider adding unit tests that assert shipping cost is zero only when `subtotal - discount >= FREE_SHIPPING_CENTS`.  
- Update `shipping_cost` to use the `discount` argument (or remove it if the rule is intentionally omitted).  

---

# Finding 5, batch 1/1

Claim: | **High** | **Cancel is not idempotent – repeated cancellations restock inventory** | `cancel` method, lines **0622‑0637**<br>`for line in self.db.lines(order_id): … self.db.execute("UPDATE products SET stock = stock + ?, …")` |

## Assessment
UNRESOLVED

No model call was made. Reason: The complete evidence exceeds the configured local token budget.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 11198 tokens; token limit: 8000.


---

# Finding 6, batch 1/1

Claim: | **Medium** | **`_insert_order` stores raw `quote.coupon` object in DB column `coupon`** | `_insert_order`, lines **0592‑0602**<br>`(order_id, request.customer_id, request.request_id, request.fingerprint(), "placed", request.shipping, quote.coupon, …)` |

## Assessment
UNRESOLVED

No model call was made. Reason: The complete evidence exceeds the configured local token budget.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 8309 tokens; token limit: 8000.


---

# Finding 7, batch 1/1

Claim: | **High** | **Cancelled orders are included in sales totals** | `ReportingService.sales` (lines 0710‑0734) – the query<br>`SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS gross_cents, … FROM orders WHERE created_at >= ? AND created_at < ?` does **not** filter out orders whose `status = 'cancelled'`. The business rules state: *“Exclude cancelled orders from order counts and gross sales.”* The function later computes `net_cents = gross_cents - refunded_cents`, so the inflated `gross_cents` propagates to the reported net sales. |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```text
0713: "SELECT COUNT(*) AS order_count, COALESCE(SUM(total_cents), 0) AS gross_cents, "
0714: "COALESCE(SUM(discount_cents), 0) AS discount_cents, "
0715: "COALESCE(SUM(tax_cents), 0) AS tax_cents, "
0716: "COALESCE(SUM(shipping_cents), 0) AS shipping_cents "
0717: "FROM orders WHERE created_at >= ? AND created_at < ?",
```
*Lines 0713‑0717 (ReportingService.sales)* – the `SELECT` pulls **all** rows from `orders` that fall in the date range, with **no condition on `status`**.

## Explanation and limits  
The business rule explicitly requires *“Exclude cancelled orders from order counts and gross sales.”*  
The `sales` method aggregates `total_cents` (gross sales) and `order_count` directly from the `orders` table, but the `WHERE` clause only restricts by `created_at`. Because there is no `status <> 'cancelled'` (or similar) filter, any order whose `status` is `'cancelled'` will still contribute to `order_count` and `gross_cents`.  

The later computation of `net_cents = gross_cents - refunded_cents` does not remove the cancelled portion, so the inflated gross value propagates to the reported net sales. No helper function or subsequent processing step is shown that would subtract cancelled orders, so the claim that cancelled orders are included is directly supported by the source.

*Limitations*:  
- The snippet does not show the schema of `orders`; we assume a `status` column exists (common elsewhere in the code).  
- Even if cancelled orders are later filtered elsewhere, this function’s own query still includes them, violating the rule for this report.  

## Next check  
- Verify the `orders` table schema includes a `status` column and that cancelled orders are stored with a distinct value (e.g., `'cancelled'`).  
- Confirm whether any higher‑level view or wrapper filters cancelled orders before calling `ReportingService.sales`. If not, add a status filter, e.g.:

```sql
... FROM orders 
WHERE created_at >= ? AND created_at < ?
  AND status != 'cancelled'
```

- Review related reporting functions (`top_products`, `customer_summary`, etc.) for similar omissions.

---

# Finding 8, batch 1/1

Claim: | **Medium** | **Average order amount uses Python’s bankers‑rounding, not “round half up”** | `ReportingService.sales` (line 0732) – `result["average_order_cents"] = round(result["gross_cents"] / count) if count else 0`<br>Python’s built‑in `round` implements “round‑to‑even”. The specification for tax rounding (and generally for monetary values) requires *half‑up* rounding. If the average is expected to be presented with the same rounding rule, the current implementation may produce a value that is off by one cent for .5 cases. |

## Assessment  
**NOT AN ESTABLISHED REQUIREMENT**

## Source evidence  
- `ReportingService.sales` implementation:  

  ```python
  0732: result["average_order_cents"] = round(result["gross_cents"] / count) if count else 0
  ```

## Explanation and limits  
The claim correctly identifies that the code uses Python’s built‑in `round`, which applies “round‑to‑even” (bankers‑rounding). However, the business‑rules document only mandates **half‑up rounding for tax calculations**:

> “Tax is 10% of merchandise after discount, rounded half up to the nearest cent.”

No rule specifies how the *average order amount* reported by `ReportingService.sales` must be rounded. Since the specification does not establish a rounding requirement for this field, the use of `round` cannot be judged a defect against the stated requirements. It may be a design choice, but it is not a violation of an explicit rule.

Thus, the claim is **not supported by an established requirement**; it highlights a potential inconsistency with common monetary‑rounding practices, but the current specification does not require half‑up rounding for the average order amount.  

*Missing helpers or callers are irrelevant here; the rounding behavior is directly visible in the function.*  

---  

**Next check**  
If the product’s reporting specifications later demand half‑up rounding for any monetary summary (including averages), the implementation would need to replace `round` with a custom half‑up routine (e.g., using `Decimal` with `ROUND_HALF_UP`). Until such a rule is added, the current behavior is acceptable.

---

# Finding 9, batch 1/1

Claim: | **Low** | **`date_bounds` builds ISO‑8601 strings by concatenating a suffix** | `ReportingService.date_bounds` (lines 0700‑0708) – `return first.isoformat() + "T00:00:00+00:00", after.isoformat() + "T00:00:00+00:00"`<br>`first` and `after` are `date` objects; `isoformat()` yields `"YYYY‑MM‑DD"`. Concatenating the suffix works, but it relies on the caller never passing a `datetime` object. If the implementation of `parse_day` were to change to return a `datetime`, the resulting string would contain an extra time component (e.g., `"2023‑01‑01T00:00:00+00:00T00:00:00+00:00"`). This could break date filtering in all reporting queries. |

## Assessment  
**UNRESOLVED**

## Source evidence  
- `parse_day` returns a **date** object:  

  ```python
  0074: def parse_day(value: str) -> date:
  0075:     try:
  0076:         return date.fromisoformat(value)
  ```  

- `ReportingService.date_bounds` builds the ISO‑8601 strings by concatenating a suffix to the result of `date.isoformat()`:

  ```python
  0700: def date_bounds(self, start: str, end: str) -> tuple[str, str]:
  0701:     first = parse_day(start)
  0702:     last = parse_day(end)
  ...
  0708:     return first.isoformat() + "T00:00:00+00:00", after.isoformat() + "T00:00:00+00:00"
  ```

## Explanation and limits  
The claim points out that concatenating `"T00:00:00+00:00"` to `first.isoformat()` (and `after.isoformat()`) is safe only while `first` and `after` are **date** objects. With the current implementation of `parse_day`, they are indeed dates, so the resulting strings are well‑formed timestamps (e.g., `"2023-01-01T00:00:00+00:00"`).  

The alleged risk—`parse_day` returning a `datetime` and producing a double‑suffix string such as `"2023-01-01T00:00:00+00:00T00:00:00+00:00"`—is **speculative**. The source shows no alternative implementation of `parse_day` that would return a `datetime`, nor any caller that passes a `datetime` directly to `date_bounds`. Therefore, there is no concrete evidence in the supplied code that this bug manifests now.

The design is indeed fragile: a future change to `parse_day` could introduce the described problem. However, without an existing implementation change or a caller that supplies a `datetime`, the claim remains an unverified potential issue rather than a proven defect.

## Next check  
- Verify whether any other module (not shown) overrides or monkey‑patches `parse_day` to return a `datetime`.  
- Look for callers of `ReportingService.date_bounds` that might pass pre‑parsed `datetime` objects instead of strings.  
- Consider adding a type‑check or using `datetime.combine` to construct the timestamp explicitly, which would make the function robust against future changes.

---

# Finding 10, batch 1/1

Claim: | **Low** | **`export_orders` does not validate that the requested date range is non‑empty** | `ReportingService.export_orders` (lines 0784‑0800) – after calling `date_bounds`, the function proceeds even if `start` and `end` represent the same day (resulting in an empty result set). While not a correctness error per se, the business rule for reports expects a *valid* range; an empty export may be surprising to callers. |

## Assessment  
**NOT AN ESTABLISHED REQUIREMENT**

## Source evidence  
- `ReportingService.date_bounds` (lines 0701‑0705):  

  ```python
  first = parse_day(start)
  last = parse_day(end)
  if first > last:
      raise ServiceError("Start date must not be after end date")
  ```  

  No check that `first == last` is disallowed.  

- `ReportingService.export_orders` (lines 0784‑0786, 0789‑0793):  

  ```python
  lower, upper = self.date_bounds(start, end)
  rows = self.db.all(
      "SELECT … FROM orders WHERE created_at >= ? AND created_at < ? …",
      (lower, upper),
  )
  ```  

  The query uses `>= lower` and `< upper`, where `upper` is `last + 1 day` (see line 0707).  

## Explanation and limits  
The code permits `start` and `end` to be the same calendar day. In that case `date_bounds` returns a lower bound at `00:00:00` of the day and an upper bound at `00:00:00` of the following day, so the SQL `WHERE` clause selects all orders created **on that day**. This is a one‑day range, not an empty range.  

The business rules only require “inclusive start/end dates” for reports; they do **not** mandate that the range contain more than one day or that it be non‑empty. Therefore, the lack of an explicit “non‑empty range” validation is not a violation of the stated requirements.  

If the caller supplies a day on which no orders exist, the result set will naturally be empty, but that is a data‑driven outcome, not a missing validation.  

## Next check  
- Verify that other reporting functions (`sales`, `top_products`, etc.) also rely on `date_bounds` and that they behave consistently for same‑day ranges.  
- Ensure callers understand that an empty CSV simply reflects no orders in the requested period, not a validation error.  

---

# Finding 11, batch 1/1

Claim: | **High** | **Partial import may leave the system in an inconsistent state** | `import_orders` – lines 857‑879<br>```python\n857: def import_orders(db: Database, path: Path, now: datetime) -> dict:\n858:     if path.stat().st_size > 1_000_000:\n859:         raise ServiceError(\"Import exceeds 1000000 bytes\")\n860:     service = OrderService(db)\n861:     accepted = []\n862:     rejected = []\n863:     with path.open(encoding=\"utf-8\") as stream:\n864:         for number, line in enumerate(stream, 1):\n865:             ...\n874:             try:\n875:                 value = json.loads(line)\n876:                 ...\n877:                 order = service.checkout(request, now)\n878:                 accepted.append({\"line\": number, \"order_id\": order[\"order_id\"]})\n879:             except (ServiceError, json.JSONDecodeError) as exc:\n880:                 rejected.append({\"line\": number, \"error\": str(exc)})\n```<br>**What the code does** – The function reads a line‑by‑line JSON‑L file, calls `OrderService.checkout` for each line, and records the result. Only `ServiceError` and `json.JSONDecodeError` are caught; any other exception (e.g., `KeyError`, database errors, programming bugs) propagates out of the loop and aborts the import.<br>**Why this can affect totals/stock** – `checkout` creates an order and reserves stock. If an unexpected exception occurs after some orders have been successfully processed, the function stops processing the remaining lines, leaving the earlier orders committed. The caller receives a partially‑filled result dict, but the import operation is considered “failed” from the caller’s perspective, which may lead to duplicate re‑imports or manual retries that double‑reserve stock and inflate totals.<br>**Assumptions / missing context** – We assume `OrderService.checkout` commits its changes inside its own transaction (common pattern). The surrounding code does not start a surrounding transaction that could roll back all processed lines on failure.<br>**What to check next** – Verify whether `OrderService.checkout` runs in its own transaction and whether the import routine is expected to be atomic. If atomicity is required, wrap the whole loop in a transaction or catch a broader set of exceptions and roll back any partial work. |

## Assessment
UNRESOLVED

No model call was made. Reason: The complete evidence exceeds the configured local token budget.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 8058 tokens; token limit: 8000.


---

# Finding 12, batch 1/1

Claim: | **Medium** | **`seed_demo` treats any existing metadata row as “already seeded”** | `seed_demo` – lines 835‑839<br>```python\n835: def seed_demo(db: Database, now: datetime) -> dict:\n836:     with db.transaction():\n837:         if db.one(\"SELECT value FROM metadata WHERE key = 'seeded'\"):\n838:             return {\"seeded\": False, \"message\": \"Demo data already exists\"}\n```<br>**What the code does** – It queries the `metadata` table for a row with key `'seeded'`. If the query returns any truthy value, the function aborts seeding and reports that demo data already exists.<br>**Why this can affect totals/stock** – The check does not verify the *value* of the row (e.g., a timestamp). If a previous run inserted the row but failed part‑way (e.g., only some customers were added), a subsequent call will think the demo data is fully present and skip inserting the missing products or coupons. This can leave the database with incomplete product rows and therefore incorrect initial stock levels, which later order calculations will use.<br>**Assumptions / missing context** – We assume `db.one` returns `None` when no row exists and a non‑`None` value otherwise. The exact schema of `metadata` is not shown, but the code only cares about existence, not content.<br>**What to check next** – Inspect the `metadata` table schema and the semantics of the `'seeded'` key. Consider storing a flag that indicates successful completion (e.g., a boolean) or performing a more robust “already seeded” detection (e.g., count of expected rows). |

## Assessment
UNRESOLVED

No model call was made. Reason: Related source context is 31395 characters; the limit is 30000. Planning stopped without API calls. No source was split or truncated. A strategy for larger evidence sets is required.

The finding remains unresolved. No source was split or truncated.

Estimated request budget: 4576 tokens; token limit: 8000.


---

# Finding 13, batch 1/1

Claim: | **High** | **Missing validation of restock quantity sign** | `0915‑0918` –<br>`restock = commands.add_parser(\"restock\")`<br>`restock.add_argument(\"sku\")`<br>`restock.add_argument(\"--quantity\", type=int, required=True)`<br>`restock.add_argument(\"--reason\", required=True)` |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `CatalogService.restock` validates the quantity:  

  ```python
  0446: def restock(self, sku: str, quantity: int, reason: str, now: datetime) -> dict:
  0447:     integer(quantity, "quantity", 1, 100_000)   # ← enforces ≥ 1
  0448:     reason = nonempty(reason, "reason", 200)
  ```

- The `integer` helper (lines 0090‑0094) raises an error unless the value is an integer within the supplied bounds:

  ```python
  0090: def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
  0091:     if isinstance(value, bool) or not isinstance(value, int):
  0092:         raise ServiceError(f"{name} must be an integer")
  0093:     if not minimum <= value <= maximum:
  0094:         raise ServiceError(f"{name} must be between {minimum} and {maximum}")
  ```

## Explanation and limits  
The claim states that the restock command lacks validation of the quantity’s sign (i.e., that it must be positive). While the argument parser (`restock.add_argument("--quantity", type=int, required=True)`) only ensures the value is an `int`, the service method immediately calls `integer(quantity, "quantity", 1, 100_000)`. This helper enforces a **minimum of 1**, rejecting zero, negative, or non‑integer values with a `ServiceError`. Therefore the implementation **does** validate the sign of the restock quantity, directly contradicting the claim.

The parser‑level code referenced in the claim (lines 0915‑0918) is not shown in the provided source, but even if it omitted sign checks, the downstream validation in `CatalogService.restock` guarantees correct behavior. No other code paths invoke `restock` without this check, and no alternative helper is used that could bypass it.

Thus, the evidence refutes the assertion that the restock quantity sign is unchecked.

## Next check  
- Verify that the `integer` helper is used consistently for any other quantity‑related inputs (e.g., checkout line quantities) to ensure sign validation throughout the system.  
- Ensure that error messages from `integer` are appropriately surfaced to the CLI user.  