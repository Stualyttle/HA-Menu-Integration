/**
 * Thin client for the add-on HTTP API (docs/API.md).
 *
 * Paths are relative ("api/...") so the panel works under any Ingress base path.
 * Errors from the server ({error: {code, message, details}}) and network failures
 * are normalised into ApiError so callers can branch on `code`.
 * The 401 handler (addon/app/main.py) answers {detail: "..."} instead; both shapes
 * are accepted. Every operation below maps to an implemented route in docs/API.md.
 */

export class ApiError extends Error {
  /**
   * @param {number} status HTTP status, or 0 for network failures.
   * @param {string} code Server error code, or a client-side code.
   * @param {string} message Human-readable text (English, from the server).
   * @param {object} [details]
   */
  constructor(status, code, message, details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Drop undefined, null and empty-string values from a query object. */
function buildQuery(query) {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.append(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

/**
 * Normalise an error response. Accepts the add-on envelope
 * ({error: {code, message, details}}) and the 401 shape ({detail: string}).
 */
function toApiError(status, payload) {
  if (payload && typeof payload === 'object') {
    const error = payload.error;
    if (error && typeof error === 'object') {
      return new ApiError(status, error.code ?? `http_${status}`, error.message ?? '', error.details ?? {});
    }
    if (typeof payload.detail === 'string') {
      return new ApiError(status, `http_${status}`, payload.detail);
    }
  }
  return new ApiError(status, `http_${status}`, typeof payload === 'string' ? payload : '');
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * @param {object} [options]
 * @param {string} [options.baseUrl='api'] Relative base, without trailing slash.
 * @param {typeof fetch} [options.fetchImpl] Injectable for tests.
 */
export function createApiClient({ baseUrl = 'api', fetchImpl = globalThis.fetch } = {}) {
  async function request(method, path, { query, body } = {}) {
    const url = `${baseUrl}${path}${buildQuery(query)}`;
    const init = { method, headers: { Accept: 'application/json' } };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetchImpl(url, init);
    } catch (err) {
      throw new ApiError(0, 'network_error', err?.message ?? 'Network error');
    }

    const payload = await parseBody(response);
    if (!response.ok) {
      throw toApiError(response.status, payload);
    }
    return payload;
  }

  const get = (path, query) => request('GET', path, { query });
  const post = (path, body) => request('POST', path, { body });
  const put = (path, body) => request('PUT', path, { body });
  const del = (path) => request('DELETE', path);
  const id = (value) => encodeURIComponent(String(value));

  return {
    request,
    health: () => get('/health'),
    sync: (payload) => post('/sync', payload),

    menu: {
      list: (from, to) => get('/menu', { from, to }),
      today: () => get('/menu/today'),
      update: (date, payload) => put(`/menu/${id(date)}`, payload),
      eaten: (date) => post(`/menu/${id(date)}/eaten`),
      swapSuggestions: (date) => get(`/menu/${id(date)}/swap`),
      swap: (date, itemIds) => post(`/menu/${id(date)}/swap`, { item_ids: itemIds }),
      replan: () => post('/menu/replan'),
    },

    items: {
      list: (filters) => get('/items', filters),
      get: (itemId) => get(`/items/${id(itemId)}`),
      create: (payload) => post('/items', payload),
      update: (itemId, payload) => put(`/items/${id(itemId)}`, payload),
      remove: (itemId) => del(`/items/${id(itemId)}`),
      lookupNutrition: (itemId) => get(`/items/${id(itemId)}/nutrition/lookup`),
      setNutrition: (itemId, payload) => put(`/items/${id(itemId)}/nutrition`, payload),
    },

    categories: {
      list: () => get('/categories'),
      get: (categoryId) => get(`/categories/${id(categoryId)}`),
      create: (payload) => post('/categories', payload),
      update: (categoryId, payload) => put(`/categories/${id(categoryId)}`, payload),
      remove: (categoryId) => del(`/categories/${id(categoryId)}`),
    },

    rules: {
      list: () => get('/rules'),
      create: (payload) => post('/rules', payload),
      update: (ruleId, payload) => put(`/rules/${id(ruleId)}`, payload),
      remove: (ruleId) => del(`/rules/${id(ruleId)}`),
      check: (rule, ruleId) =>
        post('/rules/check', { rule, ...(ruleId === undefined ? {} : { rule_id: ruleId }) }),
    },

    stock: {
      list: (unansweredFirst = true) => get('/stock', { unanswered_first: String(unansweredFirst) }),
      set: (itemId, inStock) => put(`/stock/${id(itemId)}`, { in_stock: inStock }),
      preview: (itemId, inStock) => post(`/stock/${id(itemId)}/preview`, { in_stock: inStock }),
    },

    settings: {
      get: () => get('/settings'),
      update: (payload) => put('/settings', payload),
      retryLookups: () => post('/items/nutrition/retry'),
    },

    template: {
      get: () => get('/template'),
      update: (payload) => put('/template', payload),
    },

    exportData: () => get('/export'),
    importPreview: (payload) => post('/import/preview', payload),
    importData: (document, options = {}) => post('/import', { document, ...options }),

    warnings: {
      list: () => get('/warnings'),
      resolve: (warningId) => post(`/warnings/${id(warningId)}/resolve`),
    },
  };
}
