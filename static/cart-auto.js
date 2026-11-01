'use strict';
// Serialize session-cookie writes and coalesce rapid edits to the same item.
// All amounts, promotions and stock limits come back from the server.
(() => {
  const pending = new Map();
  let busy = false, timer, latestPage, lastProduct = '';
  const forms = () => document.querySelectorAll('[data-cart-auto-update]');
  const editing = () => busy || pending.size > 0;
  function status(message) {
    const region = document.querySelector('[data-cart-status]');
    if (region) region.textContent = message;
    document.querySelector('#main')?.setAttribute('aria-busy', String(editing()));
  }
  function enhance() {
    forms().forEach(form => {
      form.querySelector('[data-cart-manual-update]')?.setAttribute('hidden', '');
    });
  }
  function queue(form, submitter) {
    const input = form.querySelector('input[name="quantity"]');
    const remove = submitter?.hasAttribute('formaction');
    if (!remove && (input.value === '' || !input.checkValidity())) {
      status('Enter a whole-number quantity from 0 to 99.');
      return;
    }
    const action = new URL(remove ? submitter.formAction : form.action, location.href);
    if (action.origin !== location.origin || !/^\/cart\/(update|remove)\/[0-9]+$/.test(action.pathname)) return;
    pending.set(form.dataset.cartProduct, {action: action.href, body: new URLSearchParams(new FormData(form))});
    lastProduct = form.dataset.cartProduct;
    clearTimeout(timer);
    status('Updating your cart…');
    timer = setTimeout(flush, 250);
  }
  async function flush() {
    clearTimeout(timer);
    if (busy || !pending.size) return;
    busy = true;
    status('Updating your cart…');
    try {
      while (pending.size) {
        const [key, change] = pending.entries().next().value;
        pending.delete(key);
        const response = await fetch(change.action, {
          method: 'POST', body: change.body, credentials: 'same-origin',
          headers: {'Accept': 'text/html'}, redirect: 'follow'
        });
        if (!response.ok || new URL(response.url).pathname !== '/cart') throw new Error('Cart refresh failed');
        latestPage = new DOMParser().parseFromString(await response.text(), 'text/html');
        if (!latestPage.querySelector('#main') || !latestPage.querySelector('.cart-link')) throw new Error('Cart response incomplete');
      }
      // Apply only the final response, after all pending quantity changes settle.
      const main = document.querySelector('#main');
      main.replaceChildren(...Array.from(latestPage.querySelector('#main').childNodes).map(node => document.importNode(node, true)));
      const badge = document.querySelector('.cart-link');
      const freshBadge = latestPage.querySelector('.cart-link');
      badge.replaceChildren(...Array.from(freshBadge.childNodes).map(node => document.importNode(node, true)));
      badge.setAttribute('aria-label', freshBadge.getAttribute('aria-label'));
      enhance();
      if (/^[0-9]+$/.test(lastProduct)) {
        const input = document.querySelector(`[data-cart-product="${lastProduct}"] input[name="quantity"]`);
        input?.focus({preventScroll:true});
      }
      busy = false;
      status('Cart updated.');
    } catch (error) {
      // Never replay a mutation after an uncertain network outcome. A GET
      // recovers the server's actual session state and fresh CSRF controls.
      pending.clear();
      status('Refreshing your cart. Please check your quantities.');
      location.assign('/cart');
    }
  }
  // Capture cart +/- before the shared quantity handler, including refreshed rows.
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-qty-delta]');
    const form = button?.closest('[data-cart-auto-update]');
    if (form) {
      event.preventDefault(); event.stopImmediatePropagation();
      const input = form.querySelector('input[name="quantity"]');
      const next = Number(input.value || 0) + Number(button.dataset.qtyDelta);
      input.value = String(Math.max(Number(input.min || 0), Math.min(Number(input.max || 99), next)));
      queue(form);
      return;
    }
    if (editing() && event.target.closest('#main a')) {
      event.preventDefault(); status('Updating your cart… Please wait before continuing.');
      return;
    }
    if (event.target.closest('[data-cart-payment-jump]')) {
      const choices = document.getElementById('cart-payment-options');
      if (choices) {
        event.preventDefault();
        choices.focus({preventScroll:true});
        const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        choices.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block:'start'});
      }
    }
  }, true);
  document.addEventListener('input', event => {
    const form = event.target.closest('[data-cart-auto-update]');
    if (form && event.target.name === 'quantity') queue(form);
  });
  document.addEventListener('change', event => {
    const form = event.target.closest('[data-cart-auto-update]');
    if (form && event.target.name === 'quantity') queue(form);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-cart-auto-update]');
    if (form) {
      event.preventDefault();
      queue(form, event.submitter);
      flush();
    } else if (editing() && event.target.closest('#main')) {
      event.preventDefault(); status('Updating your cart… Please wait before continuing.');
      return;
    }
    if (event.target.closest('[data-cart-payment-jump]')) {
      const choices = document.getElementById('cart-payment-options');
      if (choices) {
        event.preventDefault();
        choices.focus({preventScroll:true});
        const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        choices.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block:'start'});
      }
    }
  });
  enhance();
})();
