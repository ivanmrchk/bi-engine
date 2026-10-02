// Charts as plain HTML and SVG, no library.
//
// Mark specs: bars at most 24px thick with a 4px rounded end, a 2px gap in
// the surface color between stacked segments, hairline gridlines. Every
// chart comes with a table view, and every hover tooltip also opens on
// keyboard focus, so no value is reachable only by pointing at it.

import { html } from "./html.js";

// --- Horizontal bars: comparing magnitudes -----------------------------------

// rows: [{ label, value, valueLabel, detail, tooltip }]
export function barList(rows) {
  const largest = Math.max(...rows.map((row) => row.value), 1);
  return html`<div class="bar-list">${rows.map((row) => html`
    <div class="bar-row" tabindex="0" data-tooltip="${row.tooltip}">
      <span class="bar-label">${row.label}</span>
      <span class="bar-track"><span class="bar" style="width: ${(row.value / largest) * 100}%"></span></span>
      <span class="bar-value">${row.valueLabel}</span>
      <span class="bar-detail">${row.detail}</span>
    </div>`)}</div>`;
}

// --- Stacked columns: parts of a whole over time ------------------------------

const WIDTH = 640;
const HEIGHT = 240;
const PLOT = { left: 36, right: 120, top: 12, bottom: 28 }; // right: room for direct labels
const SEGMENT_GAP = 2;
const MAX_COLUMN_WIDTH = 24;
const END_RADIUS = 4;
const MIN_HEIGHT_FOR_LABEL = 14;

// columns: [{ label, values: { [seriesKey]: number } }]; series: [{ key, label, slot }]
export function stackedColumns(columns, series) {
  const plotWidth = WIDTH - PLOT.left - PLOT.right;
  const plotHeight = HEIGHT - PLOT.top - PLOT.bottom;
  const totals = columns.map((column) => series.reduce((sum, item) => sum + (column.values[item.key] || 0), 0));
  const top = niceCeiling(Math.max(...totals, 1));
  const scale = (value) => (value / top) * plotHeight;
  const band = plotWidth / columns.length;
  const columnWidth = Math.min(MAX_COLUMN_WIDTH, band * 0.6);
  const baseline = PLOT.top + plotHeight;

  const gridlines = [0, top / 2, top].map((tick) => html`
    <line class="gridline" x1="${PLOT.left}" x2="${PLOT.left + plotWidth}" y1="${baseline - scale(tick)}" y2="${baseline - scale(tick)}" />
    <text class="axis-label" x="${PLOT.left - 6}" y="${baseline - scale(tick) + 4}" text-anchor="end">${tick.toLocaleString("en-US")}</text>`);

  const columnMarks = columns.map((column, index) => {
    const x = PLOT.left + band * index + (band - columnWidth) / 2;
    const present = series.filter((item) => (column.values[item.key] || 0) > 0);
    let y = baseline;
    const segments = present.map((item, position) => {
      const height = Math.max(scale(column.values[item.key]) - SEGMENT_GAP, 1);
      y -= height + (position > 0 ? SEGMENT_GAP : 0);
      const isTop = position === present.length - 1;
      return html`<path class="series-${item.slot}" d="${isTop ? roundedTop(x, y, columnWidth, height) : rectangle(x, y, columnWidth, height)}" />`;
    });
    const tooltip = [column.label, ...series.map((item) => `${item.label}: ${column.values[item.key] || 0}`)].join("\n");
    return html`
      <g class="column" tabindex="0" data-tooltip="${tooltip}">
        <rect class="hit-area" x="${PLOT.left + band * index}" y="${PLOT.top}" width="${band}" height="${plotHeight}" />
        ${segments}
        <text class="axis-label" x="${x + columnWidth / 2}" y="${HEIGHT - 8}" text-anchor="middle">${column.label}</text>
      </g>`;
  });

  return html`
    ${legend(series)}
    <svg class="chart" viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Stacked columns; the table view lists every value">
      ${gridlines}
      <line class="baseline" x1="${PLOT.left}" x2="${PLOT.left + plotWidth}" y1="${baseline}" y2="${baseline}" />
      ${columnMarks}
      ${directLabels(columns.at(-1), series, scale, baseline, PLOT.left + band * (columns.length - 1) + (band + columnWidth) / 2)}
    </svg>`;
}

// Labels beside the last column, for segments tall enough to carry one.
function directLabels(lastColumn, series, scale, baseline, x) {
  let y = baseline;
  return series.map((item) => {
    const height = scale(lastColumn.values[item.key] || 0);
    y -= height;
    if (height < MIN_HEIGHT_FOR_LABEL) return "";
    return html`<text class="direct-label" x="${x + 8}" y="${y + height / 2 + 4}">${item.label}</text>`;
  });
}

function legend(series) {
  return html`<ul class="legend">${series.map((item) => html`
    <li><span class="swatch series-${item.slot}"></span>${item.label}</li>`)}</ul>`;
}

function rectangle(x, y, width, height) {
  return `M${x},${y}h${width}v${height}h${-width}z`;
}

// A rectangle whose top corners are rounded: the column's data end.
function roundedTop(x, y, width, height) {
  const radius = Math.min(END_RADIUS, width / 2, height);
  return `M${x},${y + height}v${-(height - radius)}q0,${-radius} ${radius},${-radius}`
    + `h${width - 2 * radius}q${radius},0 ${radius},${radius}v${height - radius}z`;
}

// 0 / 50 / 100 style axis tops: 1, 2, or 5 times a power of ten.
function niceCeiling(value) {
  const magnitude = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 5, 10].map((step) => step * magnitude).find((candidate) => candidate >= value);
}

// --- Tables: every chart's accessible twin -----------------------------------

// columns: [{ label, numeric }]; rows: arrays of cells (text or html``)
export function dataTable(columns, rows) {
  return html`
    <div class="table-scroll"><table>
      <thead><tr>${columns.map((column) => html`<th class="${column.numeric ? "numeric" : ""}">${column.label}</th>`)}</tr></thead>
      <tbody>${rows.map((row) => html`<tr>${row.map((cell, index) => html`
        <td class="${columns[index].numeric ? "numeric" : ""}">${cell}</td>`)}</tr>`)}</tbody>
    </table></div>`;
}

export function tableView(table) {
  return html`<details class="table-view"><summary>Show as a table</summary>${table}</details>`;
}

// --- One tooltip for the whole page ------------------------------------------

export function enableTooltips(tooltip) {
  const show = (target, x, y) => {
    tooltip.replaceChildren(...target.dataset.tooltip.split("\n").map((line) => {
      const row = document.createElement("div");
      row.textContent = line;
      return row;
    }));
    tooltip.hidden = false;
    const left = Math.min(x + 14, window.innerWidth - tooltip.offsetWidth - 8);
    tooltip.style.left = `${Math.max(8, left)}px`;
    tooltip.style.top = `${y + 14}px`;
  };
  const hide = () => { tooltip.hidden = true; };

  document.addEventListener("pointermove", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (target) show(target, event.clientX, event.clientY);
    else hide();
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest("[data-tooltip]");
    if (!target) return;
    const box = target.getBoundingClientRect();
    show(target, box.left + box.width / 2, box.bottom);
  });
  document.addEventListener("focusout", hide);
}
