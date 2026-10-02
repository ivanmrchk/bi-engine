// The dashboard's state (month and location), loading, and wiring.

import { getJson, uploadFile } from "./api.js";
import { enableTooltips } from "./charts.js";
import { addMonths } from "./format.js";
import { html, render } from "./html.js";
import {
  briefPanel, callHandlingPanel, channelPanel, coveragePanel, hotServicesPanel, laggingCitiesPanel, statTiles,
} from "./panels.js";

const CALL_HISTORY_MONTHS = 12;
const CHANNEL_MONTHS = 3;

const element = (id) => document.getElementById(id);
const monthInput = element("month");
const locationSelect = element("location");
const dashboard = element("dashboard");

const state = { month: null, location: "" };
let latestRequest = 0; // a newer request makes older, slower responses irrelevant

async function start() {
  enableTooltips(element("tooltip"));
  const months = await getJson("/analysis/months");
  monthInput.min = months.first_month;
  monthInput.max = months.last_month;
  monthInput.value = state.month = months.last_complete_month;

  monthInput.addEventListener("change", () => { state.month = monthInput.value; refresh(); });
  locationSelect.addEventListener("change", () => { state.location = locationSelect.value; refresh(); });
  element("upload-form").addEventListener("submit", uploadExport);
  refresh();
}

async function refresh() {
  if (!state.month) return;
  const request = ++latestRequest;
  const isCurrent = () => request === latestRequest;
  const scope = { location: state.location };

  // Keep the previous numbers visible, dimmed, until the new ones arrive.
  dashboard.classList.add("is-loading");
  const [services, cities, calls, channels, coverage] = await Promise.allSettled([
    getJson("/analysis/hot-services", { month: state.month, ...scope }),
    getJson("/analysis/lagging-cities", { month: state.month, months: 6, ...scope }),
    getJson("/analysis/call-handling", { first_month: addMonths(state.month, -(CALL_HISTORY_MONTHS - 1)), last_month: state.month, ...scope }),
    getJson("/analysis/channel-funnel", { first_month: addMonths(state.month, -(CHANNEL_MONTHS - 1)), last_month: state.month, ...scope }),
    getJson("/ingest/coverage"),
  ]);
  if (!isCurrent()) return;

  show("tiles", services, (report) => statTiles(report.services, calls.value || [], state.month));
  show("hot-services", services, hotServicesPanel);
  show("lagging-cities", cities, laggingCitiesPanel);
  show("call-handling", calls, callHandlingPanel);
  show("channels", channels, channelPanel);
  show("coverage", coverage, (report) => coveragePanel(report, null));
  dashboard.classList.remove("is-loading");

  // The brief takes a few seconds to write, so it loads on its own.
  render(element("brief"), html`<p class="meta">Writing the brief for this month…</p>`);
  const brief = await Promise.allSettled([getJson("/brief", { month: state.month, ...scope })]);
  if (isCurrent()) show("brief", brief[0], briefPanel);
}

function show(id, result, panel) {
  render(element(id), result.status === "fulfilled"
    ? panel(result.value)
    : html`<p class="delta bad">Couldn't load this: ${result.reason.message}</p>`);
}

async function uploadExport(event) {
  event.preventDefault();
  const file = element("upload-file").files[0];
  if (!file) return;
  const button = event.submitter;
  button.disabled = true;
  button.textContent = "Uploading…";
  let upload;
  try {
    upload = await uploadFile("/ingest/grasshopper", file);
  } catch (error) {
    upload = { error: error.message };
  }
  button.disabled = false;
  button.textContent = "Upload";
  if (upload.was_new) return refresh(); // new calls change every panel
  render(element("coverage"), coveragePanel(upload.coverage || await getJson("/ingest/coverage"), upload));
}

start().catch((error) => render(dashboard, html`<p class="delta bad">The dashboard couldn't start: ${error.message}</p>`));
