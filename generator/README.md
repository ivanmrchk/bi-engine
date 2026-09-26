# Synthetic data generator

Simulates three years of a fictional two-location electrical contractor,
Brightwire Electric, and writes the raw files each of its systems would
produce. The numbers are loosely calibrated against a real Seattle-area
contractor, then shifted so the fictional company is not a copy of it.
All names, phone numbers (555), emails (example.com), IPs (RFC 5737) and
the website (.example) are reserved-for-fiction values.

```bash
cd generator
pip install -r requirements.txt
python -m synthetic_data              # seed 42 -> ../data
```

The same seed always produces byte-identical output.

## How it works

The generator first simulates **what really happened**, then renders
**how each system recorded it**, quirks included.

```
calibration.py      the business in numbers: locations, services, prices, seasonality
customers.py   ┐
jobs.py        ┘    the truth: customers, leads, estimates, jobs
sources/            each system's imperfect view of the truth
  housecall_pro.py      paginated JSON (jobs, invoices, estimates), UTC, retyped phones
  grasshopper_*.py      call legs -> weekly, overlapping, hand-exported CSVs
  website_leads.py      WordPress form submissions with UTM tags and spam
  search_console.py     16 months of daily query data, rare queries anonymized
dataset.py          builds everything from one seed
writer.py           writes data/raw/ and data/answer_key/
```

## Output

| Folder | Contents |
|---|---|
| `data/raw/housecall_pro/{jobs,invoices,estimates}/` | `page_NNN.json`, one file per API page |
| `data/raw/grasshopper/` | `Detail_MM.DD.YYYY_HH.MM.SS_PM.csv`, one per manual export |
| `data/raw/website_leads/` | `page_NNN.json` |
| `data/raw/search_console/{by_date,by_query_page}/` | `YYYY-MM-DD.json`, one API response per day |
| `data/answer_key/` | The hidden truth: `leads.csv`, `call_legs.csv`, `website_submissions.csv` |

The pipeline ingests only `data/raw/`. The answer key exists so the
pipeline's attribution can be graded against what really happened, which
real data can never offer.

## Traps planted for the pipeline

- Housecall Pro doesn't record which location a job belongs to.
- "Complete" jobs include $99 estimate-only visits.
- Phone numbers are typed in six formats; cities in inconsistent case.
- One phone call is several CSV rows ("legs"); owner-placed calls log an
  inbound row from the owner's own cell.
- Weekly call exports overlap, and a call can be split across two files.
- Known customers calling about booked work are not new leads; suppliers
  look like local leads but never book.
- Web forms: double submissions, ~14% spam, empty strings instead of nulls.
- Three timestamp conventions: UTC with `Z`, local 12-hour, local ISO.
- Search Console totals exceed the sum of their query rows.
