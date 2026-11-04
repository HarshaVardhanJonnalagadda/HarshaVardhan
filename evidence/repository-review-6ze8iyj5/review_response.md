**What happens when `provider.py` raises a `ProviderError` while `reviewer.py` is running?**  

| File (repo‑relative) | Line(s) | What the code does |
|----------------------|---------|--------------------|
| **provider.py** | 14‑20 | Defines `class ProviderError(RuntimeError)`. The constructor stores `raw_response` and `duration_seconds`. |
| **provider.py** | 82‑158 | `call_model()` builds an HTTP request, then **raises `ProviderError`** in three places: <br>• If the API key is missing (line 85‑86). <br>• If the HTTP request returns a non‑2xx status (lines 108‑153). <br>• If the request fails at the transport level (lines 159‑163). |
| **reviewer.py** | 11 | Imports `ProviderError` from `provider.py`. |
| **reviewer.py** | 90‑94 | Inside the per‑section loop, the call to `call_model()` (line 91) is wrapped in a `try/except ProviderError`. When the exception is caught: <br>• `save_call_failure(folder, name, exc)` is invoked (line 93). <br>• The exception is **re‑raised** immediately (line 94). |
| **evidence_store.py** | 85‑120 | `save_call_failure()` writes the raw response (if any) to `<call_name>_raw_response.json` (line 94‑95) and creates a `<call_name>_metadata.json` file that records the outcome `"failed"`, the stringified error, the duration, and a best‑effort usage estimate (lines 115‑120). |
| **reviewer.py** | 59‑124 | The outer `try` that encloses the whole section‑processing loop catches `ProviderError` again (line 119‑121). It stores the error message in the local variable `failure`. The `finally` block later writes a `metadata.json` file that includes `"error": failure` (line 168). |
| **reviewer.py** | 171‑175 | After the `finally` block, if `failure` is not `None` the function prints an error message to `stderr` (lines 172‑173) and returns exit‑code 1 (line 174). |

### Summary of the handling flow  

1. **`call_model()`** encounters an API problem → raises `ProviderError`.  
2. **`reviewer.py` (inner loop)** catches it, records the failure with `save_call_failure()`, then **re‑raises** the exception.  
3. The **outer `try`** in `reviewer.py` catches the re‑raised `ProviderError`, stores the error string in `failure`, and lets execution fall through to the `finally` block.  
4. The `finally` block writes a top‑level `metadata.json` that contains the error message (`"error": failure`).  
5. After cleanup, `reviewer.py` prints an “Incomplete” message and exits with status 1.

Thus, an API error stops the review run after the first failing section, logs detailed evidence for that call, and propagates the error up to the overall run‑level metadata.

### Suggested fix (do not apply)

If the intended behaviour is to **continue processing the remaining sections** even when a single API call fails, the current re‑raise on line 94 prevents that. A possible fix would be:

1. **Remove the `raise`** inside the inner `except ProviderError` block (line 94) so that the loop can keep iterating over the remaining sections.  
2. Optionally, set a flag (e.g., `had_failure = True`) and let the outer `except ProviderError` be removed or changed to a generic `except Exception` that only records the failure without aborting.  
3. Ensure that the final `metadata.json` reflects a mixed outcome (e.g., `"outcome": "partial_success"`), and that `failure` contains a summary of all errors rather than just the first one.

If the design is to **abort on the first failure**, the current logic is correct; however, the comment in the `finally` block (“failed‑call usage may be unavailable”) suggests that the author expects the run to stop on error, so the code is consistent with that intention.

### What is missing?

* The exact definition of `API_URL` and any other constants used by `call_model()` is not shown, but they are not needed to understand the error‑handling path.  
* The implementation of `save_call_failure()` is provided, but the surrounding context (e.g., how `folder` is created) is omitted; however, the call site and its effect are clear from the excerpts.  

No additional evidence is required to answer the question.