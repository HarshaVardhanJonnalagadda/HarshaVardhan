# Source verification assessments

Outcome: verification_calls_complete

Model assessments require human validation. Blocked, failed, and unprocessed tasks are unresolved. No runtime reproduction or fix verification was performed.

Unprocessed tasks: []

# Finding 1, batch 1/1

Claim: | **Medium** | **`read_json` does not handle a missing file** | Lines **126‑133**:<br>`def read_json(path: Path) -> dict[str, Any]:`<br>`    if path.stat().st_size > 100_000:`<br>`        raise ServiceError(\"Request file exceeds 100000 bytes\")`<br>`    try:`<br>`        value = json.loads(path.read_text(encoding=\"utf-8\"))`<br>`    except (UnicodeError, json.JSONDecodeError) as exc:`<br>`        raise ServiceError(\"Request must be a UTF‑8 JSON document\") from exc` | The function calls `path.stat()` and `path.read_text()` **without** first checking that the file exists. If the supplied path does not exist, Python raises `FileNotFoundError`, which propagates out of `read_json` as an unhandled exception. | A checkout, catalog import, or any command that reads a JSON request will abort with a traceback instead of returning a controlled `ServiceError`. The caller will not get a chance to roll back a transaction, release any reserved stock, or compute a total. This can leave the database in an inconsistent state (e.g., a partially‑created order) and break the “stock must not be partially reserved” rule. |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `read_json` implementation:  

  ```python
  0126: def read_json(path: Path) -> dict[str, Any]:
  0127:     if path.stat().st_size > 100_000:
  0128:         raise ServiceError("Request file exceeds 100000 bytes")
  0129:         # …
  0130:         value = json.loads(path.read_text(encoding="utf-8"))
  ```  

- Top‑level entry point catches `OSError` (the base class of `FileNotFoundError`):  

  ```python
  1050: except (ServiceError, OSError, sqlite3.Error) as exc:
  1051:     print(f"Error: {exc}", file=sys.stderr)
  ```

## Explanation and limits  
`read_json` calls `path.stat()` and `path.read_text()` without first checking that the file exists. If the supplied path does not exist, Python raises `FileNotFoundError`. However, `FileNotFoundError` is a subclass of `OSError`, and the `main` function wraps the entire command dispatch in a `try`/`except` that catches `OSError` (line 1050). Consequently the exception is **handled**, producing a user‑visible error message and terminating with exit code 1.  

Because the exception occurs before any database work (the call to `read_json` happens at the start of the `checkout`/`quote` command handling), there is no risk of partially reserved stock or an incomplete transaction. The claim that the missing‑file case “propagates out of `read_json` as an unhandled exception” is therefore inaccurate given the surrounding code.

The only shortcoming is that the error is reported as a generic `OSError` rather than a domain‑specific `ServiceError`, which could make the message less consistent with other validation errors. Nonetheless, the behavior does not leave the system in an inconsistent state, and the exception is not unhandled.

## Next check  
If a more uniform error type is desired, consider wrapping the `FileNotFoundError` in a `ServiceError` inside `read_json`. Verify that any future callers that rely on catching only `ServiceError` are updated accordingly.

---

# Finding 12, batch 1/1

Claim: | **Medium** | **`seed_demo` treats any existing metadata row as “already seeded”** | `seed_demo` – lines 835‑839<br>```python\n835: def seed_demo(db: Database, now: datetime) -> dict:\n836:     with db.transaction():\n837:         if db.one(\"SELECT value FROM metadata WHERE key = 'seeded'\"):\n838:             return {\"seeded\": False, \"message\": \"Demo data already exists\"}\n```<br>**What the code does** – It queries the `metadata` table for a row with key `'seeded'`. If the query returns any truthy value, the function aborts seeding and reports that demo data already exists.<br>**Why this can affect totals/stock** – The check does not verify the *value* of the row (e.g., a timestamp). If a previous run inserted the row but failed part‑way (e.g., only some customers were added), a subsequent call will think the demo data is fully present and skip inserting the missing products or coupons. This can leave the database with incomplete product rows and therefore incorrect initial stock levels, which later order calculations will use.<br>**Assumptions / missing context** – We assume `db.one` returns `None` when no row exists and a non‑`None` value otherwise. The exact schema of `metadata` is not shown, but the code only cares about existence, not content.<br>**What to check next** – Inspect the `metadata` table schema and the semantics of the `'seeded'` key. Consider storing a flag that indicates successful completion (e.g., a boolean) or performing a more robust “already seeded” detection (e.g., count of expected rows). |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0835: def seed_demo(db: Database, now: datetime) -> dict:
0836:     with db.transaction():
0837:         if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):
0838:             return {"seeded": False, "message": "Demo data already exists"}
```
`Database.one` returns a row when the query matches (see lines 0348‑0349), so the `if` condition is true for **any** existing row with key `'seeded'`, regardless of its `value`.

## Explanation and limits  
The function checks only for the presence of a metadata row with key `'seeded'`. It does **not** inspect the stored `value` (which is a timestamp inserted later at line 0851). Consequently, if a prior invocation created the `'seeded'` row but failed before inserting the demo customers, products, or coupons, a subsequent call will hit the early‑return at line 0838 and skip the rest of the seeding logic (lines 0840‑0851).  

Because the demo products (including their initial stock) are inserted only after this guard, an incomplete prior run can leave the database without those product rows or inventory events. Later order processing that relies on product definitions and stock levels would then compute incorrect merchandise subtotals or reject orders due to missing SKUs, directly affecting totals and stock accuracy.

The claim about “treats any existing metadata row as ‘already seeded’” is directly evidenced by the code. The downstream impact on totals/stock is a logical consequence of the seeding flow, though the source does not show a concrete partial‑seed scenario; the risk is inferred from the guard’s semantics.  

**Missing context / limits**  
- The schema of `metadata` is not shown, but the guard’s logic is independent of the `value` column.  
- No explicit validation of the `'seeded'` value exists elsewhere, so the guard remains the sole determinant.  
- The claim about affecting totals/stock assumes a prior failure; the source does not contain such a failure case, but the possibility is real given the guard’s design.  