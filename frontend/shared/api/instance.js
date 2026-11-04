import { createApiClient } from './client.js';

/** Shared API client for every panel view. Relative paths keep Ingress working. */
export const api = createApiClient();
