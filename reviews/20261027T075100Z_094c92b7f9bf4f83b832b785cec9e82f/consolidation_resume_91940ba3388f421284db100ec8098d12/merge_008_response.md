# Review  

This report **consolidates all section notes** you have supplied (the previous draft and the newest findings). It extracts the quoted evidence, line references, and reasoning that may explain why an order for three MUGs ($10 each, pickup, no coupon) shows a merchandise subtotal of **$10** and a total of **$11** instead of the expected $30 + tax.  

> **Important:** The original source code has **not** been inspected in this step. All conclusions are based solely on the quoted excerpts and comments you provided. **Human validation against the complete implementation and the business rules is required** before any defect is confirmed or a change is made.  

---  

## Answer to the request  

The most plausible explanation, given the available evidence, is that **the subtotal calculation is ignoring the line quantity**, resulting in a subtotal equal to a single unit price (1 000 cents) rather than three times that amount (3 000 cents).  

* If the quoted line from `PricingService.quote` is part of the checkout flow, the code:

```python
subtotal = sum(line.unit_price_cents for line in lines)   # line 0523
```  

produces **1 000 cents**. Tax (10 % rounded half‑up) on that subtotal is **100 cents**, giving a total of **1 100 cents ($11)** – exactly the numbers you observed.  

However, a later note states that **no arithmetic code that computes the cart’s subtotal, tax, shipping, discount, or total was included in the excerpts**, so the presence of the buggy line cannot be confirmed from the supplied fragments. The discrepancy therefore remains **unverified** until the full `PricingService.quote` (or equivalent) implementation is examined.

---  

## Important findings  

| Severity | Finding | Source quotation & line reference |
|----------|---------|-----------------------------------|
| **High** | Subtotal may ignore quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |
| **Medium** | Cancel can be executed repeatedly, potentially inflating stock (restocks without status check). | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |
| **Medium** | Free‑shipping rule checks pre‑discount subtotal, not post‑discount as required. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |
| **Medium** | Refund logic lacks a non‑negative amount guard; a negative refund could increase order balance. | Refund handling section – no explicit `amount_cents > 0` guard (exact lines not quoted) |
| **Medium** | `export_orders` propagates raw `FileExistsError` instead of a domain `ServiceError`. | `def export_orders(...):` – lines 778‑800 (opens file with mode `"x"` and does not catch `FileExistsError`) |
| **Medium** | `import_orders` stops processing after the line‑limit is reached, discarding later rejections. | `def import_orders(...):` – lines 857‑870 (`break` when `number > 1000`) |
| **Low** | `seed_demo` may raise an exception when the `metadata` table is empty. | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` – lines 836‑839 |
| **Info** | Quantity parsing and bounds checking appear correct. | `CheckoutRequest.from_dict` – lines 0189‑0194 |
| **Info** | Duplicate‑SKU validation rejects duplicates instead of combining them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |
| **Info** | Shipping‑method validation maps `"pickup"` to a free method. | `CheckoutRequest.from_dict` – lines 0197‑0199 |
| **Info** | Catalog price updates are persisted correctly. | `CatalogService.update_price` – lines 0428‑0436 |

---  

## Uncertainty and conflicting evidence  

| Area | Evidence supporting a defect | Evidence contradicting it | Remaining unknowns |
|------|------------------------------|---------------------------|--------------------|
| **Subtotal calculation** | `PricingService.quote` line 0523 clearly sums only `unit_price_cents`. | New note: *“The code you supplied (argument parsing, `write_invoice`, dispatcher) does not contain any of the arithmetic that computes a cart’s merchandise subtotal… Consequently, there is no evidence here of a bug that would cause a three‑item order… to be recorded as $10 subtotal.”* | Whether the quoted line is part of the actual checkout flow or an isolated helper that is later overridden. The surrounding code (e.g., a later correction) is missing, so the defect remains **unconfirmed** until the full checkout/quote implementation is reviewed. |
| **Tax calculation** | Business rule: 10 % of merchandise after discount, rounded half‑up. | No tax‑related code was provided, so compliance cannot be verified. | Exact rounding implementation and its interaction with a possibly wrong subtotal. |
| **Free‑shipping rule** | Code checks raw `subtotal` before discount (lines 0514‑0515). | Business rule explicitly requires *post‑discount* merchandise ≥ 10 000 cents for free shipping. | Impact on orders with coupons; not directly related to the current case. |
| **Cancel idempotency** | Cancel loop always restocks (lines 0622‑0636). | No evidence of a higher‑level guard preventing double restock. | Whether another component already prevents duplicate restocking. |
| **Export/Import behavior** | Export raises `FileExistsError`; Import stops at limit. | Business rules only require “CSV export must not overwrite an existing file” and “Import line limit reached” – they do not prescribe exception type or continuation behavior. | Whether the current exception handling violates API contracts; likely a usability issue. |

---  

## Next checks  

1. **Inspect the full checkout/quote flow** (`OrderService.checkout`, `OrderService.quote`, or equivalent). Confirm whether the `subtotal` from `PricingService.quote` is stored unchanged or later corrected.  
2. **If the bug exists**, change the subtotal computation to include quantity:  

   ```python
   subtotal = sum(line.unit_price_cents * line.quantity for line in lines)
   ```  

3. **Verify tax calculation** implements 10 % of the (post‑discount) merchandise, rounded half‑up to the nearest cent.  
4. **Adjust free‑shipping logic** to use the *post‑discount* subtotal as required by the business rules.  
5. **Make `cancel` idempotent**: skip the restock loop if `order.status == "cancelled"`.  
6. **Add a non‑negative guard** to refund processing (`if amount_cents <= 0: raise ServiceError`).  
7. **Wrap `export_orders` file creation** in a `try/except FileExistsError` and raise a domain `ServiceError` with a clear message.  
8. **Re‑evaluate `import_orders`** – either document that processing stops at the limit or modify the loop to continue scanning for additional rejections.  
9. **Confirm `Database.one` behavior** on empty result sets so that `seed_demo` does not raise unexpected exceptions on a fresh DB.  
10. **Run a targeted unit test**: three MUGs ($10 each), pickup, no coupon. Assert `subtotal_cents == 3000`, `tax_cents == 300`, `total_cents == 3300`. Compare intermediate values (`priced_lines`, `subtotal_cents`, etc.) against expectations.  

---  

**Note:** This report aggregates the supplied section notes and highlights likely problem areas. **Human validation against the complete source code and the business rules is essential** before any defect is confirmed or a change is made.