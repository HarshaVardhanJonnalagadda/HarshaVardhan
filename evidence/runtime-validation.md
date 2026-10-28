# Manual runtime validation

These checks manually executed the supplied service on fresh local
databases. The review agent did not execute reviewed code.
No model API calls were made. No source fixes were applied.

## Question 1: three-mug total

Evidence: quantity-check.iXKjNS/checkout-output.json

Observed:
- Quantity: 3
- Unit price: 1000 cents
- Item line total: 3000 cents
- Order subtotal: 1000 cents
- Tax: 100 cents
- Order total: 1100 cents

Required: subtotal 3000, tax 300, total 3300 cents.
The observed discrepancy reproduces the reported problem and is
consistent with the subtotal expression identified by static review.

## Question 2: cancelled-order sales

Evidence:
- cancel-check-xdmyo_n2/cancel.json
- cancel-check-xdmyo_n2/report.json

Observed:
- Order status: cancelled
- Report order count: 1
- Report gross sales: 1650 cents

Required for this fresh database after cancellation:
order count 0 and gross sales 0.
This reproduces the reported problem.

## Limits

These checks do not verify a fix or establish that every defect was found.
Free-shipping eligibility, repeated cancellation and duplicate-SKU
handling remain supported by static assessment, without runtime
reproduction in this record.

Earlier validation notes describe the static assessment performed at
that time. This document records the later manual runtime checks.
