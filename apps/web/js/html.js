// Building HTML from data without letting the data become HTML.
//
// Everything interpolated into html`...` is escaped, so text from the API,
// including the language model's brief, can never inject markup or scripts.
// Only fragments that html`...` built itself pass through unescaped.

class SafeHtml {
  constructor(markup) {
    this.markup = markup;
  }
}

export function html(strings, ...values) {
  const markup = strings.reduce((built, text, index) => built + text + (index < values.length ? toMarkup(values[index]) : ""), "");
  return new SafeHtml(markup);
}

export function render(element, safeHtml) {
  element.innerHTML = safeHtml.markup;
}

function toMarkup(value) {
  if (value instanceof SafeHtml) return value.markup;
  if (Array.isArray(value)) return value.map(toMarkup).join("");
  if (value === null || value === undefined || value === false) return "";
  return escape(String(value));
}

function escape(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
