// The API, reached through the same origin: nginx forwards /api/* to it.

const API_ROOT = "/api";

export async function getJson(path, parameters = {}) {
  const query = new URLSearchParams(
    Object.entries(parameters).filter(([, value]) => value !== null && value !== undefined && value !== ""),
  );
  const response = await fetch(`${API_ROOT}${path}?${query}`);
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

export async function uploadFile(path, file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_ROOT}${path}`, { method: "POST", body: form });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

async function errorMessage(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}
