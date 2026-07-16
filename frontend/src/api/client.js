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

// Give every request a hard timeout. Without this, a hung/restarting backend
// leaves the fetch pending forever — the caller's `loading` flag never clears
// and buttons (e.g. "Ask") stay disabled until a manual page reload.
const REQUEST_TIMEOUT_MS = 45000;

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const opts = { method, headers, signal: controller.signal };

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

  let res;
  try {
    res = await fetch(`${BASE}${path}`, opts);
  } catch (err) {
    if (err.name === "AbortError") throw new Error("Request timed out — the server took too long. Please try again.");
    throw new Error("Could not reach the server. Check your connection and try again.");
  } finally {
    clearTimeout(timer);
  }

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

// Fetch a protected binary file (e.g. a PDF) with auth and return the Blob.
export async function fetchBlob(path) {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (res.status === 401) {
    clearSession();
    if (!location.pathname.endsWith("/login")) location.href = "/login";
    throw new Error("Session expired");
  }
  if (!res.ok) throw new Error("Could not load file");
  return res.blob();
}

// Same, but as an object URL (for inline viewing).
export async function fetchBlobUrl(path) {
  return URL.createObjectURL(await fetchBlob(path));
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
  projectTowers: (id) => request(`/v1/projects/${id}/towers`),
  projectLocation: (id) => request(`/v1/projects/${id}/location`),
  brochureInfo: (id) => request(`/v1/projects/${id}/brochure/info`),
  costSheetInfo: (id) => request(`/v1/projects/${id}/cost-sheet/info`),
  listCostSheets: (id) => request(`/v1/projects/${id}/cost-sheets`),
  uploadCostSheet: (projectId, formData) =>
    request(`/v1/admin/projects/${projectId}/cost-sheet`, { method: "POST", body: formData }),
  deleteCostSheet: (projectId, docId) =>
    request(`/v1/admin/projects/${projectId}/cost-sheets/${docId}`, { method: "DELETE" }),
  calcTypes: () => request("/v1/calculate/types"),
  calculate: (type, params) => request(`/v1/calculate/${type}`, { method: "POST", body: { params } }),
  createProject: (data) => request("/v1/admin/projects", { method: "POST", body: data }),
  updateProject: (id, data) => request(`/v1/admin/projects/${id}`, { method: "PUT", body: data }),
  listTowers: (projectId) => request(`/v1/admin/projects/${projectId}/towers`),
  addTower: (projectId, data) => request(`/v1/admin/projects/${projectId}/towers`, { method: "POST", body: data }),
  deleteTower: (towerId) => request(`/v1/admin/towers/${towerId}`, { method: "DELETE" }),
  listLocation: (projectId) => request(`/v1/admin/projects/${projectId}/location`),
  addLocation: (projectId, data) => request(`/v1/admin/projects/${projectId}/location`, { method: "POST", body: data }),
  deleteLocation: (id) => request(`/v1/admin/location/${id}`, { method: "DELETE" }),
  projectAmenities: (id) => request(`/v1/projects/${id}/amenities`),
  listAmenities: (projectId) => request(`/v1/admin/projects/${projectId}/amenities`),
  addAmenity: (projectId, data) => request(`/v1/admin/projects/${projectId}/amenities`, { method: "POST", body: data }),
  deleteAmenity: (id) => request(`/v1/admin/amenities/${id}`, { method: "DELETE" }),
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
  usage: () => request("/v1/analytics/usage"),

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
  listPaymentPlans: (projectId) =>
    request(`/v1/admin/projects/${projectId}/payment-plans`),
  deletePaymentPlan: (planId) =>
    request(`/v1/admin/payment-plans/${planId}`, { method: "DELETE" }),
  importProjectsCsv: (formData) =>
    request("/v1/admin/import/projects-csv", { method: "POST", body: formData }),
  extractDraft: (formData) => request("/v1/admin/extract", { method: "POST", body: formData }),
  applyDraft: (projectId, draft) => request(`/v1/admin/projects/${projectId}/apply`, { method: "POST", body: draft }),

  // User management (admin)
  listUsers: () => request("/v1/admin/users"),
  createUser: (data) => request("/v1/admin/users", { method: "POST", body: data }),
  toggleUser: (id) => request(`/v1/admin/users/${id}/toggle`, { method: "POST" }),
  setUserTier: (id, tier) => request(`/v1/admin/users/${id}/tier`, { method: "POST", body: { tier } }),
  toggleUserLiveChat: (id) => request(`/v1/admin/users/${id}/livechat`, { method: "POST" }),
  getTierLimits: () => request("/v1/admin/users/tier-limits"),
  setTierLimits: (data) => request("/v1/admin/users/tier-limits", { method: "PUT", body: data }),

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
  deleteBuilder: (id) => request(`/v1/admin/builders/${id}`, { method: "DELETE" }),
  getDocTypes: () => request("/v1/admin/document-types"),
  setDocTypes: (types) => request("/v1/admin/document-types", { method: "PUT", body: { types } }),

  // Chat widget config (editable greeting)
  getWidgetConfig: () => request("/v1/admin/widget-config"),
  setWidgetConfig: (greeting) => request("/v1/admin/widget-config", { method: "PUT", body: { greeting } }),

  // Assistant persona + identity (org-wide — website, CRM, WhatsApp, app)
  getAssistantConfig: () => request("/v1/admin/assistant-config"),
  setAssistantConfig: (data) => request("/v1/admin/assistant-config", { method: "PUT", body: data }),
  uploadAssistantAvatar: (formData) => request("/v1/admin/assistant-avatar", { method: "POST", body: formData }),
  deleteAssistantAvatar: () => request("/v1/admin/assistant-avatar", { method: "DELETE" }),

  // API keys (external integrations)
  listApiKeys: () => request("/v1/admin/api-keys"),
  createApiKey: (name, channel, scope) => request("/v1/admin/api-keys", { method: "POST", body: { name, channel, scope } }),
  setApiKeyChannel: (id, channel) => request(`/v1/admin/api-keys/${id}/channel`, { method: "POST", body: { channel } }),
  setApiKeyScope: (id, scope) => request(`/v1/admin/api-keys/${id}/scope`, { method: "POST", body: { scope } }),
  revokeApiKey: (id) => request(`/v1/admin/api-keys/${id}`, { method: "DELETE" }),

  // Live chat (agent takeover)
  liveSessions: () => request("/v1/admin/live/sessions"),
  liveTranscript: (sid) => request(`/v1/admin/live/sessions/${encodeURIComponent(sid)}`),
  liveTakeover: (sid) => request(`/v1/admin/live/sessions/${encodeURIComponent(sid)}/takeover`, { method: "POST" }),
  liveSend: (sid, text) => request(`/v1/admin/live/sessions/${encodeURIComponent(sid)}/message`, { method: "POST", body: { text } }),
  liveRelease: (sid) => request(`/v1/admin/live/sessions/${encodeURIComponent(sid)}/release`, { method: "POST" }),

  // Leads (captured prospects) + CRM webhook
  listLeads: () => request("/v1/admin/leads"),
  updateLeadStatus: (id, status) => request(`/v1/admin/leads/${id}`, { method: "PATCH", body: { status } }),
  deleteLead: (id) => request(`/v1/admin/leads/${id}`, { method: "DELETE" }),
  getCrmConfig: () => request("/v1/admin/crm-config"),
  setCrmConfig: (data) => request("/v1/admin/crm-config", { method: "PUT", body: data }),

  // New-chat notifications (Telegram / webhook / etc.)
  getNotifyConfig: () => request("/v1/admin/notify-config"),
  setNotifyConfig: (provider, config) => request("/v1/admin/notify-config", { method: "PUT", body: { provider, config } }),
  testNotifyConfig: () => request("/v1/admin/notify-config/test", { method: "POST" }),
};
