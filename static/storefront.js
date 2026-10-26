(()=>{
const dataEl=document.querySelector('#productData');if(!dataEl)return;
const products=JSON.parse(dataEl.textContent);const bag=new Map();let filter='all';let keyword='';let focusItem=0;const $=s=>document.querySelector(s);
function toast(message){const el=$('#storeToast');el.textContent=message;el.classList.add('show');clearTimeout(toast._t);toast._t=setTimeout(()=>el.classList.remove('show'),3200)}
function renderGrid(){let any=false;document.querySelectorAll('.shop-product').forEach(el=>{const ok=(filter==='all'||el.dataset.category===filter)&&el.dataset.name.includes(keyword);el.hidden=!ok;if(ok)any=true;});$('#emptySearch').hidden=any}
document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{filter=btn.dataset.filter;document.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));btn.classList.add('active');renderGrid()}));
$('#storeSearch').addEventListener('input',e=>{keyword=e.target.value.trim().toLowerCase();renderGrid();if(keyword)document.querySelector('#shop').scrollIntoView({behavior:'smooth'})});
const total=()=>[...bag].reduce((sum,[index,qty])=>sum+products[index].price_number*qty,0);
function redraw(){let n=0,html='';for(const [i,qty] of bag){const p=products[i];n+=qty;html+=`<div class="cart-row"><img src="${p.image_url}" alt=""><div><strong>${p.name}</strong><small>R ${p.price_number} each</small><div class="qty"><button data-qty="${i}" data-delta="-1" aria-label="Remove one">−</button><b>${qty}</b><button data-qty="${i}" data-delta="1" aria-label="Add one">+</button></div></div><b>R ${p.price_number*qty}</b></div>`}
$('#cartCount').textContent=n;$('#cartTotal').textContent='R '+total().toLocaleString('en-ZA');$('#cartItems').innerHTML=html||'<p>Your bag is empty. Browse the collection to add products.</p>';document.querySelectorAll('[data-qty]').forEach(btn=>btn.addEventListener('click',()=>{adjust(Number(btn.dataset.qty),Number(btn.dataset.delta))}));}
function adjust(i,delta){const qty=Math.max(0,(bag.get(i)||0)+delta);qty?bag.set(i,qty):bag.delete(i);redraw()}
document.querySelectorAll('[data-add]').forEach(btn=>btn.addEventListener('click',()=>{const i=Number(btn.dataset.add);adjust(i,1);toast(products[i].name+' added to preview bag')}));
function drawer(open){$('#cartDrawer').classList.toggle('open',open);$('#cartDrawer').setAttribute('aria-hidden',String(!open));$('#drawerBackdrop').hidden=!open;document.body.style.overflow=open?'hidden':''}
$('#cartToggle').addEventListener('click',()=>drawer(true));$('#cartClose').addEventListener('click',()=>drawer(false));$('#drawerBackdrop').addEventListener('click',()=>drawer(false));
$('#checkoutPreview').addEventListener('click',()=>toast('This is a design preview. No order or payment will be placed.'));
$('#contactPreview').addEventListener('click',()=>toast('Contact forms and verified details will be added after client approval.'));
const dialog=$('#productDialog');document.querySelectorAll('[data-detail]').forEach(btn=>btn.addEventListener('click',()=>{focusItem=Number(btn.dataset.detail);const p=products[focusItem];$('#modalImage').src=p.image_url;$('#modalImage').alt=p.name;$('#modalTitle').textContent=p.name;$('#modalPrice').textContent='R '+p.price;$('#modalDescription').textContent=p.blurb;dialog.showModal()}));
$('#modalAdd').addEventListener('click',()=>{adjust(focusItem,1);dialog.close();toast('Added to preview bag')});$('.modal-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});document.addEventListener('keydown',e=>{if(e.key==='Escape')drawer(false)});redraw();
})();
