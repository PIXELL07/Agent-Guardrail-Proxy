const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, apiKey, options = {}) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
      ...options.headers,
    },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${resp.status}`);
  }
  return resp.json();
}

export function fetchStats(apiKey) {
  return request("/v1/stats", apiKey);
}

export function fetchAudit(apiKey, limit = 50) {
  return request(`/v1/audit?limit=${limit}`, apiKey);
}

export function inspectPayload(apiKey, payload) {
  return request("/v1/inspect", apiKey, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
