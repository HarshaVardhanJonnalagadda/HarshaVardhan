## Findings  

| Severity | Title | Location & Code |
|----------|-------|-----------------|
| **Medium** | **Shipping method case‑sensitivity** | `CheckoutRequest.from_dict` – lines 0197‑0199  <br>```python\nshipping = value.get(\"shipping\", \"standard\")\nif not isinstance(shipping, str) or shipping not in SHIPPING_CENTS:\n    raise ServiceError(\"Shipping must be standard, express or pickup\")\n``` |
| **Medium** | **Coupon string is upper‑cased but not validated for existence** | `CheckoutRequest.from_dict` – lines 0200‑0203  <br>```python\ncoupon = value.get(\"coupon\")\nif coupon is not None:\n    coupon = nonempty(coupon, \"coupon\", 40).upper()\n``` |
| **Low** | **Potential missing transaction handling for stock‑affecting operations** (not shown in this fragment) | `Database.__init__` – line 0330 (sets `isolation_level=None`) and `Database.initialize` – lines 0337‑0343. The fragment does not show any explicit `BEGIN`/`COMMIT` around operations that reserve stock or write order totals, so callers may rely on autocommit. If a checkout routine performs several separate writes (reserve inventory, create order, write order lines) without an explicit transaction, a failure part‑way could leave stock reduced while the order is not persisted, corrupting totals/stock. |
| **Low** | **`Database.initialize` uses helper methods (`self.one`, `self.execute`) that are not defined in the shown code** | Lines 0338‑0343. If those helpers do not wrap their calls in a transaction or do not raise on failure, the schema‑initialisation step could silently succeed while later code assumes the metadata row exists, potentially causing later calculations (e.g., discount limits that depend on a stored schema version) to behave incorrectly. |

### What the code demonstrably does  

* **Shipping validation** – Accepts only values that exactly match a key in `SHIPPING_CENTS`. The default is the literal string `"standard"`. If a client sends `"Standard"` (capital “S”) or any other case variation, the check fails and a `ServiceError` is raised, even though the business rule treats shipping as case‑insensitive. This aborts the checkout before any totals or stock are touched, but it also prevents legitimate orders from being processed.  

* **Coupon handling** – When a coupon code is supplied, it is stripped/validated for length (`nonempty`) and forced to upper‑case, but the code does **not** verify that the coupon actually exists or is active. Down‑stream code that calculates the discount will receive a string that may not correspond to a row in the `coupons` table, potentially resulting in a `None` discount (i.e., no discount applied) or, if the downstream code assumes existence, a `KeyError`/`IntegrityError`. Either outcome can cause the final `total_cents` to be wrong.  

* **Database initialization** – The `Database` constructor opens the SQLite connection with `isolation_level=None`, which puts the connection in *autocommit* mode. `initialize` runs the schema script and then queries/updates the `metadata` table via helper methods that are not shown. Because autocommit is on, each statement is committed immediately. If later checkout logic performs multiple writes (stock decrement, order insert, order‑line insert) without an explicit transaction, a failure after the stock decrement will leave the inventory ledger inconsistent with the order total.  

## Uncertainty  

* **`CartLine.from_dict` validation** – The fragment does not show `CartLine`. If that class does not enforce `quantity > 0` or price positivity, the subtotal could be mis‑computed elsewhere.  

* **Implementation of `self.one` / `self.execute`** – Without seeing these helpers we cannot be certain whether they start a transaction, raise on errors, or perform additional validation.  

* **How coupon codes are later looked up** – The fragment only upper‑cases the code; we do not know whether the lookup is case‑insensitive or whether missing coupons are handled gracefully.  

* **Whether downstream code explicitly starts a transaction** – The fragment does not include the checkout service that writes inventory events and order rows. If that code does start a transaction (e.g., `BEGIN; … COMMIT;`), the autocommit setting may be overridden, mitigating the low‑severity risk.  

## Next checks  

1. **Inspect the checkout workflow** (the function that receives a `CheckoutRequest` and creates an order). Verify that:  
   * It opens a transaction (`BEGIN`/`COMMIT` or `with connection:`) that encloses **all** stock reservations, order row inserts, and order‑line inserts.  
   * It rolls back on any exception, ensuring stock is not decremented without a matching order.  

2. **Review `CartLine.from_dict`** to confirm that:  
   * `quantity` is required and must be a positive integer.  
   * `sku` exists in the `products` table and the product is active.  

3. **Examine coupon validation** in the order‑pricing code:  
   * Does it query the `coupons` table and verify `active`, `expires_on`, `max_uses`, etc.?  
   * Does it handle the case where the supplied code does not exist (should raise a clear error, not silently ignore the discount)?  

4. **Check the definition of `SHIPPING_CENTS`** – ensure the keys are lower‑case and that the API documentation (or client code) either normalises input or that the validation is case‑insensitive. If not, consider normalising (`shipping.lower()`) before the membership test.  

5. **Locate the implementations of `Database.one` and `Database.execute`**:  
   * Confirm they raise on failure and that they do not silently swallow errors.  
   * Verify they are used consistently for all write‑heavy operations (stock updates, order creation).  

6. **Confirm that the `metadata` table is populated correctly** after `initialize`. The code expects a row with key `"schema"`; ensure that the helper methods create it if missing and that the stored `SCHEMA_VERSION` matches the constant used elsewhere.  

Addressing the items above will reduce the risk of incorrect order totals, misplaced discounts, and inventory inconsistencies.