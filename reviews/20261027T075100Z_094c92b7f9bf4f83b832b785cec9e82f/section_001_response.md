## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Info** | No subtotal‑related logic in this section | Lines 1‑188 (the whole excerpt) – the file only defines utility helpers, data classes (`Customer`, `Product`, `CartLine`, `CheckoutRequest`) and validation functions. No function that *calculates* merchandise subtotal, tax, shipping or total appears here. |
| **Info** | Potential source of later bugs – `CheckoutRequest.from_dict` not shown | Lines 0187‑0188 start the `from_dict` class‑method but the implementation is cut off. If that method mishandles the `lines` field (e.g., keeps only the first line, drops the `quantity`, or stores a single `CartLine` instead of a collection), the later order‑creation code could compute a wrong subtotal. |
| **Info** | Quantity validation is correct but may be silently ignored later | `CartLine.from_dict` (lines 0171‑0176) validates `quantity` with `integer(..., 1, MAX_LINE_QUANTITY)`. The validation itself is fine; however, nothing in this excerpt shows that the validated `quantity` is actually used when the order total is computed. |

**What the supplied code demonstrably does**  

* Parses and validates JSON request files (`read_json`).  
* Provides helpers for timestamps, money conversion, percentage calculation, and JSON canonicalisation.  
* Defines immutable data classes for customers, products, cart lines, and checkout requests.  
* Validates each `CartLine`’s `sku` (non‑empty, upper‑cased) and `quantity` (integer 1‑100).  

**How that behavior could cause the reported problem**  

If the missing implementation of `CheckoutRequest.from_dict` (or a later function that consumes the `lines` tuple) drops or collapses the three `CartLine` entries into a single line, the order‑creation logic would see only **one** MUG instead of three. That would produce a merchandise subtotal of `$10` (one unit at $10) and, after adding the 10 % tax (rounded up), a total of `$11`. This matches the user’s observed numbers.

**Assumptions / Missing cross‑function evidence**  

* The actual subtotal, tax, and total calculations are located in a later section of the source file (not provided).  
* The bug, if any, resides in those later functions or in the incomplete `CheckoutRequest.from_dict`.  
* No evidence in the current excerpt shows any arithmetic error, rounding mistake, or shipping‑cost mis‑application.

## Uncertainty  

* **Exact cause of the $10 subtotal** – without seeing the order‑creation routine we cannot confirm whether the quantity is being ignored, whether the product price is read incorrectly, or whether a different part of the code (e.g., coupon handling) is mistakenly applied.  
* **Whether the request JSON is being parsed correctly** – the shape of the incoming JSON (`lines` array) and how `CheckoutRequest.from_dict` transforms it are unknown.  
* **Potential side‑effects from other modules** – inventory reservation, coupon lookup, or shipping‑method handling could also influence the final total, but those sections are not present.

## Next checks  

1. **Locate the implementation of `CheckoutRequest.from_dict`** (the rest of the method after line 0188). Verify that it:  
   * Reads the `"lines"` array from the request JSON.  
   * Calls `CartLine.from_dict` for **each** element and stores the results in a tuple/list preserving all entries.  
   * Does **not** inadvertently keep only the first line or overwrite later lines.  

2. **Find the function(s) that compute the order monetary values** – likely named something like `calculate_subtotal`, `apply_coupon`, `compute_tax`, `compute_total`, or similar. Examine:  
   * How the merchandise subtotal is summed (`price_cents * quantity`).  
   * Whether the loop iterates over **all** `CartLine`s.  
   * Whether the product price is fetched correctly from the `Product` table (no hard‑coded fallback).  

3. **Check the tax calculation** – ensure it uses `TAX_BASIS_POINTS = 1000` (10 %) and rounds half‑up as required.  

4. **Inspect shipping‑cost logic** – confirm that the `"pickup"` key maps to a zero‑cost entry in `SHIPPING_CENTS`.  

5. **Run a mental test** (or add unit tests) with a request containing three identical lines for the same SKU, no coupon, and `"shipping": "pickup"` to see whether the subtotal becomes `3 * price_cents`.  

6. **Review any deduplication or line‑combining code** – the business rules say “Combine repeated SKUs into one line.” Verify that such combination multiplies the quantity correctly rather than discarding extra units.  

By examining those sections we can determine whether the observed $10 subtotal is due to a quantity‑handling bug, a price‑lookup error, or another mis‑implementation. Once the relevant code is inspected, a concrete defect (if any) can be identified and fixed.