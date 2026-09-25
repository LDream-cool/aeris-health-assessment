import { useEffect, useRef, useState } from 'react';
import { api, APIError } from '../api/client';
import { clampQuantity, dimensions, formatPrice, isOptionAvailable, resolveVariant, validQuantity } from '../domain/variants';
import type { AddCartItemRequest, Cart, Product, Selection } from '../models';

interface Props { initialProduct: Product; initialCart: Cart }
interface Operation { key: string; payload: AddCartItemRequest }

export function ProductPage({ initialProduct, initialCart }: Props) {
  const [product, setProduct] = useState(initialProduct);
  const [cart, setCart] = useState(initialCart);
  const [selection, setSelection] = useState<Selection>({});
  const [quantity, setQuantity] = useState('1');
  const [submitting, setSubmitting] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [feedback, setFeedback] = useState<{ text: string; error: boolean } | null>(null);
  const busy = useRef(false);
  const operation = useRef<Operation | null>(null);
  const variant = resolveVariant(product, selection);
  const sku = 'sku' in variant ? variant.sku : undefined;
  const purchasable = variant.kind === 'in-stock';
  const quantityValid = !!sku && validQuantity(Number(quantity), sku.stock);
  const editable = !submitting && !uncertain;

  useEffect(() => {
    setQuantity((current) => String(clampQuantity(Number(current), sku?.stock ?? 0)));
  }, [sku?.sku_id, sku?.stock]);

  async function refresh(): Promise<boolean> {
    try {
      const [latestProduct, latestCart] = await Promise.all([api.getProduct(product.id), api.getCart()]);
      setProduct(latestProduct);
      setCart(latestCart);
      setNeedsRefresh(false);
      return true;
    } catch {
      setNeedsRefresh(true);
      return false;
    }
  }

  async function addToCart() {
    if (busy.current || needsRefresh) return;
    if (!operation.current) {
      if (!purchasable || !sku || !quantityValid) return;
      operation.current = {
        key: crypto.randomUUID(), payload: { sku_id: sku.sku_id, quantity: Number(quantity) },
      };
    }
    busy.current = true;
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await api.addCartItem(operation.current.payload, operation.current.key);
      setCart(result);
      // Apply known server stock immediately, then refresh to avoid stale replay snapshots.
      setProduct((current) => ({ ...current, skus: current.skus.map((item) => {
        const updated = result.items.find((line) => line.sku_id === item.sku_id);
        return updated ? { ...item, stock: updated.stock } : item;
      }) }));
      operation.current = null;
      setUncertain(false);
      setFeedback({ text: 'Added to your cart.', error: false });
      await refresh();
    } catch (error) {
      const retrySameRequest = !(error instanceof APIError) || error.uncertain;
      setUncertain(retrySameRequest);
      if (!retrySameRequest) {
        operation.current = null;
        await refresh();
      }
      setFeedback({
        error: true,
        text: retrySameRequest
          ? 'We couldn’t confirm the result. Retry safely with the same request.'
          : error instanceof APIError ? error.message : 'Unable to add this item.',
      });
    } finally {
      busy.current = false;
      setSubmitting(false);
    }
  }

  async function refreshAvailability() {
    if (busy.current) return;
    busy.current = true;
    setSubmitting(true);
    await refresh();
    busy.current = false;
    setSubmitting(false);
  }

  const status = variant.kind === 'incomplete' ? 'Choose a colour and size.'
    : variant.kind === 'unavailable' ? 'This combination is unavailable.'
      : variant.kind === 'out-of-stock' ? 'Out of stock'
        : `${variant.sku.stock} available`;
  const image = sku?.image ?? product.skus[0]?.image;
  const minimumPrice = Math.min(...product.skus.map((item) => item.price_cents));

  return <>
    <a className="skip-link" href="#product">Skip to product</a>
    <header className="site-header">
      <a className="wordmark" href="/">AERIS<span>EVERYDAY ESSENTIALS</span></a>
      <div className="cart-badge" role="status" aria-label={`Cart: ${cart.total_item_count} items`}>
        Cart <span>{cart.total_item_count}</span>
      </div>
    </header>
    <main id="product" className="pdp">
      <section className="product-visual" aria-label="Product image">
        {image && <img src={image} alt={`${product.name}${sku ? ` in ${sku.option_values.colour}, size ${sku.option_values.size}` : ''}`} />}
        <p>YOUR EVERYDAY, A LITTLE MORE COMFORTABLE.</p>
      </section>
      <section className="product-details" aria-labelledby="product-name">
        <p className="eyebrow">THE EVERYDAY COLLECTION</p>
        <h1 id="product-name">{product.name}</h1>
        <p className="description">{product.description}</p>
        <p className="price" aria-live="polite">{sku
          ? formatPrice(sku.price_cents, product.currency)
          : `From ${formatPrice(minimumPrice, product.currency)}`}</p>
        <form onSubmit={(event) => { event.preventDefault(); void addToCart(); }}>
          <div className="selectors">
            {dimensions.map((dimension) => <div className="field" key={dimension}>
              <label htmlFor={dimension}>{dimension === 'colour' ? 'Colour' : 'Size'}</label>
              <select id={dimension} value={selection[dimension] ?? ''} disabled={!editable}
                onChange={(event) => {
                  setSelection((current) => ({ ...current, [dimension]: event.target.value || undefined }));
                  setFeedback(null);
                }}>
                <option value="">Select {dimension}</option>
                {product.options[dimension].map((value) => {
                  const available = isOptionAvailable(product, selection, dimension, value);
                  return <option key={value} value={value} disabled={!available}>
                    {value}{available ? '' : ' — unavailable'}
                  </option>;
                })}
              </select>
            </div>)}
          </div>
          <p className={`stock ${variant.kind === 'out-of-stock' ? 'sold-out' : ''}`} role="status">{status}</p>
          <div className="purchase-row">
            <div className="field quantity">
              <label htmlFor="quantity">Quantity</label>
              <input id="quantity" type="number" min="1" max={sku?.stock || 1} step="1"
                value={quantity} disabled={!editable || !purchasable}
                aria-invalid={purchasable && !quantityValid} aria-describedby="quantity-help"
                onChange={(event) => setQuantity(event.target.value)} />
            </div>
            <button className="primary add-button" type="submit"
              disabled={submitting || needsRefresh || (!uncertain && (!purchasable || !quantityValid))}>
              {submitting ? 'Please wait…' : uncertain ? 'Retry add to cart' : 'Add to cart'}
            </button>
          </div>
          <p id="quantity-help" className="helper">{purchasable && !quantityValid
            ? `Enter a whole number from 1 to ${sku?.stock}.`
            : 'Availability is confirmed when you add to cart.'}</p>
        </form>
        {feedback && <p className={`feedback ${feedback.error ? 'error' : 'success'}`}
          role={feedback.error ? 'alert' : 'status'}>{feedback.text}</p>}
        {needsRefresh && <div className="feedback error" role="alert">
          <p>We couldn’t refresh availability. Refresh before adding another item.</p>
          <button className="secondary" onClick={() => void refreshAvailability()} disabled={submitting}>Refresh availability</button>
        </div>}
        <div className="product-note"><strong>Made for the everyday.</strong><p>Soft cotton. A relaxed fit. Your choice of colour and size.</p></div>
      </section>
    </main>
    <footer>Simple essentials. Thoughtfully chosen.</footer>
  </>;
}
