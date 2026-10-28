# Source verification assessments

Outcome: verification_incomplete

Model assessments require human validation. Blocked, failed, and unprocessed tasks are unresolved. No runtime reproduction or fix verification was performed.

Unprocessed tasks: [10, 11]

# Finding 1, batch 1/1

Claim: | **High** | Subtotal may ignore quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |

**## Assessment**  
**SUPPORTED IN THIS BATCH**

**## Source evidence**  
- `PricingService.quote` – line 0523:  

  ```python
  subtotal = sum(line.unit_price_cents for line in lines)
  ```

**## Explanation and limits**  
The implementation computes `subtotal` by iterating over the priced lines and adding only `line.unit_price_cents`. Each `PricedLine` also contains `line_total_cents`, which is calculated as `product.price_cents * line.quantity` in `PricingService.price_lines` (lines 0488‑0489). By ignoring `line_total_cents` (or `quantity`), the subtotal reflects the sum of a single unit price per SKU, regardless of how many units were ordered.  

According to the business rules, *“Merchandise subtotal is the sum of unit price multiplied by quantity for every cart line.”* Therefore the current code under‑calculates the subtotal whenever any line has a quantity > 1, leading to downstream errors in discount, tax, shipping, and total calculations. The defect is directly observable from the source; no helper elsewhere compensates for the missing multiplication.

**## Next check**  
- Verify that `Quote.total_cents` uses the computed `subtotal` (it does: `total_cents=taxable + tax + shipping`).  
- Ensure that any downstream logic (e.g., order creation, reporting) does not re‑apply the quantity factor, which would mask the bug.  
- Consider adding a test case with a multi‑quantity cart line to confirm the discrepancy.  

---

# Finding 2, batch 1/1

Claim: | **Medium** | Free‑shipping rule checks pre‑discount subtotal, not post‑discount as required. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `PricingService.shipping_cost` definition (lines 0511‑0516):  

  ```python
  0511: def shipping_cost(self, method: str, subtotal: int, discount: int) -> int:
  0512:     if method == "pickup":
  0513:         return 0
  0514:     if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:
  0515:         return 0
  0516:     return SHIPPING_CENTS[method]
  ```

- Call site in `PricingService.quote` (lines 0524‑0525):  

  ```python
  0524: discount = self.coupon_discount(request.coupon, subtotal, now)
  0525: shipping = self.shipping_cost(request.shipping, subtotal, discount)
  ```

## Explanation and limits  
The business rule states that **standard shipping is free when merchandise *after discount* is at least 10,000 cents**. The code’s `shipping_cost` receives both `subtotal` (pre‑discount) and `discount`, but the free‑shipping check (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS`) uses only `subtotal`. It never incorporates `discount`, so the condition is evaluated on the pre‑discount amount, contrary to the rule.

Consequences: an order whose pre‑discount subtotal exceeds 10 000 cents will receive free standard shipping even if a coupon reduces the post‑discount amount below that threshold. Conversely, an order that meets the free‑shipping threshold only after discount will still be charged the standard 500‑cent fee.

No other helper or later adjustment to shipping is shown in the provided source; the only place shipping cost is computed is this function. Therefore the evidence directly refutes the intended behavior.

## Next check  
- Verify whether any downstream logic (e.g., after `quote` creation) overrides `shipping_cents` based on post‑discount totals. If such logic exists elsewhere, it could mitigate the issue, but it is not present in the retrieved excerpts.

---

# Finding 3, batch 1/1

Claim: | **Medium** | Cancel can be executed repeatedly, potentially inflating stock (restocks without status check). | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |

## Assessment
UNRESOLVED

No model call was made: the complete evidence exceeds the configured local token budget. Source was not split or truncated.

Estimated budget: 10398 tokens; limit: 8000.


---

# Finding 4, batch 1/1

Claim: | **Medium** | Refund logic lacks a non‑negative amount guard; a negative refund could increase order balance. | Refund handling section – no explicit `amount_cents > 0` guard (exact lines not quoted) |

## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `OrderService.refund` validates the amount:  

  ```python
  0661: integer(amount_cents, "amount_cents", 1, 100_000_000)
  0662: request_id = nonempty(request_id, "request_id", 80)
  ```  

- The `integer` helper (lines 0090‑0094) raises an error unless the value is between the given bounds, inclusive of the lower bound `minimum`:

  ```python
  0090: def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
  0091:     if isinstance(value, bool) or not isinstance(value, int):
  0092:         raise ServiceError(f"{name} must be an integer")
  0093:     if not minimum <= value <= maximum:
  0094:         raise ServiceError(f"{name} must be between {minimum} and {maximum}")
  ```

  Here `minimum` is `1`, so any `amount_cents` ≤ 0 triggers a `ServiceError`.

## Explanation and limits  
The claim states that the refund routine lacks a guard against negative amounts, implying a negative refund could increase the order’s balance. The source shows an explicit validation step (`integer(amount_cents, ..., 1, ...)`) that enforces `amount_cents` to be **at least 1**. Consequently, a negative (or zero) refund amount cannot be passed to the subsequent logic, and the scenario described in the claim cannot occur within this implementation.

No other code paths invoke `OrderService.refund` without this validation, and the helper `integer` is the sole gatekeeper for the amount’s sign. Therefore the evidence directly refutes the claim.

## Next check  
The existing guard satisfies the non‑negative amount requirement; no further missing validation is evident in the provided snippets. However, ensure that any future modifications to `OrderService.refund` retain this validation, and verify that callers do not bypass it via alternative interfaces.

---

# Finding 5, batch 1/1

Claim: | **Medium** | `export_orders` propagates raw `FileExistsError` instead of a domain `ServiceError`. | `def export_orders(...):` – lines 778‑800 (opens file with mode `"x"` and does not catch `FileExistsError`) |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
```python
0784: def export_orders(self, path: Path, start: str, end: str) -> dict:
0785:     lower, upper = self.date_bounds(start, end)
0786:     if not path.parent.is_dir():
0787:         raise ServiceError("Export directory does not exist")
0788:     rows = self.db.all(
0789:         "SELECT order_id, customer_id, status, subtotal_cents, discount_cents, "
0790:         "shipping_cents, tax_cents, total_cents, created_at FROM orders "
0791:         "WHERE created_at >= ? AND created_at < ? ORDER BY created_at, order_id",
0792:         (lower, upper),
0793:     )
0794:     columns = ["order_id", "customer_id", "status", "subtotal_cents", "discount_cents",
0795:                "shipping_cents", "tax_cents", "total_cents", "created_at"]
0796:     with path.open("x", encoding="utf-8", newline="") as stream:   # ← opens with mode "x"
0797:         writer = csv.DictWriter(stream, fieldnames=columns)
0798:         writer.writeheader()
0799:         writer.writerows(dict(row) for row in rows)
0800:     return {"path": str(path), "row_count": len(rows)}
```

## Explanation and limits  
`export_orders` opens the target file using `path.open("x", …)`. The `"x"` mode raises a built‑in `FileExistsError` if the file already exists. The function does **not** catch this exception nor translate it into the domain‑specific `ServiceError`. The only pre‑check is for the existence of the containing directory (lines 0786‑0787). Consequently, when a caller attempts to export to an existing file, the raw `FileExistsError` propagates out of the service layer, contrary to the intended error‑handling pattern that wraps operational problems in `ServiceError`. This matches the claim.

No other code in the provided context catches `FileExistsError` for this operation, and there is no helper that would perform such translation implicitly. Therefore the evidence directly supports the finding.

## Next check  
- Verify whether callers of `export_orders` (e.g., the CLI dispatch at line 1022) expect a `ServiceError` and handle it uniformly.  
- Consider adding a `try/except FileExistsError` block that raises `ServiceError("Export file already exists")` to align with domain error handling.  

---

# Finding 6, batch 1/1

Claim: | **Medium** | `import_orders` stops processing after the line‑limit is reached, discarding later rejections. | `def import_orders(...):` – lines 857‑870 (`break` when `number > 1000`) |

## Assessment
UNRESOLVED

No model call was made: the complete evidence exceeds the configured local token budget. Source was not split or truncated.

Estimated budget: 10249 tokens; limit: 8000.


---

# Finding 7, batch 1/1

Claim: | **Low** | `seed_demo` may raise an exception when the `metadata` table is empty. | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` – lines 836‑839 |

## Assessment
UNRESOLVED

No model call was made: the complete evidence exceeds the configured local token budget. Source was not split or truncated.

Estimated budget: 11247 tokens; limit: 8000.


---

# Finding 8, batch 1/1

Claim: | **Info** | Quantity parsing and bounds checking appear correct. | `CheckoutRequest.from_dict` – lines 0189‑0194 |

## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- **CartLine quantity validation**  
  ```python
  0174: sku = nonempty(value.get("sku"), "sku", 40).upper()
  0175: quantity = integer(value.get("quantity"), "quantity", 1, MAX_LINE_QUANTITY)
  ```  
- **CheckoutRequest cart‑line count validation**  
  ```python
  0192: if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= MAX_CART_LINES:
  0193:     raise ServiceError(f"Cart must contain 1 to {MAX_CART_LINES} lines")
  ```

## Explanation and limits  
The `CartLine.from_dict` method parses the `quantity` field and passes it to the `integer` helper, which enforces that the value is an integer between **1** and **MAX_LINE_QUANTITY** (100). This satisfies the requirement for correct quantity parsing and bounds checking.

`CheckoutRequest.from_dict` further validates the overall cart by ensuring the `items` list exists, is a list, and its length is between **1** and **MAX_CART_LINES** (40). This is an additional bounds check on the number of cart lines, which is also correctly implemented.

No source code contradicts these checks, and there is no evidence of missing or incorrect validation elsewhere in the provided snippets. Therefore the claim that “Quantity parsing and bounds checking appear correct” is supported by the existing implementation.

## Next check  
- Verify that the `integer` helper correctly raises `ServiceError` for out‑of‑range or non‑integer inputs (already shown).  
- Ensure that duplicate SKU detection (`line 0195‑0196`) and shipping validation (`line 0198‑0199`) also behave as intended, though they are outside the scope of this specific claim.

---

# Finding 9, batch 1/1

Claim: | **Info** | Duplicate‑SKU validation rejects duplicates instead of combining them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |

## Assessment
UNRESOLVED

Provider call failed: Groq HTTP 429: Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m5xyqyxbep5bwm577d07gxyh` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 196428, Requested 4054. Please try again in 3m28.224s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing | Limit details: {"retry-after": "209", "x-ratelimit-limit-requests": "1000", "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-requests": "995", "x-ratelimit-remaining-tokens": "8000", "x-ratelimit-reset-requests": "7m12s", "x-ratelimit-reset-tokens": "1ms"}
