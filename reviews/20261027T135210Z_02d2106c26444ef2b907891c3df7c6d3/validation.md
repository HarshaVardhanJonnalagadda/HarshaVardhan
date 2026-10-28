# Human validation

Status: pending

## Supported findings
Check each finding against the source and business rules.

## Assumptions or unsupported claims
Record missing evidence and uncertain conclusions.

## Missed issues
Record relevant issues the model did not identify.

## Next checks
Describe additional checks and whether they were performed.


## Manual validation: cancelled-order request

Method: static comparison of the saved source snapshot, business rules,
and section_006_response.md. No runtime reproduction or fix verification.

Supported main finding:
ReportingService.sales, lines 713–718, aggregates orders by creation date
without excluding cancelled status. OrderService.cancel, lines 634–635,
sets status to 'cancelled' without changing the stored monetary amounts.
Together, these explain why the cancelled order remains in both the
sales count and gross sales.

Supported additional finding:
OrderService.cancel rejects shipped orders but does not stop repeated
cancellation. Lines 628–633 can therefore restore stock more than once.

Limitations:
The section review remains incomplete: 6 of 9 sections were saved before
a provider quota failure. These notes validate specific findings, not
the entire service. The supplied service was not modified.

Next checks:
On a disposable database, reproduce create → cancel → sales report.
Check repeated cancellation against stock before and after each call.