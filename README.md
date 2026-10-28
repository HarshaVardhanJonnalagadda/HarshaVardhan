# Python Code Review Agent

A reusable Python command-line tool that reviews Python source in response
to an ordinary-language question using Groq inference.

The tool reads and parses the reviewed source without importing or
executing it. Source files, questions and optional business rules are
provided at runtime. Defect answers are not hardcoded.

## Requirements

- Python 3.11 or newer; tested with Python 3.11.18
- tiktoken 0.14.0
- A Groq API key and available quota for live reviews

The supplied order service remains unchanged in Data/.

## Setup

Run these commands from the project root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Alternatively, activate an existing Python 3.11 environment.

Set GROQ_API_KEY in the same terminal used to run the reviewer.
For macOS zsh, enter the key without displaying it:

```zsh
read -s "GROQ_API_KEY?Paste your Groq API key and press Enter: "
export GROQ_API_KEY
```

Never commit credentials. The default model is openai/gpt-oss-120b.

## Run a review

Supply a Python source path and an ordinary-language request:

```bash
python reviewer.py Data/order_service.py \
  --request "Review this code for bugs affecting totals or stock." \
  --rules Data/BUSINESS_RULES.md
```

The user does not need to identify a faulty function or line.

To read a question from a text file:

```bash
python reviewer.py Data/order_service.py \
  --request-file requests/my-question.txt \
  --rules Data/BUSINESS_RULES.md
```

The request file must exist and contain the question.
Business rules are optional.

Prepare prompts without making API calls:

```bash
python reviewer.py Data/order_service.py \
  --request "Review this code for bugs." \
  --rules Data/BUSINESS_RULES.md \
  --dry-run
```

Display all reviewer options:

```bash
python reviewer.py --help
```

## Workflow

1. Read the source, calculate its hash and parse its Python syntax.
2. Divide the source into overlapping numbered sections.
3. Send each section with the request and optional business rules.
4. Save prompts, available raw responses, usage and outcome metadata.
5. Check that the reviewed source remains unchanged.
6. Assess generated findings against the original source and rules.

The tool processes every source line, but individual sections may lack
related code. Section reviews are candidate findings, not verified facts.

    ## Project files

    - reviewer.py: main review CLI
    - source_context.py: source loading and section preparation
    - prompts.py: review prompt construction
    - provider.py: Groq HTTP connection and response parsing
    - evidence_store.py: evidence and metadata storage
    - resume_review.py: reuse validated successful section responses
    - consolidate.py: optional consolidation of section notes
    - resume_consolidation.py: consolidation recovery utility
    - verification_context.py: approximate source-context retrieval
    - verification_plan.py: prepare source-verification tasks
    - verify_report.py: optional model assessment of retrieved evidence
    - Data/: unchanged supplied service, rules and cases
    - requests/: saved ordinary-language questions
    - reviews/: review runs and validation notes
    - tests/: automated tests
    - evidence/: saved test output
    - review-input/: checksum-verified supplied assignment files; Data/ is
    retained as an identical compatibility copy for earlier commands.

## Results and evidence

Every review prints its evidence folder under reviews/.

Important files within a run include:

- request.txt: the question
- rules.txt: supplied business rules
- source_snapshot.py: saved source text
- section_*_prompt.json: exact model request payloads
- section_*_context.txt: numbered source context
- section_*_raw_response.json: available raw model responses
- section_*_response.md: individual section reviews
- section_*_metadata.json: individual call outcomes and usage
- section_reviews.md: combined section responses, when available
- metadata.json: run outcome, duration and token usage
- validation.md: assessment of supported and unsupported findings

Check metadata.json before treating a run as complete.
Failed and partial runs are retained.
Unavailable usage values are recorded as unknown.

Generated model evidence is preserved separately from validation notes.

## Assignment review runs

The following completed section-review runs are under reviews/:

| Request | Run folder |
| --- | --- |
| Three-mug order total | 20261027T075100Z_094c92b7f9bf4f83b832b785cec9e82f |
| Cancelled-order sales report | 20261027T153834Z_38f4c38b13ed4aa0839b3025640a905b |
| General review of totals and stock | 20261028T040809Z_7d35c55538ff404cb032cf64863ef21b |

Each listed run completed nine section reviews.
Completion does not establish correctness of every generated finding.

Earlier failed runs and resumed runs are retained.
Resumed runs identify their reused section responses in resume_info.json.
Do not sum usage across linked runs without accounting for reused calls.

## Resume a review

Replace RUN_FOLDER with the actual saved run path:

```bash
python resume_review.py RUN_FOLDER Data/order_service.py --check-only
python resume_review.py RUN_FOLDER Data/order_service.py
```

The resume tool validates saved prompts and successful raw responses
before reusing them. It estimates the budget for remaining calls.

A passing budget estimate does not guarantee provider acceptance or
available daily quota. Do not resume a complete run unnecessarily.

## Optional consolidation and verification

Consolidation combines section notes; it does not independently inspect
the original source.

```bash
python consolidate.py RUN_FOLDER
```

To prepare verification tasks from a generated report:

```bash
python verification_plan.py PATH_TO_REVIEW_MD
```

Then inspect the plan's estimated budgets:

```bash
python verify_report.py VERIFICATION_FOLDER --dry-run
```

Run eligible verification tasks:

```bash
python verify_report.py VERIFICATION_FOLDER
```

Replace uppercase placeholders with actual paths.
These live stages consume additional provider quota.
Verification may remain partial, blocked or unresolved.
Its assessments still require human validation.

## Tests

Run local tests and save their output:

```bash
mkdir -p evidence
python -m unittest discover -s tests -v > evidence/test-results.txt 2>&1
cat evidence/test-results.txt
```

The latest recorded test run passed 34 tests.
The saved output is evidence/test-results.txt.

Tests use simulated provider responses. Passing tests do not establish
that live model findings are correct.

## Check supplied-file integrity

On macOS:

```bash
(cd Data && shasum -a 256 -c SHA256SUMS.txt)
```

Keep the supplied source, rules and cases unchanged.
The Data/README.md documents the supplied sample service.
This root README documents the review tool.

## Known limitations

- Section boundaries can split functions and SQL statements.
- Individual sections can lack relevant helpers, callers or validation.
- Models can invent defects, overstate severity or cite inaccurate lines.
- Context retrieval approximates relationships using names and a depth
  limit; runtime types and dynamic calls are not fully resolved.
- Consolidation can lose context or mishandle conflicting notes.
- Provider rate limits, daily quotas and output limits can interrupt runs.
- Token estimates do not guarantee acceptance by the provider.
- Optional verification may be incomplete or unresolved.
- Runtime reproduction and fix verification have not been performed
  for the findings documented in the general-review validation notes.

Human assessment must distinguish supported findings, refuted claims,
missing evidence and requirements that were not specified.

## Provider and model choice

Groq with openai/gpt-oss-120b was selected because free-tier access
supported the assignment's code-review workflow. The tool uses the
provider's HTTP API and records available token usage. Rate limits
and daily quotas required pauses and resumable runs.

## Independent-file demonstration

The tool also reviewed examples/average_example.py using an
ordinary-language question without identifying the faulty line.

Evidence:
reviews/20261028T053704Z_e1d60fc9b4a44d06811e106de0ce8b94/

The model identified the deliberate accumulation bug. Its response
also contained an incorrect explanation and speculative findings,
documented separately in that run's validation.md.

## Incomplete work and remaining limitations

Runtime reproduction and fix verification remain unperformed.
Some historical consolidation and verification attempts failed or
remained incomplete; their saved metadata records these outcomes.

Section boundaries can split functions and SQL statements, producing
incomplete context and false positives. Human validation remains
necessary.

Failed-call token usage is now preserved when supplied in a response.
Run-level totals cover successful calls only, as stated in their
usage_scope metadata. Reused calls must not be counted again when
calculating usage across resumed runs.

Historical evidence has not been rewritten to reflect later fixes.

Selected completed-run usage is summarized in [evidence/usage-summary.md](evidence/usage-summary.md).