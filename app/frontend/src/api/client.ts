import type {
  AddCartItemRequest, AddCartItemResponse, APIErrorResponse, CartResponse, ProductResponse,
} from '../models';

export class APIError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message);
    this.name = 'APIError';
  }

  get uncertain(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

function isErrorResponse(value: unknown): value is APIErrorResponse {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false;
  const error = value.error;
  return typeof error === 'object' && error !== null
    && 'code' in error && typeof error.code === 'string'
    && 'message' in error && typeof error.message === 'string';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(15_000);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  try {
    const response = await fetch(path, {
      ...init,
      signal,
      headers: { Accept: 'application/json', ...init.headers },
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      throw new APIError(response.status,
        isErrorResponse(body) ? body.error.code : 'HTTP_ERROR',
        isErrorResponse(body) ? body.error.message : 'The request could not be completed.');
    }
    if (body === null) throw new APIError(0, 'INVALID_RESPONSE', 'The server returned an unreadable response.');
    return body as T;
  } catch (error) {
    if (init.signal?.aborted) throw error;
    if (error instanceof APIError) throw error;
    throw new APIError(0, 'NETWORK_ERROR', 'Unable to reach the server. Please try again.');
  }
}

export const api = {
  getProduct: (id: string, signal?: AbortSignal) =>
    request<ProductResponse>(`/api/products/${encodeURIComponent(id)}`, { signal }),
  getCart: (signal?: AbortSignal) => request<CartResponse>('/api/cart', { signal }),
  addCartItem: (payload: AddCartItemRequest, key: string) =>
    request<AddCartItemResponse>('/api/cart/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
      body: JSON.stringify(payload),
    }),
};
