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