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