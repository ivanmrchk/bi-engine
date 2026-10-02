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

## Planted stories

The report also checks that the pipeline's own analyses find what the
generator planted. Across four seeds:

| Story | Expected finding | Found |
|---|---|---|
| Sammamish's landing pages drop out of Google | demand fell | 3 of 4 seeds |
| A cheaper competitor reaches Bellevue | conversion fell | 3 of 4 |
| Issaquah's work shifts to smaller jobs | ticket size fell | 4 of 4 |
| The AI call taker is adopted | unanswered calls at least halve | 4 of 4 |
| ChatGPT becomes a lead channel | at least 3x the leads of the first year | 4 of 4 |

City stories are judged on six months of jobs against the same months a
year earlier, and a factor only counts as a reason when its change is
beyond chance (about two standard errors). With a few dozen jobs per city,
a year-ago window that happened to be unusually bad or good can hide a real
change, which is what the two misses are: the analysis reports no clear
reason rather than a wrong one.

## Grading definitions

- A lead **converted** if it reached Housecall Pro at all: a job or an estimate.
  Leads that never did are expected as `unconverted_caller`.
- A customer is **returning** only if they were already in Housecall Pro
  before the lead. Someone who asked before but never booked is a new customer.
