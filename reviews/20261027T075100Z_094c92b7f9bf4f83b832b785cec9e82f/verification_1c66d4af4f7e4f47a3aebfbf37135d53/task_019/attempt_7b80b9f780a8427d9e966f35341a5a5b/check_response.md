## Assessment  
**SUPPORTED IN THIS BATCH**

## Source evidence  
- `CheckoutRequest.from_dict` lines 0195‑0196:  

  ```python
  0195: if len({line.sku for line in lines}) != len(lines):
  0196:     raise ServiceError("Combine duplicate SKUs into one cart line")
  ```

## Explanation and limits  
The code builds a set of SKUs from the parsed cart lines and compares its size to the number of lines. If they differ, a `ServiceError` is raised with the message *“Combine duplicate SKUs into one cart line”*. This behavior **rejects** a request that contains duplicate SKUs instead of automatically merging them into a single line. No logic in this block combines duplicates; it only detects and aborts.  

Thus the claim that “Duplicate‑SKU validation rejects duplicates instead of combining them” is directly supported by the source.  

Limitations: The assessment is confined to the shown `CheckoutRequest.from_dict` implementation. Other parts of the codebase (outside this batch) might perform SKU combination elsewhere, but within this batch the validation is clearly a rejection.  

## Next check  
- Verify whether any higher‑level caller or helper later combines duplicate SKUs before invoking `CheckoutRequest.from_dict`. Since caller retrieval is disabled for this batch, that question remains **UNRESOLVED** here.