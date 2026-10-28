## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **`seed_demo` may raise an exception when the `metadata` table is empty** | `seed_demo` – lines **837‑839**:<br>`if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` |
| **Medium** | **`reconcile_inventory` can report false mismatches when a product has no inventory events** | `reconcile_inventory` – lines **777‑782** (the `LEFT JOIN` query that groups by `p.sku, p.stock` but does not coalesce `SUM(e.delta)` to `0`) |
| **Low** | **`export_orders` does not guard against the target path being a directory** | `export_orders` – lines **796‑800** (opens the file with mode `"x"`; if `path` points to an existing directory, `IsADirectoryError` propagates) |
| **Low** | **`import_orders` silently stops processing after the first line that exceeds the 1 000‑line limit** | `import_orders` – lines **867‑870** (breaks out of the loop after adding a single rejected entry) |

### What the code demonstrably does  

| Finding | Behaviour |
|--------|-----------|
| **`seed_demo`** – The call to `db.one(...)` expects a row to exist. If the `metadata` table has no row with key `'seeded'` (the usual case on a fresh database), the underlying `Database.one()` implementation will raise an exception (e.g., `IndexError` or a custom `DatabaseError`). The function never reaches the insertion of demo customers, products, or coupons, so the inventory ledger is never populated. |
| **`reconcile_inventory`** – The query `FROM products p LEFT JOIN inventory_events e ON e.sku = p.sku GROUP BY p.sku, p.stock` returns one row per product. When a product has **no** inventory events, `SUM(e.delta)` evaluates to `NULL`. The returned dict contains `"ledger_stock": row["ledger_stock"]` (which will be `None`) and `"matches": row["stock"] == row["ledger_stock"]`. Because `None != <int>`, the `matches` flag is `False`, causing the health endpoint to list a spurious inventory mismatch. |
| **`export_orders`** – The function checks that the parent directory exists, then opens the target file with mode `"x"` (exclusive‑create). If `path` already exists **as a directory**, Python raises `IsADirectoryError`. The exception is not caught, so the whole request fails with a 500‑type error instead of returning a clean “file already exists” message. |
| **`import_orders`** – After line 1000 the loop executes `break`, leaving the remaining lines unprocessed and unreported. The caller receives a `rejected` list that mentions only the first line that crossed the limit, which can be misleading when many lines are ignored. |

### How the behaviour could affect totals or stock  

| Finding | Potential impact on totals / stock |
|--------|------------------------------------|
| **`seed_demo`** – If demo data is not seeded, the product table may contain rows with a `stock` value but **no corresponding opening‑stock inventory events**. Subsequent calls to `reconcile_inventory` (used by `health`) will flag mismatches, and any logic that relies on the ledger (e.g., stock‑reservation checks) could treat the inventory as unavailable, causing orders to be rejected or stock counts to be wrong. |
| **`reconcile_inventory`** – False mismatches in the health report may mask real inventory problems or, conversely, cause operators to think the system is inconsistent when it is not. If other parts of the service (not shown) use the same query to decide whether to allow a reservation, a `NULL` ledger total could be interpreted as “no stock”, preventing legitimate sales and thus affecting total sales figures. |
| **`export_orders`** – A crash when the export path points to a directory prevents the generation of the CSV report. While this does not directly change monetary totals, it blocks a key audit mechanism that stakeholders use to verify that order totals and stock movements are correct. |
| **`import_orders`** – Silently dropping lines after the 1 000‑line limit can lead to many orders never being created. The missing orders mean the system’s recorded totals (gross sales, inventory reservations, etc.) will be lower than the source data, producing inaccurate reports. |

## Uncertainty  

| Area | Why the evidence is insufficient |
|------|-----------------------------------|
| **Exact shape of `reconcile_inventory` result** – The snippet shows only the `SELECT` string and the list‑comprehension that builds the return value. We do not see the column alias for the summed ledger (`ledger_stock`). If the query already uses `COALESCE(SUM(e.delta), 0) AS ledger_stock`, the `NULL` issue would not exist. |
| **Implementation of `Database.one`** – The behaviour when the query returns no rows is unknown. If `Database.one` returns `None` instead of raising, the `if db.one(...):` check would simply evaluate to `False` and the seeding would proceed correctly. |
| **How `health`’s `inventory_mismatches` list is used** – If the health endpoint is only for diagnostics and never consulted by order‑processing logic, the false‑positive mismatches may be harmless. |
| **Whether other code validates the export path** – There may be higher‑level validation that prevents a directory path from being passed to `export_orders`. |

## Next checks  

1. **Inspect `Database.one` implementation** – Confirm whether it raises on “no rows” or returns `None`. If it raises, wrap the call in a try/except or use a `SELECT EXISTS` pattern.  
2. **Review the full `reconcile_inventory` SQL** – Verify that the `SUM(e.delta)` column is wrapped with `COALESCE(..., 0)` (or similar) to avoid `NULL` ledger totals for products without events.  
3. **Search for any callers of `health` that rely on `inventory_mismatches`** – Determine whether false mismatches could block order placement or affect reporting.  
4. **Add a guard in `export_orders`** – Before opening the file, check `if path.exists(): raise ServiceError("Export file already exists")` to provide a clearer error and avoid `IsADirectoryError`.  
5. **Consider handling the line‑limit case in `import_orders`** – Instead of `break`, continue reading the file and record each excess line as rejected, or stop after the limit but clearly document that remaining lines are ignored.  
6. **Run integration tests that seed a fresh database** – Verify that `seed_demo` runs without error on an empty `metadata` table and that the resulting inventory ledger matches the product `stock` values.  

These steps will confirm whether the identified high‑ and medium‑severity issues are real bugs and will help ensure that order totals and stock levels remain accurate.