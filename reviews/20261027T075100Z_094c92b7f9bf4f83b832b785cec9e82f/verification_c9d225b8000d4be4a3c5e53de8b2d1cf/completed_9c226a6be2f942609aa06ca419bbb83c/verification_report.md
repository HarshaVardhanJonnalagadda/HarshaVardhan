# Source verification assessments

Outcome: verification_incomplete

Model assessments require human validation. Blocked, failed, and unprocessed tasks are unresolved. No runtime reproduction or fix verification was performed.

Unprocessed tasks: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# Finding 1, batch 1/1

Claim: | **High** | Subtotal may ignore quantity – `PricingService.quote` sums only `unit_price_cents`. | `PricingService.quote` – line 0523: `subtotal = sum(line.unit_price_cents for line in lines)` |

## Assessment
UNRESOLVED

Provider call failed: GROQ_API_KEY is not set.
