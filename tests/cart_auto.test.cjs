// DOM-level unit checks; no browser, live site or payment provider is contacted.
// npm install --prefix /tmp/cart40-dom linkedom (development dependency only)
const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const {parseHTML,DOMParser}=require(process.env.CART_TEST_DOM || 'linkedom');
const source=fs.readFileSync(path.join(__dirname,'../static/cart-auto.js'),'utf8');
function html(q=1) {
  return `<html><body><a class="cart-link" aria-label="Your cart, ${q} items"><span>${q}</span></a><main id="main"><p data-cart-status></p>${q ? `<form data-cart-auto-update data-cart-product="1" action="/cart/update/1"><input name="csrf_token" value="csrf"><button type="button" data-qty-delta="-1">−</button><input type="number" name="quantity" value="${q}" min="0" max="99"><button type="button" data-qty-delta="1">+</button><button data-cart-manual-update>Update</button><button formaction="/cart/remove/1">Remove</button></form><b data-total>${q*200}</b>` : '<h2>Your cart is empty</h2>'}</main></body></html>`;
}
function harness(fetcher) {
  const {window,document}=parseHTML(html());let seq=0;const timers=new Map(),nav=[],calls=[];
  Object.defineProperty(window.HTMLElement.prototype,'action',{configurable:true,get(){return new URL(this.getAttribute('action'),'http://shop.test').href;}});
  Object.defineProperty(window.HTMLElement.prototype,'formAction',{configurable:true,get(){return new URL(this.getAttribute('formaction'),'http://shop.test').href;}});
  window.HTMLElement.prototype.checkValidity=function(){return /^\d+$/.test(this.value) && Number(this.value)<=99;};
  window.HTMLElement.prototype.focus=function(){};
  const fetch=async (url,options)=>{calls.push({url,q:options.body.get('quantity')});return fetcher(url,options);};
  const ctx={document,DOMParser,URL,URLSearchParams,FormData:class{constructor(form){this.entries=Array.from(form.querySelectorAll('input')).map(i=>[i.name,i.value]);}[Symbol.iterator](){return this.entries[Symbol.iterator]();}},location:{href:'http://shop.test/cart',origin:'http://shop.test',assign:url=>nav.push(url)},fetch,setTimeout:fn=>{timers.set(++seq,fn);return seq;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source,ctx);
  return {document,calls,nav,clickPlus(){document.querySelector('[data-qty-delta="1"]').dispatchEvent(new window.Event('click',{bubbles:true,cancelable:true}));},submitRemove(){const event=new window.Event('submit',{bubbles:true,cancelable:true});event.submitter=document.querySelector('[formaction]');document.querySelector('form').dispatchEvent(event);},run(){const fn=Array.from(timers.values()).at(-1);timers.clear();return fn?.();}};
}
function response(q){return {ok:true,url:'http://shop.test/cart',text:async()=>html(q)};}
test('rapid changes are coalesced and session mutations are serialized',async()=>{
  let release;let count=0;
  const h=harness(async(url,options)=>{if(++count===1)return new Promise(resolve=>release=()=>resolve(response(Number(options.body.get('quantity')))));return response(Number(options.body.get('quantity')));});
  assert.ok(h.document.querySelector('[data-cart-manual-update]').hasAttribute('hidden'));
  h.clickPlus();const saving=h.run();h.clickPlus();h.clickPlus();
  assert.equal(h.calls.length,1);
  release();await saving;
  assert.deepEqual(h.calls.map(c=>c.q),['2','4']);
  assert.equal(h.document.querySelector('[data-total]').textContent,'800');
  assert.equal(h.document.querySelector('.cart-link span').textContent,'4');
  assert.equal(h.document.querySelector('[data-cart-status]').textContent,'Cart updated.');
  assert.deepEqual(h.nav,[]);
  // Refreshed controls keep working without rebinding the shared shop script.
  h.clickPlus();await h.run();assert.equal(h.calls.at(-1).q,'5');
});
test('Remove refreshes the empty cart and header badge',async()=>{
  const h=harness(async()=>response(0));h.submitRemove();
  // Submit starts the asynchronous flush immediately.
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(h.calls[0].url.endsWith('/cart/remove/1'));
  assert.equal(h.document.querySelector('.cart-link span').textContent,'0');
  assert.equal(h.document.querySelector('h2').textContent,'Your cart is empty');
});
test('uncertain network outcome recovers with GET instead of replaying a POST',async()=>{
  const h=harness(async()=>{throw new Error('connection lost');});
  h.clickPlus();await h.run();assert.equal(h.calls.length,1);assert.deepEqual(h.nav,['/cart']);
});
