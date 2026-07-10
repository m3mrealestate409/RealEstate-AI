// Thin API client. All requests go through the backend (API-first, §13).
// The token is kept in localStorage and attached as a Bearer header.

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

export function getToken() {
  return localStorage.getItem("token");
}

export function setSession(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function getUser() {
  const raw = localStorage.getItem("user");
  return raw ? JSON.parse(raw) : null;
}

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  const opts = { method, headers };

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  if (form) {
    // application/x-www-form-urlencoded (used by OAuth2 login)
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    opts.body = new URLSearchParams(form).toString();
  } else if (body instanceof FormData) {
    opts.body = body; // multipart, browser sets boundary
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, opts);

  // Expired/invalid token on an authenticated call → clear session and send
  // the user back to login instead of hanging on a failed request.
  if (res.status === 401 && auth) {
    clearSession();
    if (!location.pathname.endsWith("/login")) location.href = "/login";
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password) =>
    request("/v1/auth/login", { method: "POST", form: { username: email, password }, auth: false }),
  me: () => request("/v1/auth/me"),
  query: (query, session_id) => request("/v1/query", { method: "POST", body: { query, session_id } }),
  projects: (q) => request(`/v1/projects${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  project: (id) => request(`/v1/projects/${id}`),
  projectPrice: (id) => request(`/v1/projects/${id}/price`),
  projectPaymentPlan: (id) => request(`/v1/projects/${id}/payment-plan`),
  projectInventory: (id) => request(`/v1/projects/${id}/inventory`),
  calcTypes: () => request("/v1/calculate/types"),
  calculate: (type, params) => request(`/v1/calculate/${type}`, { method: "POST", body: { params } }),
  createProject: (data) => request("/v1/admin/projects", { method: "POST", body: data }),
  uploadDocument: (formData) => request("/v1/admin/documents", { method: "POST", body: formData }),
  audit: () => request("/v1/admin/audit"),
  health: () => request("/health", { auth: false }),

  // AI settings (admin)
  getLlmSettings: () => request("/v1/admin/settings/llm"),
  updateLlmSettings: (data) => request("/v1/admin/settings/llm", { method: "PUT", body: data }),
  testLlm: () => request("/v1/admin/settings/llm/test", { method: "POST" }),
  listModels: () => request("/v1/admin/settings/models"),

  // Analytics (manager+)
  dashboard: () => request("/v1/analytics/dashboard"),

  // Data management (admin)
  addConfiguration: (projectId, data) =>
    request(`/v1/admin/projects/${projectId}/configurations`, { method: "POST", body: data }),
  listConfigurations: (projectId) =>
    request(`/v1/admin/projects/${projectId}/configurations`),
  updatePrice: (configId, data) =>
    request(`/v1/admin/configurations/${configId}/price`, { method: "PUT", body: data }),
  updateInventory: (configId, data) =>
    request(`/v1/admin/configurations/${configId}/inventory`, { method: "PUT", body: data }),
  addPaymentPlan: (projectId, data) =>
    request(`/v1/admin/projects/${projectId}/payment-plans`, { method: "POST", body: data }),
  importProjectsCsv: (formData) =>
    request("/v1/admin/import/projects-csv", { method: "POST", body: formData }),

  // User management (admin)
  listUsers: () => request("/v1/admin/users"),
  createUser: (data) => request("/v1/admin/users", { method: "POST", body: data }),
  toggleUser: (id) => request(`/v1/admin/users/${id}/toggle`, { method: "POST" }),

  // Knowledge / RAG monitoring
  knowledgeOverview: () => request("/v1/admin/knowledge/overview"),
  listDocuments: () => request("/v1/admin/knowledge/documents"),
  reindexDocument: (id) => request(`/v1/admin/knowledge/documents/${id}/reindex`, { method: "POST" }),
  replaceDocument: (id, formData) =>
    request(`/v1/admin/knowledge/documents/${id}/replace`, { method: "POST", body: formData }),
  deleteDocument: (id) => request(`/v1/admin/knowledge/documents/${id}`, { method: "DELETE" }),

  // System health
  systemHealth: () => request("/v1/admin/system/health"),

  // Super-admin (platform owner)
  saPlans: () => request("/v1/superadmin/plans"),
  saCreatePlan: (data) => request("/v1/superadmin/plans", { method: "POST", body: data }),
  saUpdatePlan: (id, data) => request(`/v1/superadmin/plans/${id}`, { method: "PUT", body: data }),
  saOrgs: () => request("/v1/superadmin/organizations"),
  saCreateOrg: (data) => request("/v1/superadmin/organizations", { method: "POST", body: data }),
  saUpdateOrg: (id, data) => request(`/v1/superadmin/organizations/${id}`, { method: "PUT", body: data }),

  // Builders & document types
  listBuilders: () => request("/v1/admin/builders"),
  createBuilder: (data) => request("/v1/admin/builders", { method: "POST", body: data }),
  getDocTypes: () => request("/v1/admin/document-types"),
  setDocTypes: (types) => request("/v1/admin/document-types", { method: "PUT", body: { types } }),
};
