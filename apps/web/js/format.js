// How numbers and months read on the page.

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function dollars(cents) {
  return `$${Math.round(cents / 100).toLocaleString("en-US")}`;
}

export function compactDollars(cents) {
  const value = cents / 100;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 10_000) return `$${Math.round(value / 1_000)}K`;
  return dollars(cents);
}

export function percent(share) {
  return share === null || share === undefined ? "–" : `${Math.round(share * 100)}%`;
}

export function percentChange(change) {
  if (change === null || change === undefined) return "–";
  const rounded = Math.round(change * 100);
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

// "2026-08" or "2026-08-01" -> "Aug 2026"
export function monthLabel(month) {
  const [year, monthNumber] = month.split("-");
  return `${MONTH_NAMES[Number(monthNumber) - 1]} ${year}`;
}

// "2026-08", -11 -> "2025-09"
export function addMonths(month, count) {
  const [year, monthNumber] = month.split("-").map(Number);
  const monthsSinceYearZero = year * 12 + (monthNumber - 1) + count;
  const newMonth = (monthsSinceYearZero % 12) + 1;
  return `${Math.floor(monthsSinceYearZero / 12)}-${String(newMonth).padStart(2, "0")}`;
}
