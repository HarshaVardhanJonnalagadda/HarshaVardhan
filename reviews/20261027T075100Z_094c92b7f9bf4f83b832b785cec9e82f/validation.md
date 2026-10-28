# Validation: order-total request

Method: static comparison with the original supplied source and business rules.
No service reproduction or fix verification was performed in this assessment.

## Supported main finding
PricingService.quote(), line 523, sums unit_price_cents rather than
quantity-adjusted line totals. OrderService.checkout() uses this quote,
and _insert_order() stores its amounts.

This explains a $10 subtotal and $11 total for one line containing
three $10 mugs. Intended amounts: $30 subtotal, $3 tax, $33 total.

## Supported additional findings
- Standard free shipping checks the pre-discount subtotal.
- Repeated cancellation can restore stock more than once.

## Rejected or unsupported findings
- Negative refunds: rejected by the existing positive-integer validation.
- Empty metadata query causing seeding failure: unsupported.
- Export exception type: not an established business-rule violation.
- Import continuation beyond the limit: not required by supplied rules.
- checkout.py reference: incorrect filename; source is order_service.py.

## Review-tool limitation
Consolidation incorrectly treats a later section's lack of pricing code
as evidence against a finding established in an earlier section.

## Next checks
Fix the general consolidation instructions and add a regression test.
Then regenerate consolidation and compare it with this assessment.
Keep the supplied service unchanged.
