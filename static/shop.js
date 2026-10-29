'use strict';
// All operations also work without JavaScript; totals are recalculated on the server.
const checkout = document.querySelector('#checkout-form');
if (checkout) {
  const fulfillment = document.querySelector('#fulfillment');
  const address = document.querySelector('#address');
  const updateTotals = () => {
    const subtotal = Number(checkout.dataset.subtotal);
    const shipping = fulfillment.value === 'randburg' && subtotal <= 60000 ? 5000 : 0;
    const zar = cents => new Intl.NumberFormat('en-ZA', {style: 'currency', currency: 'ZAR'}).format(cents / 100);
    document.querySelector('#shipping-total').textContent = zar(shipping);
    document.querySelector('#order-total').textContent = zar(subtotal + shipping);
    address.required = fulfillment.value === 'randburg';
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
  if (savedAddress.value) {document.querySelector('#address').value=savedAddress.value; document.querySelector('#fulfillment').value='randburg'; document.querySelector('#fulfillment').dispatchEvent(new Event('change'));}
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
