## Assessment  
**UNRESOLVED**

## Source evidence  
- `SHIPPING_CENTS = {"standard": 500, "express": 1200, "pickup": 0}` ( line 0038 )

## Explanation and limits  
The source defines a dictionary that assigns a cost of 0 cents to the shipping method `"pickup"`, which is consistent with the idea that pickup is free. However, the claim refers specifically to *validation* performed inside `CheckoutRequest.from_dict` at lines 0197‑0199, mapping the string `"pickup"` to a free method. Those lines are not present in the provided batch, so we cannot verify whether the method actually validates the input and uses the dictionary to set a free shipping cost.  

Because we lack the relevant function body, we cannot confirm nor refute the claim. The constant alone does not prove that the validation logic exists or behaves as described. Therefore the assessment remains **UNRESOLVED** for this batch.  

*Next check*: Obtain the implementation of `CheckoutRequest.from_dict` (especially lines 0197‑0199) to see whether it references `SHIPPING_CENTS` and enforces the free‑shipping rule for `"pickup"`.