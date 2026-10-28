## Findings
**None in this section.**  
The lines you supplied (1005‑1060) only contain the command‑dispatch logic, the `main()` entry point, and the program‑termination guard. They do not include any of the order‑creation, pricing, tax, or shipping calculations that would affect the subtotal or total shown to the user. Consequently, no defect can be demonstrated from the provided code.

## Uncertainty
- The behaviour you observed (subtotal $10 for three $10 mugs, total $11 with pickup) must be produced somewhere else in the codebase – most likely in the functions that:
  - Parse the cart line(s) and combine quantities (`orders.create`, `cart.add_line`, etc.).
  - Look up product prices (`catalog.get_price` or similar).
  - Compute the merchandise subtotal, discounts, tax, and shipping (`orders.calculate_total`, `order.compute_totals`, etc.).
- Without seeing those implementations we cannot confirm whether the problem is due to:
  - Ignoring the quantity field.
  - Using the wrong price (e.g., a discounted or promotional price).
  - Mis‑applying the shipping‑cost‑free‑for‑pickup rule.
  - Rounding or tax‑calculation errors.

## Next checks
1. **Order creation path** – locate the function that builds an `Order` object from the CLI arguments (likely called from `dispatch` when the command is `"checkout"` or similar). Verify that it:
   - Reads the `quantity` argument correctly.
   - Multiplies `unit_price * quantity` for each line.
   - Handles repeated SKUs by consolidating them.

2. **Price lookup** – inspect `catalog.get_price` (or whatever function supplies the unit price). Ensure it returns the current catalog price in cents and that the price for SKU “MUG” is indeed `1000` (i.e., $10).

3. **Subtotal / total calculation** – examine the routine that:
   - Sums line totals to produce the merchandise subtotal.
   - Applies coupons (none in this case, but confirm the path is bypassed correctly).
   - Calculates tax (10 % of the post‑discount subtotal, rounded half‑up).
   - Adds shipping cost (should be `0` for pickup).

4. **CLI argument parsing** – review the `argparse` configuration for the checkout command to confirm that the quantity argument is defined as an integer and that the default is not silently set to `1`.

5. **Tests / examples** – if a test suite exists, run the scenario “3 MUGs, pickup, no coupon” and compare the computed JSON output with the expected values (`subtotal: 3000`, `tax: 300`, `shipping: 0`, `total: 3300`). This will pinpoint which step diverges.

By focusing on the modules that actually perform the monetary calculations, you’ll be able to locate the root cause of the $10 subtotal instead of the expected $30. The dispatch and `main()` code shown here appear to be functioning as intended.