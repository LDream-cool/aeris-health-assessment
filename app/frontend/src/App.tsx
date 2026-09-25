import { useEffect, useState } from 'react';
import { api } from './api/client';
import type { Cart, Product } from './models';
import { ProductPage } from './components/ProductPage';

type LoadState = { kind: 'loading' } | { kind: 'error' }
  | { kind: 'ready'; product: Product; cart: Cart };

export default function App() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: 'loading' });
    Promise.all([
      api.getProduct('everyday-tee', controller.signal), api.getCart(controller.signal),
    ]).then(([product, cart]) => {
      if (!controller.signal.aborted) setState({ kind: 'ready', product, cart });
    }).catch(() => {
      if (!controller.signal.aborted) setState({ kind: 'error' });
    });
    return () => controller.abort();
  }, [attempt]);

  if (state.kind === 'ready') return <ProductPage initialProduct={state.product} initialCart={state.cart} />;

  return <main className="loading-shell">
    <a className="wordmark" href="/">AERIS<span>EVERYDAY ESSENTIALS</span></a>
    {state.kind === 'loading'
      ? <p role="status">Loading product and cart…</p>
      : <div role="alert"><h1>Something went wrong</h1>
        <p>We couldn’t load the product and cart. Please try again.</p>
        <button className="primary" onClick={() => setAttempt((value) => value + 1)}>Retry</button>
      </div>}
  </main>;
}
