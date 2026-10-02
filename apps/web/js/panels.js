// One function per dashboard panel: an API response in, HTML out.

import { barList, dataTable, stackedColumns, tableView } from "./charts.js";
import { compactDollars, dollars, monthLabel, percent, percentChange } from "./format.js";
import { html } from "./html.js";

const CHANNEL_NAMES = {
  google_ads: "Google Ads",
  google_business_profile: "Google Business Profile (tagged link)",
  google_search_or_profile: "Google search or Business Profile",
  chatgpt: "ChatGPT",
  referral: "Referrals",
  website_unspecified: "Website (source not recorded)",
  unknown: "Unknown (mostly phone calls)",
};

const CALL_SERIES = [
  { key: "answered_by_owner", label: "Owner answered", slot: 1 },
  { key: "answered_by_ai", label: "AI call taker", slot: 2 },
  { key: "voicemail", label: "Voicemail", slot: 3 },
  { key: "missed", label: "Missed", slot: 4 },
];

// --- The brief ---------------------------------------------------------------

export function briefPanel(brief) {
  const byModel = brief.written_by !== "template";
  const rejected = brief.rejected_drafts.length;
  return html`
    <p class="brief-headline">${brief.text.headline}</p>
    <p>${brief.text.summary}</p>
    <div class="brief-split">
      <div><h3>Biggest opportunity</h3><p>${brief.text.biggest_opportunity}</p></div>
      <div><h3>Biggest risk</h3><p>${brief.text.biggest_risk}</p></div>
    </div>
    <p class="meta">
      ${byModel
        ? `Written by ${brief.written_by} from the month's numbers and the notes below. Every number in it was checked against them.`
        : "Assembled directly from the month's numbers, without a language model."}
      ${rejected ? ` ${rejected} draft${rejected > 1 ? "s were" : " was"} rejected for using numbers not in the data.` : ""}
    </p>
    ${brief.notes.length ? html`
      <details>
        <summary>Notes it drew on (${brief.notes.length})</summary>
        <ul class="notes">${brief.notes.map((note) => html`
          <li><span class="meta">${note.written_on}${note.city ? ` · ${note.city}` : ""}${note.times_written > 1 ? ` · written ${note.times_written} times` : ""}</span>${note.body}</li>`)}
        </ul>
      </details>` : ""}`;
}

// --- Headline numbers ------------------------------------------------------------

export function statTiles(services, callMonths, month) {
  const sum = (pick) => services.reduce((total, service) => total + pick(service), 0);
  const revenue = sum((service) => service.this_month.revenue_cents);
  const revenueLastYear = sum((service) => service.same_month_last_year.revenue_cents);
  const jobs = sum((service) => service.this_month.jobs);
  const jobsLastYear = sum((service) => service.same_month_last_year.jobs);
  const calls = callMonths.find((callMonth) => callMonth.month.startsWith(month));

  return html`
    ${tile("Revenue", compactDollars(revenue), delta(revenue, revenueLastYear, true))}
    ${tile("Completed jobs", jobs.toLocaleString("en-US"), delta(jobs, jobsLastYear, true))}
    ${tile("Calls unanswered", calls ? percent(calls.unanswered_share) : "–",
      calls ? html`<span class="meta">${calls.unanswered} of ${calls.calls} · ${calls.never_returned} never called back</span>` : "")}`;
}

function tile(label, value, footnote) {
  return html`<div class="tile"><div class="tile-label">${label}</div><div class="tile-value">${value}</div>${footnote}</div>`;
}

// Direction is shown with an arrow and words, never by color alone.
function delta(now, before, upIsGood) {
  if (!before) return html`<span class="meta">nothing the same month last year</span>`;
  const change = (now - before) / before;
  const good = change >= 0 === upIsGood;
  return html`<span class="delta ${good ? "good" : "bad"}">${change >= 0 ? "▲" : "▼"} ${percentChange(change)}</span>
    <span class="meta"> vs same month last year</span>`;
}

// --- Hot services ------------------------------------------------------------------

export function hotServicesPanel(report) {
  const active = report.services.filter((service) => service.this_month.jobs > 0);
  if (!active.length) return html`<p class="meta">No completed jobs this month.</p>`;
  return html`
    ${barList(active.map((service) => ({
      label: service.service,
      value: service.this_month.revenue_cents,
      valueLabel: dollars(service.this_month.revenue_cents),
      detail: service.has_enough_jobs_vs_last_year
        ? `${percentChange(service.revenue_change_vs_last_year)} vs last year`
        : `${jobCount(service.this_month.jobs)} · too few to compare`,
      tooltip: [
        service.service,
        `This month: ${dollars(service.this_month.revenue_cents)} from ${jobCount(service.this_month.jobs)}`,
        `Last month: ${dollars(service.previous_month.revenue_cents)} from ${jobCount(service.previous_month.jobs)}`,
        `Same month last year: ${dollars(service.same_month_last_year.revenue_cents)} from ${jobCount(service.same_month_last_year.jobs)}`,
      ].join("\n"),
    })))}
    ${tableView(dataTable(
      [{ label: "Service" }, { label: "Jobs", numeric: true }, { label: "Revenue", numeric: true },
       { label: "vs last month", numeric: true }, { label: "vs last year", numeric: true }],
      report.services.map((service) => [
        service.service,
        service.this_month.jobs,
        dollars(service.this_month.revenue_cents),
        service.has_enough_jobs_vs_previous_month ? percentChange(service.revenue_change_vs_previous_month) : "too few jobs",
        service.has_enough_jobs_vs_last_year ? percentChange(service.revenue_change_vs_last_year) : "too few jobs",
      ]),
    ))}`;
}

function jobCount(jobs) {
  return `${jobs} job${jobs === 1 ? "" : "s"}`;
}

// --- Lagging cities ---------------------------------------------------------------

export function laggingCitiesPanel(report) {
  const compared = report.cities.filter((city) => city.revenue_change !== null);
  const newCities = report.cities.filter((city) => city.revenue_change === null).map((city) => city.city);
  const period = `${monthLabel(report.recent_period.first_month)}–${monthLabel(report.recent_period.last_month)}`;
  const before = `${monthLabel(report.year_before_period.first_month)}–${monthLabel(report.year_before_period.last_month)}`;

  return html`
    <p class="meta">${period} against ${before}. ▲▼ mark a factor whose change is bigger than chance would produce;
      gray changes could be chance.</p>
    ${dataTable(
      [{ label: "City" }, { label: "Revenue", numeric: true }, { label: "Demand", numeric: true },
       { label: "Conversion", numeric: true }, { label: "Ticket size", numeric: true }],
      [report.company, ...compared].map((city) => {
        const factors = Object.fromEntries(city.factors.map((factor) => [factor.factor, factor]));
        return [
          city === report.company ? html`<strong>${city.city}</strong>` : city.city,
          percentChange(city.revenue_change),
          factorCell(factors.demand),
          factorCell(factors.conversion),
          factorCell(factors["ticket size"]),
        ];
      }),
    )}
    ${newCities.length ? html`<p class="meta">No jobs a year before, so nothing to compare yet: ${newCities.join(", ")}.</p>` : ""}`;
}

function factorCell(factor) {
  if (!factor || factor.change === null) return "–";
  if (!factor.is_clear) return html`<span class="unclear">${percentChange(factor.change)}</span>`;
  return factor.change < 0
    ? html`<span class="delta bad"><span aria-hidden="true">▼</span> ${percentChange(factor.change)}<span class="visually-hidden"> clearly down</span></span>`
    : html`<span class="delta good"><span aria-hidden="true">▲</span> ${percentChange(factor.change)}<span class="visually-hidden"> clearly up</span></span>`;
}

// --- Call handling ---------------------------------------------------------------

export function callHandlingPanel(callMonths) {
  if (!callMonths.length) return html`<p class="meta">No calls in this period.</p>`;
  const columns = callMonths.map((callMonth) => {
    const [year, number] = callMonth.month.split("-");
    return { label: number === "01" ? `Jan ${year.slice(2)}` : monthLabel(callMonth.month).slice(0, 3), values: callMonth };
  });
  return html`
    ${stackedColumns(columns, CALL_SERIES)}
    ${tableView(dataTable(
      [{ label: "Month" }, { label: "Calls", numeric: true }, ...CALL_SERIES.map((series) => ({ label: series.label, numeric: true })),
       { label: "Unanswered", numeric: true }, { label: "Never called back", numeric: true }, { label: "Median callback", numeric: true }],
      callMonths.map((callMonth) => [
        monthLabel(callMonth.month),
        callMonth.calls,
        ...CALL_SERIES.map((series) => callMonth[series.key]),
        percent(callMonth.unanswered_share),
        callMonth.never_returned,
        callMonth.median_minutes_to_callback === null ? "–" : `${Math.round(callMonth.median_minutes_to_callback)} min`,
      ]),
    ))}`;
}

// --- Lead channels ---------------------------------------------------------------

export function channelPanel(report) {
  const largest = Math.max(...report.channels.map((channel) => channel.leads), 1);
  return html`
    ${dataTable(
      [{ label: "Channel" }, { label: "Leads", numeric: true }, { label: "" }, { label: "Closed", numeric: true }],
      report.channels.map((channel) => [
        CHANNEL_NAMES[channel.channel] || channel.channel,
        channel.leads,
        html`<span class="bar-track inline"><span class="bar" style="width: ${(channel.leads / largest) * 100}%"></span></span>`,
        channel.rates_are_inflated
          ? html`<span class="unclear">${percent(channel.close_rate)} <span class="label">⚠ inflated</span></span>`
          : percent(channel.close_rate),
      ]),
    )}
    <p class="meta">Leads from ${monthLabel(report.first_month)} to ${monthLabel(report.last_month)}.
      "⚠ inflated": the channel is only known from Housecall Pro's lead-source field, which exists only on leads that
      booked, so its lost leads land in "Unknown" and its close rate looks better than it is.</p>`;
}

// --- Call-export coverage ----------------------------------------------------------

export function coveragePanel(coverage, upload) {
  const recentGaps = coverage.gaps.slice(-4).reverse();
  return html`
    ${upload ? html`<p class="${upload.error ? "delta bad" : "meta"}">${upload.error
      ? `Upload failed: ${upload.error}`
      : `${upload.file_name}: ${upload.was_new ? "stored, and the dashboard's data was rebuilt." : "already stored, so nothing changed."}`}</p>` : ""}
    <p class="meta">${coverage.exports} exports stored, covering calls through ${coverage.covered_until ? coverage.covered_until.slice(0, 10) : "–"}.</p>
    ${coverage.gaps.length ? html`
      <p><span class="delta bad">⚠ ${coverage.gaps.length} possible gaps</span> where no export covers the time. Re-export these ranges:</p>
      <ul class="gaps">${recentGaps.map((gap) => html`<li>${gap.missing_from.slice(0, 16).replace("T", " ")} → ${gap.missing_until.slice(0, 16).replace("T", " ")} UTC</li>`)}</ul>
      ${coverage.gaps.length > recentGaps.length ? html`<p class="meta">Showing the ${recentGaps.length} most recent.</p>` : ""}` : html`<p class="meta">No gaps between exports.</p>`}`;
}
