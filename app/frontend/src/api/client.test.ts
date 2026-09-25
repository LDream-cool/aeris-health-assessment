import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, APIError } from './client';
import { addedCart, emptyCart, product } from '../test/fixtures';

afterEach(() => vi.unstubAllGlobals());

describe('API client', () => {
  it('loads product and cart through the expected endpoints', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(product)))
      .mockResolvedValueOnce(new Response(JSON.stringify(emptyCart)));
    vi.stubGlobal('fetch', fetchMock);
    expect(await api.getProduct('everyday-tee')).toEqual(product);
    expect(await api.getCart()).toEqual(emptyCart);
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual(['/api/products/everyday-tee', '/api/cart']);
  });

  it('sends only SKU and quantity with the provided idempotency key', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(addedCart)));
    vi.stubGlobal('fetch', fetchMock);
    const payload = { sku_id: 'tee-blue-s', quantity: 1 };
    expect(await api.addCartItem(payload, 'stable-key')).toEqual(addedCart);
    expect(fetchMock).toHaveBeenCalledWith('/api/cart/items', expect.objectContaining({
      method: 'POST', body: JSON.stringify(payload),
      headers: expect.objectContaining({ 'Idempotency-Key': 'stable-key', 'Content-Type': 'application/json' }),
    }));
  });

  it('preserves structured errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'INSUFFICIENT_STOCK', message: 'Stock changed.' },
    }), { status: 409 })));
    await expect(api.addCartItem({ sku_id: 'tee-blue-s', quantity: 6 }, 'key'))
      .rejects.toMatchObject({ status: 409, code: 'INSUFFICIENT_STOCK', message: 'Stock changed.', uncertain: false });
  });

  it('normalises network and non-JSON server failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network disconnected')));
    await expect(api.getCart()).rejects.toMatchObject({ code: 'NETWORK_ERROR', uncertain: true });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('internal details', { status: 500 })));
    await expect(api.getCart()).rejects.toBeInstanceOf(APIError);
    await expect(api.getCart()).rejects.toMatchObject({ message: 'The request could not be completed.', uncertain: true });
  });
});
