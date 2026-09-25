import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { api, APIError } from '../api/client';
import type { Cart } from '../models';
import { addedCart, emptyCart, product } from './fixtures';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return { ...actual, api: { getProduct: vi.fn(), getCart: vi.fn(), addCartItem: vi.fn() } };
});

beforeEach(() => {
  vi.mocked(api.getProduct).mockReset().mockResolvedValue(structuredClone(product));
  vi.mocked(api.getCart).mockReset().mockResolvedValue(structuredClone(emptyCart));
  vi.mocked(api.addCartItem).mockReset().mockResolvedValue(structuredClone(addedCart));
});

async function load() {
  render(<App />);
  await screen.findByRole('heading', { name: product.name });
  return userEvent.setup();
}

async function chooseBlueSmall(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText('Colour'), 'blue');
  await user.selectOptions(screen.getByLabelText('Size'), 'S');
}

it('shows initial loading, then an incomplete selection and current cart count', async () => {
  render(<App />);
  expect(screen.getByText('Loading product and cart…')).toBeInTheDocument();
  await screen.findByRole('heading', { name: product.name });
  expect(screen.getByText('Choose a colour and size.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
  expect(screen.getByLabelText('Cart: 0 items')).toBeInTheDocument();
});

it('retries an initial failure without reloading the browser', async () => {
  vi.mocked(api.getProduct).mockRejectedValueOnce(new Error('offline'));
  render(<App />);
  const retry = await screen.findByRole('button', { name: 'Retry' });
  await userEvent.click(retry);
  await screen.findByRole('heading', { name: product.name });
  expect(api.getProduct).toHaveBeenCalledTimes(2);
});

it('disables impossible options while keeping sold-out SKUs selectable', async () => {
  const user = await load();
  await user.selectOptions(screen.getByLabelText('Colour'), 'sand');
  expect(screen.getByRole('option', { name: 'L — unavailable' })).toBeDisabled();
  await user.selectOptions(screen.getByLabelText('Colour'), 'blue');
  expect(screen.getByRole('option', { name: 'M' })).toBeEnabled();
  await user.selectOptions(screen.getByLabelText('Size'), 'M');
  expect(screen.getByText('Out of stock')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
  expect(screen.getByLabelText('Quantity')).toBeDisabled();
});

it('updates image, price and stock and clamps quantity on variant change', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  const quantity = screen.getByLabelText('Quantity');
  await user.clear(quantity);
  await user.type(quantity, '5');
  await user.selectOptions(screen.getByLabelText('Colour'), 'black');
  expect(quantity).toHaveValue(2);
  expect(screen.getByText('$26.00')).toBeInTheDocument();
  expect(screen.queryByText('$25.00')).not.toBeInTheDocument();
  expect(screen.getByText('2 available')).toBeInTheDocument();
  expect(screen.getByRole('img')).toHaveAttribute('src', '/static/tee-black.svg');
  await user.selectOptions(screen.getByLabelText('Size'), 'L');
  expect(quantity).toHaveValue(1);
  expect(screen.getByText('$28.00')).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Size'), '');
  expect(screen.queryByText('$28.00')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
});

it.each(['', '0', '-1', '1.5', '6'])('disables adding invalid quantity %s', async (value) => {
  const user = await load();
  await chooseBlueSmall(user);
  fireEvent.change(screen.getByLabelText('Quantity'), { target: { value } });
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
  expect(screen.getByLabelText('Quantity')).toHaveAttribute('aria-invalid', 'true');
});

it('guards duplicate clicks, then displays successful cart and stock updates', async () => {
  let complete: (cart: Cart) => void = () => { throw new Error('Not ready'); };
  vi.mocked(api.addCartItem).mockImplementation(() => new Promise<Cart>((resolve) => { complete = resolve; }));
  const user = await load();
  await chooseBlueSmall(user);
  const button = screen.getByRole('button', { name: 'Add to cart' });
  await user.dblClick(button);
  expect(api.addCartItem).toHaveBeenCalledTimes(1);
  expect(button).toBeDisabled();
  expect(screen.getByLabelText('Colour')).toBeDisabled();
  const updated = structuredClone(product);
  const sku = updated.skus.find((item) => item.sku_id === 'tee-blue-s');
  if (sku) sku.stock = 4;
  vi.mocked(api.getProduct).mockResolvedValue(updated);
  vi.mocked(api.getCart).mockResolvedValue(addedCart);
  await act(async () => complete(addedCart));
  expect(await screen.findByText('Added to your cart.')).toBeInTheDocument();
  await waitFor(() => expect(button).toBeEnabled());
  expect(screen.getByLabelText('Cart: 1 items')).toBeInTheDocument();
  expect(screen.getByText('4 available')).toBeInTheDocument();
});

it('reuses the original key and payload after an ambiguous network failure', async () => {
  vi.mocked(api.addCartItem).mockRejectedValueOnce(new APIError(0, 'NETWORK_ERROR', 'offline'));
  const user = await load();
  await chooseBlueSmall(user);
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  const retry = await screen.findByRole('button', { name: 'Retry add to cart' });
  expect(screen.getByLabelText('Colour')).toBeDisabled();
  await user.click(retry);
  await screen.findByText('Added to your cart.');
  expect(api.addCartItem).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.addCartItem).mock.calls[0]).toEqual(vi.mocked(api.addCartItem).mock.calls[1]);
});

it('refreshes authoritative stock after a stock rejection', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  const updated = structuredClone(product);
  const sku = updated.skus.find((item) => item.sku_id === 'tee-blue-s');
  if (sku) sku.stock = 0;
  vi.mocked(api.getProduct).mockResolvedValue(updated);
  vi.mocked(api.addCartItem).mockRejectedValueOnce(new APIError(409, 'INSUFFICIENT_STOCK', 'Requested quantity exceeds current stock.'));
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Requested quantity exceeds current stock.');
  expect(screen.getByText('Out of stock')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
});

it('shows unavailable rather than sold out if the selected SKU disappears on refresh', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  vi.mocked(api.getProduct).mockResolvedValue({
    ...product, skus: product.skus.filter((sku) => sku.sku_id !== 'tee-blue-s'),
  });
  vi.mocked(api.addCartItem).mockRejectedValueOnce(new APIError(404, 'SKU_NOT_FOUND', 'SKU not found.'));
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  expect(await screen.findByText('This combination is unavailable.')).toBeInTheDocument();
  expect(screen.queryByText('Out of stock')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
});

it('allows refresh recovery after a successful add without submitting again', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  vi.mocked(api.getProduct).mockRejectedValueOnce(new Error('offline'));
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  const refresh = await screen.findByRole('button', { name: 'Refresh availability' });
  expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
  await user.click(refresh);
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Refresh availability' })).not.toBeInTheDocument());
  expect(api.addCartItem).toHaveBeenCalledTimes(1);
});

it('announces server validation failures and allows a corrected operation', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  vi.mocked(api.addCartItem).mockRejectedValueOnce(new APIError(422, 'INVALID_QUANTITY', 'Quantity must be a positive integer.'));
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Quantity must be a positive integer.');
  expect(screen.getByLabelText('Quantity')).toBeEnabled();
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  await screen.findByText('Added to your cart.');
  const calls = vi.mocked(api.addCartItem).mock.calls;
  expect(calls[0]?.[1]).not.toBe(calls[1]?.[1]);
});

it('retries a server failure with the same key without changing the operation', async () => {
  const user = await load();
  await chooseBlueSmall(user);
  vi.mocked(api.addCartItem).mockRejectedValueOnce(new APIError(500, 'INTERNAL_ERROR', 'An unexpected server error occurred.'));
  await user.click(screen.getByRole('button', { name: 'Add to cart' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Retry safely with the same request.');
  expect(screen.getByLabelText('Quantity')).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Retry add to cart' }));
  await screen.findByText('Added to your cart.');
  const calls = vi.mocked(api.addCartItem).mock.calls;
  expect(calls[0]).toEqual(calls[1]);
});

it('provides labelled controls in keyboard order and supports keyboard submission', async () => {
  const user = await load();
  await user.tab();
  expect(screen.getByRole('link', { name: 'Skip to product' })).toHaveFocus();
  await user.tab();
  await user.tab();
  expect(screen.getByLabelText('Colour')).toHaveFocus();
  await user.selectOptions(screen.getByLabelText('Colour'), 'blue');
  await user.tab();
  expect(screen.getByLabelText('Size')).toHaveFocus();
  await user.selectOptions(screen.getByLabelText('Size'), 'S');
  await user.tab();
  expect(screen.getByLabelText('Quantity')).toHaveFocus();
  await user.tab();
  expect(screen.getByRole('button', { name: 'Add to cart' })).toHaveFocus();
  await user.keyboard('{Enter}');
  await screen.findByText('Added to your cart.');
  expect(api.addCartItem).toHaveBeenCalledTimes(1);
});
