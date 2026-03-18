const API = (() => {
  const DEFAULT_BASE = 'http://localhost:8000';

  async function getConfig() {
    const { apiConfig = {} } = await chrome.storage.local.get('apiConfig');
    return {
      baseUrl: apiConfig.baseUrl || DEFAULT_BASE,
      token: apiConfig.token || null,
    };
  }

  async function saveConfig(config) {
    const { apiConfig = {} } = await chrome.storage.local.get('apiConfig');
    await chrome.storage.local.set({ apiConfig: { ...apiConfig, ...config } });
  }

  async function request(path, options = {}) {
    const config = await getConfig();
    if (!config.token) throw new Error('Not authenticated');

    const url = `${config.baseUrl}${path}`;
    const headers = {
      Authorization: `Bearer ${config.token}`,
      ...options.headers,
    };

    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
      await saveConfig({ token: null });
      throw new Error('Session expired. Please log in again.');
    }

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || 'Request failed');
    }

    if (response.status === 204) return null;
    return response.json();
  }

  return {
    getConfig,
    saveConfig,

    async isAuthenticated() {
      const config = await getConfig();
      return !!config.token;
    },

    async register(email, password) {
      const config = await getConfig();
      const res = await fetch(`${config.baseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Registration failed');
      }
      return res.json();
    },

    async login(email, password) {
      const config = await getConfig();
      const body = new URLSearchParams({ username: email, password });
      const res = await fetch(`${config.baseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Login failed');
      }
      const data = await res.json();
      await saveConfig({ token: data.access_token });
      return data;
    },

    async logout() {
      await saveConfig({ token: null });
    },

    async listJobs(params = {}) {
      const query = new URLSearchParams();
      if (params.status) query.set('status', params.status);
      if (params.tag) query.set('tag', params.tag);
      if (params.search) query.set('search', params.search);
      const qs = query.toString();
      return request(`/jobs${qs ? '?' + qs : ''}`);
    },

    async createJob(job) {
      return request('/jobs', {
        method: 'POST',
        body: JSON.stringify(job),
      });
    },

    async getJob(id) {
      return request(`/jobs/${id}`);
    },

    async updateJob(id, data) {
      return request(`/jobs/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },

    async deleteJob(id) {
      return request(`/jobs/${id}`, { method: 'DELETE' });
    },

    async exportCSV() {
      const config = await getConfig();
      const res = await fetch(`${config.baseUrl}/jobs/export/csv`, {
        headers: { Authorization: `Bearer ${config.token}` },
      });
      if (!res.ok) throw new Error('Export failed');
      return res.blob();
    },

    async importFile(file) {
      const formData = new FormData();
      formData.append('file', file);
      return request('/jobs/import', {
        method: 'POST',
        body: formData,
      });
    },
  };
})();
