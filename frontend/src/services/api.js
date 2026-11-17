
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.message || `Request failed with status ${response.status}`
    );
  }

  return data;
}

// Get CSRF token before state-changing requests.
async function getCsrfToken() {
  const response = await fetch(`${API_BASE_URL}/api/csrf/token`, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  const data = await parseResponse(response);

  if (!data.csrf_token) {
    throw new Error("Unable to obtain CSRF token.");
  }

  return data.csrf_token;
}

// POST request.
async function postRequest(endpoint, body = {}) {
  const csrfToken = await getCsrfToken();

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify(body),
  });

  return parseResponse(response);
}

// DELETE request.
async function deleteRequest(endpoint) {
  const csrfToken = await getCsrfToken();

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "DELETE",
    credentials: "include",
    headers: {
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    },
  });

  return parseResponse(response);
}

// GET request.
async function getRequest(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  });

  return parseResponse(response);
}

export const api = {
  // AUTHENTICATION
  async register(userData) {
    return postRequest("/api/auth/register", userData);
  },

  async login(identifier, password) {
    return postRequest("/api/auth/login", {
      identifier,
      password,
    });
  },

  async logout() {
    return postRequest("/api/auth/logout");
  },

  async getCurrentUser() {
    return getRequest("/api/auth/me");
  },

  // BACKEND HEALTH
  async checkHealth() {
    return getRequest("/api/health");
  },

  // DASHBOARD
  async getDashboardSummary() {
    return getRequest("/api/dashboard/summary");
  },

  // DATABASE CONNECTIONS
  async getConnections() {
    return getRequest("/api/connections");
  },

  async saveConnection(connectionData) {
    return postRequest("/api/connections", connectionData);
  },

  async testConnection(connectionId) {
    return postRequest(`/api/connections/${connectionId}/test`);
  },

  async deleteConnection(connectionId) {
    return deleteRequest(`/api/connections/${connectionId}`);
  },

  // SQL QUERY ANALYSIS
  async analyzeQuery(query) {
    return postRequest("/api/queries/analyze", {
      query,
    });
  },

  // SQL QUERY OPTIMIZATION
  async optimizeQuery(query) {
    return postRequest("/api/queries/optimize", {
      query,
    });
  },

  // EXECUTION PLAN AND INDEX ANALYSIS
  async explainQuery(query, connectionId) {
    return postRequest("/api/queries/explain", {
      query,
      connection_id: connectionId,
    });
  },

  // PERFORMANCE COMPARISON
  async compareQueries({
    originalQuery,
    optimizedQuery,
    connectionId,
    iterations = 5,
    warmupRuns = 1,
  }) {
    return postRequest("/api/queries/compare", {
      original_query: originalQuery,
      optimized_query: optimizedQuery,
      connection_id: connectionId,
      iterations,
      warmup_runs: warmupRuns,
    });
  },

  // QUERY HISTORY
  async getQueryHistory({
    page = 1,
    perPage = 20,
    queryType = "",
    executionStatus = "",
  } = {}) {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });

    if (queryType) {
      params.set("query_type", queryType);
    }

    if (executionStatus) {
      params.set("execution_status", executionStatus);
    }

    return getRequest(`/api/history?${params.toString()}`);
  },

  // DATABASE SECURITY ANALYSIS
  async analyzeSecurity({
    connectionId,
    query = "",
    tableNames = [],
  }) {
    const body = {
      connection_id: connectionId,
    };

    if (query.trim()) {
      body.query = query.trim();
    }

    if (tableNames.length) {
      body.table_names = tableNames;
    }

    return postRequest("/api/security/analyze", body);
  },
};
