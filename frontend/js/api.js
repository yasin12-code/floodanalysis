/* Thin wrappers around the backend API. Everything the map shows comes from
   /api endpoints; nothing spatial is hard-coded in the frontend. */

export async function apiGet(path, params = {}) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue;
    if (Array.isArray(value)) {
      for (const item of value) qs.append(key, item);
    } else {
      qs.append(key, value);
    }
  }
  const url = `/api${path}` + (qs.toString() ? `?${qs.toString()}` : '');
  const res = await fetch(url);
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body && body.detail) {
        detail = Array.isArray(body.detail)
          ? body.detail.map((d) => d.msg).join('; ')
          : String(body.detail);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status})`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        detail = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join('; ')
          : String(data.detail);
      }
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const fetchConfig = () => apiGet('/config');
export const fetchAreas = () => apiGet('/areas');
export const fetchZones = (params) => apiGet('/layers/flood-zones', params);
export const fetchShelters = (params) => apiGet('/layers/shelters', params);
export const fetchRoads = (params) => apiGet('/layers/roads', params);
export const fetchReports = (params) => apiGet('/layers/flood-reports', params);
export const riskCheck = (params) => apiGet('/risk-check', params);
export const fetchStats = (params) => apiGet('/stats', params);
export const submitShelter = (body) => apiPost('/shelters', body);
export const submitFloodReport = (body) => apiPost('/flood-reports', body);

export function escapeHtml(value) {
  if (value === null || value === undefined) return '';
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function formatDistance(metres) {
  if (metres === null || metres === undefined) return '—';
  if (metres < 1000) return `${Math.round(metres)} m`;
  return `${(metres / 1000).toFixed(1)} km`;
}
