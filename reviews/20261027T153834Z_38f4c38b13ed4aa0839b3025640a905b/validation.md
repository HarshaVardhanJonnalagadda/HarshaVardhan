# Human validation: cancelled-order sales request

Status: static assessment recorded; runtime checks not performed.

## Method

Compared the saved source snapshot, supplied business rules and the
sales-report finding in section_006_response.md.

Evidence folder:
reviews/20261027T153834Z_38f4c38b13ed4aa0839b3025640a905b

All nine section reviews completed. These notes assess specific findings,
not every generated claim. No runtime reproduction or fix verification
was performed. The supplied service remains unchanged.

## Supported main finding

ReportingService.sales, lines 712–718, aggregates orders by creation date
without excluding cancelled orders. The date-only filter is at line 717.

OrderService.cancel, lines 634–635, sets status to 'cancelled' without
changing stored monetary amounts.

Together, these explain why a cancelled order remains in both the order
count and gross sales. The business rules require its exclusion.

## Supported additional finding

OrderService.cancel rejects shipped orders at lines 626–627 but does not
stop repeated cancellation. Lines 628–633 can restore stock more than
once, contrary to the business rules.

## Assumptions and uncertainty

The order was successfully cancelled, and its creation date falls within
the requested report range. Static inspection supports this explanation;
runtime reproduction remains unperformed.

## Review-tool limitation

A section lacking cancellation code has insufficient context. Its lack
of that code does not contradict evidence from the cancellation method.

## Missed issues

No additional missed issue is confirmed in this request-specific assessment.

## Next checks

Not yet performed:
- Create an order on a disposable database, cancel it, and run the sales
  report for its creation date.
- Compare the reported count and gross sales with the expected exclusion.
- Repeat cancellation and compare stock before and after each call.

Keep reproduction databases outside Data/.
