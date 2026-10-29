# Source verification assessments

Outcome: verification_incomplete

Model assessments require human validation. Blocked, failed, and unprocessed tasks are unresolved. No runtime reproduction or fix verification was performed.

Unprocessed tasks: []

# Finding 1, batch 1/1

Claim: | **Medium** | **`read_json` does not handle a missing file** | Lines **126‑133**:<br>`def read_json(path: Path) -> dict[str, Any]:`<br>`    if path.stat().st_size > 100_000:`<br>`        raise ServiceError(\"Request file exceeds 100000 bytes\")`<br>`    try:`<br>`        value = json.loads(path.read_text(encoding=\"utf-8\"))`<br>`    except (UnicodeError, json.JSONDecodeError) as exc:`<br>`        raise ServiceError(\"Request must be a UTF‑8 JSON document\") from exc` | The function calls `path.stat()` and `path.read_text()` **without** first checking that the file exists. If the supplied path does not exist, Python raises `FileNotFoundError`, which propagates out of `read_json` as an unhandled exception. | A checkout, catalog import, or any command that reads a JSON request will abort with a traceback instead of returning a controlled `ServiceError`. The caller will not get a chance to roll back a transaction, release any reserved stock, or compute a total. This can leave the database in an inconsistent state (e.g., a partially‑created order) and break the “stock must not be partially reserved” rule. |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0126: def read_json(path: Path) -> dict[str, Any]:
0127:     if path.stat().st_size > 100_000:
0128:         raise ServiceError("Request file exceeds 100000 bytes")
0129:     try:
0130:         value = json.loads(path.read_text(encoding="utf-8"))
0131:     except (UnicodeError, json.JSONDecodeError) as exc:
0132:         raise ServiceError("Request must be a UTF‑8 JSON document") from exc
```
*Lines 0126‑0130* show `path.stat()` and `path.read_text()` called directly, with no prior existence check or `except FileNotFoundError`.

## Explanation and limits  
The function assumes the supplied `Path` points to an existing file. If the file does not exist, `path.stat()` raises `FileNotFoundError`, which is **not** caught by the surrounding `try/except`. Consequently the exception propagates out of `read_json` as an uncaught error, bypassing the intended `ServiceError` handling.

`read_json` is used by the command dispatcher (see lines 0991‑0994) for checkout, quote, and other JSON‑based commands. Those callers only anticipate `ServiceError`; they do not catch `FileNotFoundError`. Therefore a missing request file will abort the command with a traceback, preventing any cleanup (e.g., rolling back a reservation) and potentially leaving the system in an inconsistent state. This directly violates the business rule that “stock must not be partially reserved” because a failure during checkout could leave a reservation half‑done.

No other helper in the provided excerpts performs a pre‑check for file existence before calling `read_json`, so the defect is not mitigated elsewhere.

## Next check  
* Verify whether any higher‑level entry point (e.g., the CLI wrapper) catches generic exceptions and converts them to `ServiceError`. If not, add an explicit existence check (`if not path.is_file(): raise ServiceError("Request file not found")`) or catch `FileNotFoundError` inside `read_json` and re‑raise as `ServiceError`.  
* Review other file‑reading utilities (e.g., `import_orders`, `write_invoice`) for similar missing‑file handling.  
* Ensure that any transaction‑related code surrounding `orders.checkout` correctly rolls back when `read_json` raises an exception.  

---

# Finding 2, batch 1/1

Claim: | **High** | **Subtotal calculated from unit price instead of line total** | `quote` method (lines 0522‑0524):<br>`lines = self.price_lines(request.lines)`<br>`subtotal = sum(line.unit_price_cents for line in lines)` | `price_lines` creates a `PricedLine` that contains both `unit_price_cents` **and** `line_total_cents` (line 0489). The subtotal of an order must be the sum of *line totals* (price × quantity). Summing only the unit price ignores the quantity, so any line with `quantity > 1` under‑states the merchandise subtotal, which in turn reduces the computed discount, tax, and final total. This directly violates the business rule “Merchandise subtotal is the sum of unit price multiplied by quantity for every cart line.” |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.price_lines` creates a `PricedLine` that includes both `unit_price_cents` **and** `line_total_cents` (line 0489).  
- In `PricingService.quote` the subtotal is computed as:  

```python
0522: lines = self.price_lines(request.lines)
0523: subtotal = sum(line.unit_price_cents for line in lines)   # ← uses only unit price
```

## Explanation and limits  
The business rule states that *“Merchandise subtotal is the sum of unit price multiplied by quantity for every cart line.”*  
`price_lines` correctly calculates `line_total_cents = product.price_cents * line.quantity` (line 0489), but `quote` ignores this field and sums only `unit_price_cents`. For any cart line where `quantity > 1`, the subtotal will be too low by a factor of `(quantity‑1) * unit_price_cents`. Consequently:

- **Discount** (which depends on subtotal) may be smaller than intended.  
- **Tax** (10 % of subtotal‑discount) will also be reduced.  
- **Total** (`taxable + tax + shipping`) will be understated.

No other helper in the shown code recomputes the subtotal from `line_total_cents`, nor is there a later correction. Therefore the claim that the subtotal is calculated from unit price instead of line total is directly supported by the source.

## Next check  
Verify that no downstream logic (e.g., in reporting or order persistence) re‑derives the subtotal from `line_total_cents`. If such logic exists, it could mask the bug for some operations but would not fix the incorrect total returned to the caller. Ensure that the subtotal calculation is updated to:

```python
subtotal = sum(line.line_total_cents for line in lines)
```

---

# Finding 5, batch 1/1

Claim: | **High** | **Cancel is not idempotent – repeated cancellations restock inventory** | `cancel` method, lines **0622‑0637**<br>`for line in self.db.lines(order_id): … self.db.execute("UPDATE products SET stock = stock + ?, …")` |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0622: def cancel(self, order_id: str, reason: str, now: datetime) -> dict:
0623:     reason = nonempty(reason, "reason", 200)
0624:     with self.db.transaction():
0625:         order = self.db.order(order_id)
0626:         if order["status"] == "shipped":
0627:             raise Conflict("A shipped order cannot be cancelled")
0628:         for line in self.db.lines(order_id):
0629:             self.db.execute("UPDATE products SET stock = stock + ?, updated_at = ? "
0630:                             "WHERE sku = ?",
0631:                             (line["quantity"], timestamp(now), line["sku"]))
0632:             self.db.inventory_event(line["sku"], line["quantity"],
0633:                                 "cancellation", now, order_id)
0634:         self.db.execute("UPDATE orders SET status = 'cancelled', updated_at = ? "
0635:                         "WHERE order_id = ?", (timestamp(now), order_id))
0636:         self.db.audit("order", order_id, "cancelled", {"reason": reason}, now)
0637:     return self.view(order_id)
```

## Explanation and limits  
The method checks only for a **shipped** status (line 0626‑0627). It does **not** verify whether the order is already in the **cancelled** state before performing the restocking loop (lines 0628‑0633). Consequently, invoking `cancel` a second time on the same order will:

1. Execute the `UPDATE products SET stock = stock + …` statement again for each line, adding the same quantity back to inventory a second time.  
2. Record another inventory event of type `"cancellation"` (line 0632).  
3. Overwrite the order status with `'cancelled'` again (no state change).  

Thus, repeated cancellations are **not idempotent** and will inflate stock counts, violating the business rule that “Repeating cancellation must not add stock again.” The code lacks a guard such as `if order["status"] == "cancelled": return …` or similar.

The evidence is confined to the `cancel` method; no other part of the provided source shows additional checks (e.g., in a higher‑level dispatcher) that would prevent a second call. Therefore, based on the available code, the claim is supported.

## Next check  
* Verify whether any external wrapper or command‑line logic prevents duplicate cancellation calls (e.g., by tracking request IDs).  
* Ensure that audit logs or other services do not enforce idempotency elsewhere.  
* Review tests or documentation for expected cancellation behavior.  

---

# Finding 6, batch 1/1

Claim: | **Medium** | **`_insert_order` stores raw `quote.coupon` object in DB column `coupon`** | `_insert_order`, lines **0592‑0602**<br>`(order_id, request.customer_id, request.request_id, request.fingerprint(), "placed", request.shipping, quote.coupon, …)` |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `Quote` definition shows the coupon field is a simple value:  

  ```python
  0226:     coupon: str | None
  ```  

- `_insert_order` inserts the value of `quote.coupon` directly into the `coupon` column:  

  ```python
  0599‑0602: (order_id, request.customer_id, request.request_id, request.fingerprint(),
              "placed", request.shipping, quote.coupon, quote.subtotal_cents,
              quote.discount_cents, quote.shipping_cents, quote.tax_cents,
              quote.total_cents, timestamp(now), timestamp(now)),
  ```

## Explanation and limits  
The claim states that a *raw* `quote.coupon` object is stored, implying a complex, possibly mutable object is persisted. The source shows `quote.coupon` is typed as `str | None`, i.e., a plain coupon code string (or `None`). Storing this string in the `coupon` column is consistent with the data model and does not constitute a bug. No evidence suggests that `quote.coupon` is anything other than a scalar identifier, so the assertion that a raw object is stored is directly contradicted by the type annotation and the insertion code.

## Next check  
- Verify that the `coupon` column in the database schema is defined to hold a text value (e.g., `TEXT`), matching the stored string.  
- Ensure that any later processing of the stored coupon code correctly interprets it (e.g., joins to a coupons table) rather than assuming it contains richer data.  

*Note: The absence of a more complex coupon object here does not guarantee overall coupon handling correctness; other parts of the system (e.g., validation, usage counting) should still be reviewed.*

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
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0837: if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):
0838:     return {"seeded": False, "message": "Demo data already exists"}
```
`Database.one` returns a row object when the query finds a matching row and `None` otherwise (see lines 0348‑0349). The condition therefore tests only for the *existence* of a row with key `'seeded'`, not its contents.

## Explanation and limits  
The `seed_demo` function aborts seeding whenever a row with key `'seeded'` is present, regardless of the stored `value`. The later insertion (line 0851) stores a timestamp as the value, but the early‑return logic never inspects that timestamp. Consequently, if a previous invocation created the metadata row but failed before inserting all customers, products, or coupons, a subsequent call will incorrectly assume the demo data is fully present and skip the missing inserts. This can leave the database without some products or coupons, leading to wrong merchandise subtotals, stock levels, and coupon availability in later order processing.

The claim is directly reflected in the source; no counter‑evidence (e.g., a later value check) exists in the provided code.

## Next check  
* Verify the schema of the `metadata` table (does it enforce a single row per key?).  
* Consider adding a more robust “seeded” flag, such as a boolean column or a sentinel value indicating successful completion, or wrap the entire seeding block in a try/except that removes the metadata row on failure.  
* Ensure that any partial failure cleans up inserted rows or rolls back the transaction (the surrounding `db.transaction()` will roll back on exception, but the early return bypasses that).  