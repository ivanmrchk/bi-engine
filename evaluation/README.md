# Evaluation

Grades the pipeline's clean layer against the generator's answer key: the
one thing real data can never offer. It lives outside `apps/` so the
pipeline can never see the answers.

```bash
pip install -r evaluation/requirements.txt

# Grade whatever is in the local database against data/answer_key
cd evaluation && python -m grading

# Generate a seed, run the whole pipeline into its own database, and grade it
evaluation/evaluate_seed.sh 7        # PYTHON=.venv/Scripts/python on Windows
```

The attribution rules were tuned on seed 42, so the honest score is the one
on a seed they never saw.

| | seed 42 (tuned on) | seed 7 (held out) |
|---|---|---|
| Spam filter (precision / recall) | 100% / 100% | 100% / 100% |
| Duplicate submissions | 100% / 100% | 100% / 100% |
| Jobs: real or not, service, location | 100% | 100% |
| Call legs grouped into conversations | 99.9% | 100.0% |
| Call classification | 98.4% | 98.2% |
| &nbsp;&nbsp;new customer leads (recall) | 100% | 100% |
| &nbsp;&nbsp;returning customer leads (recall) | 83.2% | 74.7% |

Returning-customer leads are the known limit: a past customer who calls and
never gets a quote or a job looks exactly like one asking about old work.

## Grading definitions

- A lead **converted** if it reached Housecall Pro at all: a job or an estimate.
  Leads that never did are expected as `unconverted_caller`.
- A customer is **returning** only if they were already in Housecall Pro
  before the lead. Someone who asked before but never booked is a new customer.
