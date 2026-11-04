(() => {
  const panel = document.querySelector('[data-champion-share]');
  if (!panel) return;
  const campaign = panel.querySelector('[data-share-campaign]');
  const output = panel.querySelector('[data-share-url]');
  const preview = panel.querySelector('[data-share-open]');
  const status = panel.querySelector('[data-share-status]');
  function generate() {
    const tag = campaign.value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'champion-registration';
    campaign.value = tag;
    const link = new URL(panel.dataset.registrationUrl);
    link.searchParams.set('utm_source', 'tiktok');
    link.searchParams.set('utm_medium', 'social');
    link.searchParams.set('utm_campaign', tag);
    output.value = link.href;
    preview.href = link.pathname + link.search;
    status.textContent = 'Registration link created. Copy it to share on TikTok.';
  }
  panel.querySelector('[data-share-generate]').addEventListener('click', generate);
  campaign.addEventListener('input', () => { status.textContent = 'Select Create registration link to apply this campaign name.'; });
  panel.querySelector('[data-share-copy]').addEventListener('click', async () => {
    generate();
    try {
      await navigator.clipboard.writeText(output.value);
      status.textContent = 'Registration link copied. Paste it into your TikTok bio or post.';
    } catch (_) {
      output.focus(); output.select();
      status.textContent = 'Link selected. Press Ctrl+C or use your phone’s Copy option.';
    }
  });
})();
