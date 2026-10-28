# Validation: independent average example

Method: static comparison of the live model response with the complete
13-line example. No runtime reproduction or fix verification performed.

## Supported finding

The model correctly identified that total = value replaces the running
total instead of accumulating it. The function returns the final element
divided by the sequence length, rather than the arithmetic mean.

For [2, 4, 6], static inspection predicts 2 instead of the expected 4.

## Corrections and unsupported claims

- The claim that identical elements make the result correct is false.
  For [4, 4], the function returns 2 instead of 4.
- Explicit numeric-input validation is not an established requirement.
- The function requires an input supporting len(); describing it as
  accepting any iterable is inaccurate.
- Searching for a custom sum implementation is irrelevant because this
  function does not call sum.
- Speculation about wrappers or custom types is not evidence of a defect.

## Conclusion and limits

A live review identified the deliberate defect in an unrelated Python
file using an ordinary-language request without manually selected lines.

This demonstrates one successful independent example. It does not prove
that the tool finds every bug or avoids false positives.

The example is deliberately buggy test input; the saved review is a real
model response. The reviewer did not execute the example.
