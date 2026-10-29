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