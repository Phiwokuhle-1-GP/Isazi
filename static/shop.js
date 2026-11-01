'use strict';
// All operations also work without JavaScript; totals are recalculated on the server.
const checkout = document.querySelector('#checkout-form');
if (checkout) {
  const fulfillment = document.querySelector('#fulfillment');
  const address = document.querySelector('#address');
  const updateTotals = () => {
    const subtotal = Number(checkout.dataset.subtotal);
    const zar = cents => new Intl.NumberFormat('en-ZA', {style: 'currency', currency: 'ZAR'}).format(cents / 100);
    if(fulfillment.value==='pep'){
      const fee=checkout.dataset.pepFee;
      const shipping=5995;
      document.querySelector('#shipping-total').textContent=shipping===null?'Contact us for pricing':zar(shipping);
      document.querySelector('#order-total').textContent=shipping===null?zar(subtotal)+' + delivery':zar(subtotal+shipping);
      if(address) address.required=false;return;
    }
    const shipping = ['courier','randburg'].includes(fulfillment.value) ? 9900 : 0;
    document.querySelector('#shipping-total').textContent = zar(shipping);
    document.querySelector('#order-total').textContent = zar(subtotal + shipping);
    if(address) address.required = ['courier','randburg'].includes(fulfillment.value);
  };
  fulfillment.addEventListener('change', updateTotals);
  updateTotals();
}

// User-triggered playback. No autoplay, tracking, or simulated video files.
const videoDialog = document.querySelector('#video-dialog');
if (videoDialog) {
  const player = document.querySelector('#dialog-player');
  const error = document.querySelector('#video-error');
  document.querySelectorAll('[data-video-src]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      document.querySelector('#video-dialog-title').textContent = trigger.dataset.videoTitle;
      error.hidden = true;
      player.poster = trigger.dataset.videoPoster;
      player.src = window.matchMedia('(max-width: 760px)').matches && trigger.dataset.videoMobile ? trigger.dataset.videoMobile : trigger.dataset.videoSrc;
      videoDialog.showModal();
      player.play().catch(() => { /* Native controls remain available. */ });
    });
  });
  const stopPlayback = () => {
    player.pause();
    player.removeAttribute('src');
    player.load();
  };
  document.querySelector('#close-video').addEventListener('click', () => {
    stopPlayback();
    videoDialog.close();
  });
  videoDialog.addEventListener('cancel', stopPlayback);
  videoDialog.addEventListener('close', stopPlayback);
  player.addEventListener('error', () => { error.hidden = false; });
}

// Quantity controls, gallery thumbnails and accessible product tabs.
document.querySelectorAll('[data-qty-delta]').forEach(button => button.addEventListener('click', () => {
  const input = button.closest('[data-qty-control]').querySelector('input[type="number"]');
  const low = Number(input.min || 0), high = Number(input.max || 99);
  input.value = String(Math.max(low, Math.min(high, Number(input.value || low) + Number(button.dataset.qtyDelta))));
  input.dispatchEvent(new Event('change', {bubbles:true}));
}));
document.querySelectorAll('[data-product-image]').forEach(button => button.addEventListener('click', () => {
  const mainImage=document.querySelector('#main-product-image');
  mainImage.removeAttribute('srcset');mainImage.removeAttribute('sizes');
  mainImage.src=button.dataset.productImage;
}));
document.querySelectorAll('[data-tabs]').forEach(group => {
  const buttons = Array.from(group.querySelectorAll('[data-tab]'));
  const activate = button => {
    buttons.forEach(item => {item.setAttribute('aria-selected', String(item === button)); item.tabIndex = item === button ? 0 : -1;});
    group.querySelectorAll('[data-tab-panel]').forEach(panel => {panel.hidden = panel.id !== button.dataset.tab;});
  };
  buttons.forEach((button,index) => {
    button.addEventListener('click', () => activate(button));
    button.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = buttons[(index+1)%buttons.length];
      if (event.key === 'ArrowLeft') next = buttons[(index+buttons.length-1)%buttons.length];
      if (event.key === 'Home') next = buttons[0];
      if (event.key === 'End') next = buttons[buttons.length-1];
      if (next) {event.preventDefault(); activate(next); next.focus();}
    });
  });
  const fromHash = buttons.find(button => '#'+button.dataset.tab === window.location.hash);
  activate(fromHash || buttons[0]);
  document.querySelectorAll('a[href="#reviews"]').forEach(link => link.addEventListener('click', () => activate(buttons.find(button => button.dataset.tab === 'reviews'))));
});
const savedAddress = document.querySelector('#saved-address');
if (savedAddress) savedAddress.addEventListener('change', () => {
  if (savedAddress.value) {document.querySelector('#address').value=savedAddress.value; document.querySelector('#fulfillment').value='courier'; document.querySelector('#fulfillment').dispatchEvent(new Event('change'));}
});
if (window.matchMedia('(max-width:640px)').matches) document.querySelectorAll('.category-nav').forEach(menu => menu.removeAttribute('open'));

// Keep customer recordings from playing over one another.
const testimonyAudio = document.querySelectorAll('.testimonial-audio');
testimonyAudio.forEach(player => player.addEventListener('play', () => {
  testimonyAudio.forEach(other => { if (other !== player) other.pause(); });
}));

// Compact phone navigation; the full links remain usable when JavaScript is absent.
const menuButton=document.querySelector('.nav-menu-toggle');
const mobileNavigation=document.querySelector('#primary-navigation');
if(menuButton && mobileNavigation){
 const nav=menuButton.closest('.nav');nav.setAttribute('data-menu-ready','');
 const setMenu=open=>{mobileNavigation.classList.toggle('is-open',open);menuButton.setAttribute('aria-expanded',String(open));menuButton.querySelector('.sr-only').textContent=open?'Close menu':'Open menu';};
 menuButton.addEventListener('click',()=>setMenu(menuButton.getAttribute('aria-expanded')!=='true'));
 mobileNavigation.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>setMenu(false)));
 nav.addEventListener('keydown',event=>{if(event.key==='Escape' && menuButton.getAttribute('aria-expanded')==='true'){setMenu(false);menuButton.focus();}});
}

// Choose a light mobile rendition without downloading video before a user plays it.
document.querySelectorAll('video[data-mobile-source]').forEach(player => {
  if (player.dataset.mobileSource && window.matchMedia('(max-width: 760px)').matches) {
    player.src = player.dataset.mobileSource;
  }
});
document.querySelectorAll('form.media-edit').forEach(form => {
  form.addEventListener('submit', () => {
    const file = form.querySelector('input[name="video"]');
    const button = form.querySelector('button[type="submit"], button.button');
    const status = form.querySelector('.media-processing-status');
    if (file && file.files.length) {
      status.hidden = false;
      status.textContent = 'Uploading and optimizing desktop and mobile video. Please keep this page open until saving finishes.';
      form.setAttribute('aria-busy', 'true');
      button.disabled = true;
      button.textContent = 'Processing video…';
    }
  });
});

// Native touch rails; labelled buttons also work with keyboard and mouse.
document.querySelectorAll('.scroll-home .featured-layout .product-grid, .scroll-home .bestsellers-and-values .product-grid, .scroll-home .testimonials-grid, .scroll-home .media-and-tips .article-grid').forEach((rail, index) => {
  rail.id = rail.id || `collection-rail-${index}`;
  const tools = document.createElement('div');
  tools.className = 'carousel-tools';
  const previous = document.createElement('button');
  const next = document.createElement('button');
  const label = document.createElement('span');
  label.textContent = 'Swipe to explore';
  previous.type = next.type = 'button';
  previous.textContent = '←'; next.textContent = '→';
  previous.setAttribute('aria-label', 'Previous items');
  next.setAttribute('aria-label', 'Next items');
  previous.setAttribute('aria-controls', rail.id); next.setAttribute('aria-controls', rail.id);
  tools.append(previous, label, next); rail.after(tools);
  const update = () => {
    previous.disabled = rail.scrollLeft <= 2;
    next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
  };
  const move = direction => rail.scrollBy({left: direction * (rail.firstElementChild?.getBoundingClientRect().width + 12 || rail.clientWidth), behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  previous.addEventListener('click', () => move(-1)); next.addEventListener('click', () => move(1));
  rail.addEventListener('scroll', update, {passive:true}); window.addEventListener('resize', update);
  update();
});

// Sequential requests bound memory use and make each result independently visible.
const storyBatch = document.querySelector('#story-batch-upload');
if (storyBatch) {
  let uploading = false;
  window.addEventListener('beforeunload', event => {
    if (uploading) { event.preventDefault(); event.returnValue = ''; }
  });
  storyBatch.addEventListener('submit', async event => {
    event.preventDefault();
    if (uploading) return;
    const input = storyBatch.querySelector('[name="videos"]');
    const files = Array.from(input.files);
    if (!files.length) return;
    const list = document.querySelector('#story-upload-progress');
    const summary = document.querySelector('#story-upload-summary');
    const button = storyBatch.querySelector('button');
    list.replaceChildren(); uploading = true; button.disabled = true; input.disabled = true;
    let success = 0;
    for (const file of files) {
      const item = document.createElement('li'); list.appendChild(item);
      if (file.size > 250 * 1024 * 1024 || !/\.(mp4|webm)$/i.test(file.name)) {
        item.textContent = file.name + ': skipped — use MP4/WebM under 250 MB.'; continue;
      }
      item.textContent = file.name + ': uploading…';
      const body = new FormData(); body.append('video', file);
      body.append('csrf_token', storyBatch.querySelector('[name="csrf_token"]').value);
      try {
        const result = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest(); xhr.open('POST', storyBatch.action);
          xhr.upload.onprogress = e => { if (e.lengthComputable) item.textContent = file.name + ': uploading ' + Math.round(e.loaded/e.total*100) + '%'; };
          xhr.upload.onload = () => { item.textContent = file.name + ': creating desktop and mobile videos…'; };
          xhr.onload = () => {
            try { const data = JSON.parse(xhr.responseText); if (xhr.status !== 201) reject(new Error(data.error || 'Upload failed.')); else resolve(data); }
            catch { reject(new Error('Session expired or server interrupted processing. Check the library before retrying.')); }
          };
          xhr.onerror = () => reject(new Error('Connection lost. Check the library before retrying.'));
          xhr.send(body);
        });
        item.textContent = result.title + ': ready in the video library.'; success++;
      } catch (error) { item.textContent = file.name + ': ' + error.message; }
    }
    uploading = false; button.disabled = false; input.disabled = false; input.value = '';
    summary.textContent = success + ' of ' + files.length + ' videos published. Refresh this page to edit titles and covers. Check failed files before selecting them again.';
  });
}

// Product covers stay visible; testimonial uploads play as audio only.
document.querySelectorAll('[data-audio-target]').forEach(button => {
 const audio=document.getElementById(button.dataset.audioTarget);
 const error=button.closest('article').querySelector('.audio-playback-error');
 button.hidden=false; audio.hidden=true;
 button.addEventListener('click',()=>{
  error.hidden=true;
  if(!audio.paused){audio.pause();return;}
  document.querySelectorAll('.testimonial-audio').forEach(other=>{if(other!==audio)other.pause();});
  audio.hidden=false;
  audio.play().catch(()=>{error.hidden=false;});
 });
 audio.addEventListener('play',()=>{button.textContent='Ⅱ Pause';button.setAttribute('aria-pressed','true');});
 const reset=()=>{button.textContent='▶ Listen now';button.setAttribute('aria-pressed','false');};
 audio.addEventListener('pause',reset);audio.addEventListener('ended',reset);
 audio.addEventListener('error',()=>{error.hidden=false;reset();});
});
