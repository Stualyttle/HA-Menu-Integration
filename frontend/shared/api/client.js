/**
 * Thin client for the add-on HTTP API (docs/API.md).
 *
 * Paths are relative ("api/...") so the panel works under any Ingress base path.
 * Errors from the server ({error: {code, message, details}}) and network failures
 * are normalised into ApiError so callers can branch on `code`.
 * The 401 handler (addon/app/main.py) answers {detail: "..."} instead; both shapes
 * are accepted. Routes marked "Planned" in docs/API.md are called but may 404 until
 * they land; calls marked TODO(API) use request bodies the contract does not define yet.
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

/** Client-side rejection for routes that docs/API.md does not define. No request is sent. */
function notInContract(name) {
  return Promise.reject(new ApiError(501, 'not_implemented', `${name} is not in docs/API.md`));
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
    // Planned (API.md). TODO(API): request body not defined in the contract.
    sync: (payload) => post('/sync', payload),

    menu: {
      // Planned (API.md): GET /api/menu?from=&to= returns a bare array.
      list: (from, to) => get('/menu', { from, to }),
      // Planned (API.md): GET /api/menu/today.
      today: () => get('/menu/today'),
      // Planned (API.md): PUT /api/menu/{date}. TODO(API): body (pin, unpin, set dinner) not defined in the contract.
      update: (date, payload) => put(`/menu/${id(date)}`, payload),
      // Planned (API.md): POST /api/menu/{date}/eaten.
      eaten: (date) => post(`/menu/${id(date)}/eaten`),
      // Planned (API.md): GET /api/menu/{date}/swap.
      swapSuggestions: (date) => get(`/menu/${id(date)}/swap`),
      // Planned (API.md): POST /api/menu/{date}/swap with {dinner_id}.
      swap: (date, dinnerId) => post(`/menu/${id(date)}/swap`, { dinner_id: dinnerId }),
      // Not in docs/API.md. Stubbed: no network call. TODO(API): confirm whether the route exists.
      replan: () => notInContract('menu.replan'),
    },

    items: {
      list: (filters) => get('/items', filters),
      get: (itemId) => get(`/items/${id(itemId)}`),
      create: (payload) => post('/items', payload),
      update: (itemId, payload) => put(`/items/${id(itemId)}`, payload),
      remove: (itemId) => del(`/items/${id(itemId)}`),
      // Planned (API.md): POST /api/items/{id}/nutrition/lookup.
      lookupNutrition: (itemId) => post(`/items/${id(itemId)}/nutrition/lookup`),
      // Planned (API.md): PUT /api/items/{id}/nutrition. TODO(API): body shape not defined in the contract.
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
      // Planned (API.md): POST /api/rules/check. TODO(API): body not defined in the contract.
      check: (payload) => post('/rules/check', payload),
    },

    stock: {
      list: (unansweredFirst = true) => get('/stock', { unanswered_first: String(unansweredFirst) }),
      set: (itemId, inStock) => put(`/stock/${id(itemId)}`, { in_stock: inStock }),
      preview: (itemId, inStock) => post(`/stock/${id(itemId)}/preview`, { in_stock: inStock }),
    },

    settings: {
      get: () => get('/settings'),
      update: (payload) => put('/settings', payload),
      // Not in docs/API.md. Stubbed: no network call. TODO(API): confirm whether the route exists.
      retryLookups: () => notInContract('settings.retryLookups'),
    },

    template: {
      get: () => get('/template'),
      update: (payload) => put('/template', payload),
    },

    // Planned (API.md): GET /api/export. TODO(API): the response is a file download; it is parsed as JSON here.
    exportData: () => get('/export'),
    // Planned (API.md): POST /api/import/preview. TODO(API): body not defined in the contract.
    importPreview: (payload) => post('/import/preview', payload),
    // Planned (API.md): POST /api/import. TODO(API): body (include_settings, include_history) not fully defined in the contract.
    importData: (payload) => post('/import', payload),

    warnings: {
      list: () => get('/warnings'),
      resolve: (warningId) => post(`/warnings/${id(warningId)}/resolve`),
    },
  };
}
