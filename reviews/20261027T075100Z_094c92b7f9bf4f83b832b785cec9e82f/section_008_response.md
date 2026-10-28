## Findings
**None in this section** – The code you supplied (argument parsing, `write_invoice`, and the top‑level `dispatch` dispatcher) does not contain any of the arithmetic that computes a cart’s merchandise subtotal, tax, shipping, discount, or total. Consequently, there is no evidence here of a bug that would cause a three‑item order of $10‑each to be recorded as a $10 subtotal and $11 total.

## Uncertainty
- The incorrect subtotal you observed must be produced by logic that is **not** included in the excerpt you posted.  
- The relevant calculations are likely located in one (or more) of the following components, which are referenced but not shown:
  * `PricingService.quote(...)`
  * `OrderService.checkout(...)`
  * `OrderService.view(...)` (used by `write_invoice`)
  * Data‑model helpers such as `CheckoutRequest.from_dict`, `format_money`, or any utility that aggregates line items.

Without seeing those functions we cannot confirm whether the problem stems from:
1. **Quantity handling** – e.g., ignoring the `quantity` field or defaulting it to 1.
2. **Unit‑price lookup** – e.g., fetching the wrong price from the catalog.
3. **Subtotal aggregation** – e.g., summing only the first line item.
4. **Rounding or tax‑shipping logic** – though the symptom (subtotal $10 instead of $30) points more directly to a quantity‑related issue.

## Next checks
1. **`PricingService.quote` implementation** – Verify that it multiplies `unit_price_cents` by `quantity` for each cart line and that it correctly aggregates the results into `subtotal_cents`.
2. **`OrderService.checkout`** – Ensure it stores the quoted values unchanged (order line snapshots) and that it does not inadvertently overwrite the subtotal with a single‑item value.
3. **`CheckoutRequest.from_dict`** – Confirm that the JSON request schema includes a `quantity` field and that the parser correctly populates it.
4. **Data model for order items** – Look at how `order["items"]` is built and persisted; check that `line_total_cents` = `unit_price_cents * quantity`.
5. **Any helper that normalises or validates cart lines** – Search for code that “combines repeated SKUs into one line” and make sure it sums quantities rather than discarding them.
6. **Unit tests (if any)** – Run tests that create a cart with multiple identical SKUs and verify the resulting `subtotal_cents`.

Inspecting those modules will reveal whether the subtotal is being truncated to a single unit price, which would explain the $10 subtotal you observed. Once the relevant code is examined, any mis‑calculation can be pinpointed and corrected.