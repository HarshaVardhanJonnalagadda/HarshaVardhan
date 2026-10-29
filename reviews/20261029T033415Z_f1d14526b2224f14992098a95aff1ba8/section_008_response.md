## Findings

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **High** | **Missing validation of restock quantity sign** | `0915‑0918` –<br>`restock = commands.add_parser(\"restock\")`<br>`restock.add_argument(\"sku\")`<br>`restock.add_argument(\"--quantity\", type=int, required=True)`<br>`restock.add_argument(\"--reason\", required=True)` |

**Evidence status:** SUPPORTED IN SUPPLIED CODE.  

**What the supplied code demonstrably does**  
The CLI parser defines a `restock` sub‑command that requires a `--quantity` argument of type `int`. No further constraints (e.g., `choices`, `type=lambda x: int(x) if int(x) > 0 else argparse.ArgumentTypeError`) are applied, so any integer – positive, zero, or negative – will be accepted by the parser.

**How that behavior could cause the reported problem**  
The business rule *“Checkout must reserve the requested quantities and create the order together, or do neither. A stock shortage must not partially reserve a cart.”* and the related inventory rules assume that a **restock** operation only **adds** stock. If a caller supplies a negative quantity, the downstream handler (not shown in this fragment) will likely add the supplied value to the current inventory count, effectively **subtracting** stock. This can corrupt inventory totals, allow overselling, and produce incorrect order‑fulfilment decisions.

**Assumptions / missing cross‑function evidence**  
* The implementation of the `restock` command (the function that receives the parsed arguments and updates the database) is not present in the supplied fragment. The finding assumes that the handler uses the parsed `quantity` value directly to adjust inventory (e.g., `stock += quantity`). If the handler contains its own guard against negative values, the bug would be mitigated, but that guard is not visible here.

**What should be checked next**  
1. Locate the function that processes the `restock` command (likely something like `def restock(db, sku, quantity, reason): …`). Verify whether it validates that `quantity > 0` before applying the change.  
2. If the validation is missing there, add a check either in the parser (e.g., `type=lambda x: int(x) if int(x) > 0 else argparse.ArgumentTypeError('quantity must be positive')`) or in the command handler, raising a clear `ServiceError` for non‑positive values.  
3. Add unit tests that attempt to restock with `--quantity -5` (or `0`) and assert that the operation is rejected and that inventory levels remain unchanged.  

---

## Uncertainty

| Area | Why uncertain |
|------|----------------|
| **Restock implementation** | The fragment does not include the code that actually updates inventory. Without seeing that code we cannot definitively state that a negative quantity will be applied to stock. |
| **Other commands that accept numeric input** (e.g., `set-price --amount`, `refund --amount`) | The parser accepts strings for these arguments; validation may occur later. Their correctness with respect to totals cannot be confirmed from this section alone. |

These items should be examined in the surrounding sections of the source file.

---

## Next checks

1. **Inspect the restock handler** – confirm it does not accept negative quantities or, if it does, that it explicitly rejects them.  
2. **Review other numeric‑argument commands** (`set-price`, `refund`, `order`‑related commands) for similar missing positivity checks that could affect monetary totals or inventory.  
3. **Run integration tests** that simulate a full checkout‑cancel‑restock cycle, verifying that inventory never goes below zero and that order totals remain consistent after each operation.  

If the restock handler already validates the sign, the immediate risk is mitigated; otherwise, add the validation as described above.