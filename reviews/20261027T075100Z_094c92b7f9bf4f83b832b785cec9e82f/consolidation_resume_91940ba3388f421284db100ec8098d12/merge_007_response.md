# Review  

This report **consolidates all section notes** you supplied (the previous draft and the additional findings) and highlights evidence that may explain why an order for three MUGs ($10 each, pickup, no coupon) shows a merchandise subtotal of **$10** and a total of **$11** instead of the expected $30 + tax.  

> **Important:** The original source code has **not** been inspected in this step. All conclusions are based solely on the quoted excerpts and comments you provided. **Human validation against the complete implementation and the business rules is required** before any defect is confirmed or a change is made.  

---  

## Answer to the request  

The most plausible explanation, given the available evidence, is that **the pricing routine computes the merchandise subtotal from the unit price only, ignoring the line quantity**.  

* In `PricingService.quote` the subtotal is calculated as  

```python
subtotal = sum(line.unit_price_cents for line in lines)   # line 0523
```  

  This yields **1 000 cents** (the price of a single mug) instead of **3 000 cents**.  

* Tax (10 % rounded half‑up) is then applied to that incorrect subtotal, giving 100 cents tax and a total of 1 100 cents ($11) – exactly the numbers you observed.  

If this code path is the one used when the order is created, the discrepancy is caused by the **“subtotal calculated from unit price instead of line total”** defect.  

---  

## Important findings  

| Severity | Finding | Source quotation & line reference |
|----------|---------|-----------------------------------|
| **High** | Subtotal ignores quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |
| **Medium** | Cancel can be executed repeatedly, inflating stock – `cancel` adds back stock without checking order status. | `checkout.py` – lines 0622‑0636 (stock‑restock loop) |
| **Medium** | Free‑shipping rule checks pre‑discount subtotal, not post‑discount as required. | `PricingService.shipping_cost` – lines 0514‑0515 (`if method == "standard" and subtotal >= FREE_SHIPPING_CENTS:`) |
| **Medium** | Refund logic lacks a non‑negative amount check – a negative refund could increase the order balance. | Refund handling section (no explicit `amount_cents > 0` guard) |
| **Medium** | `export_orders` propagates a raw `FileExistsError` instead of a domain `ServiceError`. | `def export_orders(...):` – lines 778‑800 (opens file with mode `"x"` and does not catch `FileExistsError`) |
| **Low** | `import_orders` stops processing after the line‑limit is reached, discarding later rejections. | `def import_orders(...):` – lines 857‑870 (`break` when `number > 1000`) |
| **Info** | `seed_demo` may raise an exception when the `metadata` table is empty. | `if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):` – lines 836‑839 |
| **Info** | Quantity parsing and bounds checking are present and appear correct. | `CheckoutRequest.from_dict` – lines 0189‑0194 |
| **Info** | Duplicate‑SKU validation rejects duplicates instead of combining them. | `CheckoutRequest.from_dict` – lines 0195‑0196 |
| **Info** | Shipping‑method validation maps `"pickup"` to a free method. | `CheckoutRequest.from_dict` – lines 0197‑0199 |
| **Info** | Catalog price updates are persisted correctly. | `CatalogService.update_price` – lines 0428‑0436 |

---  

## Uncertainty and conflicting evidence  

| Area | Evidence supporting a defect | Evidence contradicting it | Remaining unknowns |
|------|------------------------------|---------------------------|--------------------|
| **Subtotal calculation** | `PricingService.quote` line 0523 clearly sums only `unit_price_cents`. | A later note states: *“The code you provided deals with refunds, audit‑history retrieval, and reporting… None of the examined statements compute a cart’s merchandise subtotal… Therefore, based on the supplied lines there is no demonstrable defect that could cause an order’s subtotal to be recorded as $10 instead of $30.”* | Whether the quoted snippet is part of the actual checkout flow or an isolated helper that is later overridden. The surrounding code (e.g., a later adjustment) is missing, so the defect remains **unconfirmed** until the full checkout implementation is reviewed. |
| **Tax calculation** | Business rule requires 10 % tax, round‑half‑up. | No tax‑related code was provided, so compliance cannot be verified. | Exact implementation of tax rounding and its interaction with the (potentially wrong) subtotal. |
| **Free‑shipping rule** | Code checks raw `subtotal` before discount (lines 0514‑0515). | Business rule explicitly says *post‑discount* merchandise ≥ 10 000 cents qualifies for free shipping. | Impact on orders that use coupons; not directly related to the current case. |
| **Cancel idempotency** | Cancel loop always restocks (lines 0622‑0636). | No evidence that another guard elsewhere prevents double restock. | Whether the live system already has a higher‑level check. |
| **Export/Import behavior** | Export raises `FileExistsError`; Import stops at limit. | Business rules only require “CSV export must not overwrite an existing file” and “Import line limit reached” – they do not prescribe exception type or continuation behavior. | Whether the current exception handling violates API contracts; likely a usability issue. |

---  

## Next checks  

1. **Inspect the full checkout/quote flow** (e.g., `OrderService.checkout` or `OrderService.quote`). Confirm whether the `subtotal` from `PricingService.quote` is stored unchanged or later corrected.  
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

> **Note:** This report aggregates the supplied section notes and highlights likely problem areas. **Human validation against the complete source code and the business rules is essential** before any defect is confirmed or a change is made.