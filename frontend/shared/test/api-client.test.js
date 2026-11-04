import { describe, it, expect, vi } from 'vitest';
import { ApiError, createApiClient } from '../api/client.js';

function jsonResponse(status, body) {
  const text = body === undefined ? '' : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
  };
}

describe('createApiClient', () => {
  it('builds relative URLs under the default base and drops empty query values', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, []));
    const api = createApiClient({ fetchImpl });

    await api.items.list({ type: 'protein', q: '', category_id: null, verified: undefined });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('api/items?type=protein');
    expect(init.method).toBe('GET');
    expect(init.headers.Accept).toBe('application/json');
    expect(init.body).toBeUndefined();
  });

  it('omits the query string when every value is empty', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, []));
    await createApiClient({ fetchImpl }).items.list({ q: '' });
    expect(fetchImpl.mock.calls[0][0]).toBe('api/items');
  });

  it('sends JSON bodies with a Content-Type header on writes', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(201, { id: 7 }));
    const api = createApiClient({ fetchImpl });

    const result = await api.items.create({ name: 'Salmon' });

    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe('api/items');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ name: 'Salmon' });
    expect(result).toEqual({ id: 7 });
  });

  it('encodes path segments such as dates and ids', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const api = createApiClient({ fetchImpl });

    await api.menu.eaten('2026-11-04');
    await api.stock.set('a/b', false);

    expect(fetchImpl.mock.calls[0][0]).toBe('api/menu/2026-11-04/eaten');
    expect(fetchImpl.mock.calls[1][0]).toBe('api/stock/a%2Fb');
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toEqual({ in_stock: false });
  });

  it('maps the server error envelope to ApiError with code and details', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(422, {
        error: { code: 'infeasible', message: 'Rule makes minimum impossible', details: { days: 3 } },
      }),
    );
    const api = createApiClient({ fetchImpl });

    const error = await api.rules.create({}).catch((err) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe('infeasible');
    expect(error.message).toBe('Rule makes minimum impossible');
    expect(error.details).toEqual({ days: 3 });
  });

  it('falls back to an http_<status> code when the body is not the error envelope', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(500, undefined));
    const error = await createApiClient({ fetchImpl }).health().catch((err) => err);

    expect(error.status).toBe(500);
    expect(error.code).toBe('http_500');
  });

  it('turns network failures into a network_error with status 0', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    const error = await createApiClient({ fetchImpl }).health().catch((err) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.code).toBe('network_error');
  });

  it('returns null for an empty successful body', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(204, undefined));
    const result = await createApiClient({ fetchImpl }).items.remove(3);
    expect(result).toBeNull();
    expect(fetchImpl.mock.calls[0][0]).toBe('api/items/3');
    expect(fetchImpl.mock.calls[0][1].method).toBe('DELETE');
  });

  it('sends stock queries with unanswered_first by default', async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, []));
    await createApiClient({ fetchImpl }).stock.list();
    expect(fetchImpl.mock.calls[0][0]).toBe('api/stock?unanswered_first=true');
  });
});
