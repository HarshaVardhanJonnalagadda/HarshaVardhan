# Human validation: general-review request

Status: static assessment recorded; runtime checks not performed.

## Method

Compared the generated section reviews with the supplied source and
business rules. No runtime reproduction or fix verification was
performed. The supplied service remains unchanged.
Evidence folder:
reviews/20261028T040809Z_7d35c55538ff404cb032cf64863ef21b

Reviewed output: section_reviews.md.
All nine section reviews completed, but completion does not establish
correctness of every model finding.

This run reused six saved section responses from:
reviews/20261028T040039Z_2e3808b351404476869eae1e3f2f4564

## Supported findings

1. Incorrect subtotal — PricingService.quote, line 523, sums unit
   prices instead of quantity-adjusted line totals. Three $10 mugs
   therefore produce a $10 subtotal and $11 total instead of $30
   subtotal and $33 total.

2. Incorrect free-shipping eligibility — PricingService.shipping_cost,
   line 514, checks subtotal >= FREE_SHIPPING_CENTS without using
   discount. The caller at line 525 passes the pre-discount subtotal.
   Standard shipping can incorrectly remain free when discounted
   merchandise falls below 10,000 cents.

3. Repeated cancellation inflates stock — OrderService.cancel,
   lines 626–635, rejects shipped orders but does not stop an already
   cancelled order from restoring stock again.

4. Cancelled orders appear in sales — ReportingService.sales,
   lines 712–718, aggregates orders without excluding cancelled status.
   The date-only filter is at line 717. Cancellation changes status
   without clearing monetary amounts, leaving cancelled orders in
   the count and gross sales.

5. Low-severity duplicate-SKU rule deviation — CheckoutRequest.from_dict,
   lines 195–196, rejects repeated SKUs, while the business rules say
   repeated SKUs are combined into one line. This fails safely, but it
   does not follow the stated rule.

## Rejected or unsupported claims

- Database.transaction, lines 355–363, uses BEGIN IMMEDIATE at line 356
  and rolls back on exceptions. Checkout uses this transaction at
  line 576. _reserve_line, lines 613–619, conditionally updates stock
  only when sufficient stock remains.
- low_stock includes active-product and stock-threshold filters.
- Export uses exclusive creation mode "x", preventing overwrites.
- Refund amounts and restock quantities must be positive.
- Price updates reject negative prices.
- Export and top-products command handlers exist.
- Database.one returns None when no row matches; the missing metadata
  row does not itself cause seeding failure.
- Inventory reconciliation already uses COALESCE.
- CheckoutRequest.from_dict rejects empty carts and invalid shipping
  methods.
- OrderService.view supplies refunded_cents.
- coupon_discount rejects unavailable coupons.
- initialize inserts the schema metadata row.
- main catches OSError and ServiceError.
- The claim that older SQLite ignores a bound LIMIT is unsupported.
- Timestamp precision alone does not establish an inventory race.
- The set-active parser restricts --value to "yes" or "no".
  Its case-sensitive comparison does not establish a defect.

## Assumptions and remaining uncertainty


Truncated identifier collisions remain a theoretical risk, not a
demonstrated defect.

This assessment is not exhaustive and does not establish that every
defect was found.

## Missed issues

The model missed the duplicate-SKU rule deviation (finding 5).
No other missed issue is confirmed in these notes.

## Review-tool limitations



Section boundaries split some functions and SQL statements. Several
findings inferred missing behavior from incomplete context. Some
citations have inaccurate line numbers.

## Next checks

Not yet performed:
- Reproduce the five supported findings, including duplicate-SKU
  handling, using disposable databases.
- Add verification regression cases for the autocommit, low_stock,
  negative-restock and missing-handler claims.
- Improve context selection to preserve complete functions and retrieve
  relevant helpers and callers.

Verification should refute claims when direct counter-evidence is
available and leave them unresolved when context is insufficient.   