## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
```python
0197: shipping = value.get("shipping", "standard")
0198: if not isinstance(shipping, str) or shipping not in SHIPPING_CENTS:
0199:     raise ServiceError("Shipping must be standard, express or pickup")
```

## Explanation and limits  
The `CheckoutRequest.from_dict` method only **validates** that the supplied `shipping` field is a string and that its value appears in the `SHIPPING_CENTS` mapping. It does **not** perform any mapping of `"pickup"` to a free‑shipping cost; the actual cost lookup (e.g., `SHIPPING_CENTS["pickup"] == 0`) would occur elsewhere, but that code is not present in the provided block. Therefore the claim that “shipping‑method validation maps `\"pickup\"` to a free method” is not supported by the evidence in this batch.

The absence of a cost‑assignment statement here does not prove that such a mapping does not exist elsewhere, but the specific lines cited do not contain it, so the claim is refuted for this batch.

## Next check  
Further investigation of the `SHIPPING_CENTS` definition or any function that computes the order total would be needed to confirm how `"pickup"` is priced. This batch alone does not provide that information.