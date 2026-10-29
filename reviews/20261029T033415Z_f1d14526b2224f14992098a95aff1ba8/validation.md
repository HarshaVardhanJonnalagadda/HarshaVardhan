# Validation: upgraded general review

Status: static assessment recorded; model verification remains partial.

## Evidence and method

Review run:
20261029T033415Z_f1d14526b2224f14992098a95aff1ba8

Reviewed output: section_reviews.md.

Verification plan:
verification_5b30cd179ad3456bb28973590cb851b2/plan.json

Compared generated findings and verification assessments with the
original order_service.py and supplied business rules.

All nine section reviews completed. Eight responses were reused from
the previous attempt; the remaining section used a new API call.

No new runtime reproduction or fix verification was performed for this
assessment. The supplied service remains unchanged.

Follow-up verification plan:
verification_c276df718fd74883b19b9d9949817e9e/plan.json

## Supported defects

1. PricingService.quote, line 523, sums unit prices instead of
   quantity-adjusted line totals. Three $10 mugs produce a $10 subtotal
   and $11 total instead of a $30 subtotal and $33 total.

2. PricingService.shipping_cost, line 514, checks the pre-discount
   subtotal. It can incorrectly grant free standard shipping when
   merchandise after discount falls below 10,000 cents.

3. OrderService.cancel, lines 622–637, does not stop an already-cancelled
   order from restoring stock again.

4. ReportingService.sales, lines 712–718, includes cancelled orders
   in order counts and gross sales.

## Rejected or unsupported claims

- Missing request files do not establish inconsistent stock:
  main catches OSError, and request reading precedes checkout.
- CatalogService.restock rejects non-positive quantities.
- Quote.coupon is a string or None; storing it is not an object-type bug.
- Same-day report ranges include the entire day, not an empty range.
- Seeding and its completion marker share one transaction.
- Half-up rounding is required for tax, but no supplied rule establishes
  that requirement for average order amounts.
- Import-wide atomicity is not an established requirement.
- Repeating an identical checkout request ID does not reserve stock again.
- A hypothetical future change to parse_day does not demonstrate a
  current date-construction defect.

## Missed issue

CheckoutRequest.from_dict, lines 195–196, rejects repeated SKUs.
The business rules require combining them into one line.
The model missed this low-severity rule deviation.

## Model-verification results: first two rounds

The initial plan extracted 13 candidate table rows, not 13 confirmed bugs.
Seven calls completed in the first round; six tasks were blocked.

After improving explicit function-reference matching, five additional
calls completed. Across both rounds, 12 candidate findings received
model assessments. Original finding 11 remains blocked by the token
budget. Completion does not establish correctness.

Human assessment of the results:

- Finding 1: incorrectly supported. main catches OSError, and request
  reading precedes checkout. The alleged partial reservation is unsupported.
- Finding 2: correctly supports the quantity-ignoring subtotal defect.
  The model added a comment to a purported exact source quotation.
- Finding 3: supports the free-shipping defect but repeats an incorrect
  consequence. A non-negative discount cannot raise merchandise from
  below the threshold to above it.
- Finding 4: confirms the unused discount argument. This supports
  finding 3 rather than establishing another independent defect.
- Finding 5: correctly supports repeated cancellation restoring stock.
- Finding 6: correctly refutes the coupon-object storage claim.
- Finding 7: correctly supports the cancelled-order sales defect.
- Finding 8: correctly identifies average half-up rounding as an
  unspecified requirement.
- Finding 9: demonstrates no current date-construction defect.
- Finding 10: explains that a same-day range includes the entire day,
  contradicting the original empty-range claim.
- Finding 11: no model assessment; remains blocked.
- Finding 12: incorrectly supported. Demo data and the seeded marker
  share one transaction, with the marker inserted after the data.
- Finding 13: correctly refutes missing restock-sign validation, but
  adds a comment to a purported exact source quotation.

Verification can repeat false positives. A locally true observation
does not establish the entire claimed application-level effect.

Both generated verification reports remain unchanged.

## Latest targeted verification

Evidence:
verification_7e30502dca90430aac2cdf7295f4e702/

Two additional calls reassessed original findings 1 and 12 using
two caller levels and revised causal-assessment instructions.
These were reassessments, not additional distinct findings.

Finding 1 was correctly refuted in this round. main catches OSError,
and request reading precedes checkout's stock changes. However,
the response inserted an omission comment into a source quotation
and overstated this as occurring before any database work.

Finding 12 remained incorrectly supported. The seeded marker is
inserted after the demo data within the same transaction, and
Database.transaction rolls back on exceptions. The proposed
partial-seeding failure is contradicted by this evidence.

Original finding 11 remains blocked. Human validation is still
necessary even when relevant counter-evidence is retrieved.

All generated verification reports remain unchanged.
No new runtime reproduction or fix verification was performed.

## Review-tool limitations

Some findings infer missing behavior from unseen helpers or callers.
Some speculative claims are incorrectly labelled source-supported.
Some source quotations and line references are inaccurate.

The scope map gives structural locations, not complete dependency code.
Retrieval approximates call relationships by names.
The verification plan extracts severity-table rows only; prose-only
findings and uncertainty sections are excluded.

These results do not establish that every defect was found or that
the accuracy problem is resolved.

## Next checks

Completed:
- Improved explicit function-reference matching.
- Added configurable caller traversal.
- Confirmed caller depths 0, 1 and 2 with a local check.
- Passed the existing 46-test suite before the latest planning
  and verification-prompt edits.
- Reassessed findings 1 and 12 with revised evidence and instructions.

Remaining:
- Save permanent caller-depth regression tests.
- Add dedicated finding-extraction regression tests.
- Run the full test suite and save its output.
- Update the README with current test results and accuracy limitations.
- Review the Git changes before committing and pushing.

Original finding 11 remains blocked by the configured token budget.
Keep generated reports and supplied assignment files unchanged.