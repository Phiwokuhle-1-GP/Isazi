# AI demonstration artwork

Created with the built-in image generation tool. These are illustrative/demo restorations, not verified product label photography or approved customer portraits. Replace them through owner uploads. Original low-resolution assets remain in the project for reference; custom uploads are never mapped to demo files.

| Asset | Native source size | Prompt brief |
|---|---|---|
| demo-hero | 2172 × 724 px | Reference-based landscape; preserve people/clothing; remove text and UI. |
| demo-product-1 | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-product-2 | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-product-3 | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-product-4 | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-product-5 | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-combo | 1536 × 1024 px | Premium botanical product photo, warm wood, cream/green/gold labels; no medical claims, dosage or seals. |
| demo-botanicals | 1536 × 1024 px | Natural editorial botanical still life, roots/leaves/wood/linen, no text or people. |
| demo-story | 1672 × 941 px | Reference-based identity-preserving cover restoration; remove play/time overlays; no invented quote. |
| demo-testimonial-1 | 1448 × 1086 px | Reference-based identity-preserving cover restoration; remove play/time overlays; no invented quote. |
| demo-testimonial-2 | 1448 × 1086 px | Reference-based identity-preserving cover restoration; remove play/time overlays; no invented quote. |
| demo-testimonial-3 | 1448 × 1086 px | Reference-based identity-preserving cover restoration; remove play/time overlays; no invented quote. |
| demo-testimonial-4 | 1448 × 1086 px | Reference-based identity-preserving cover restoration; remove play/time overlays; no invented quote. |

Source PNGs were encoded as WebP at native resolution, quality 92; they were not enlarged from screenshot crops. Layout crops are controlled in CSS. Every generated file is included in static/images inside the ZIP.

Additional editorial prompts (built-in generation): Article 2 — green stone mortar, fresh leaves and dried herbs on wood; Article 3 — three herb jars with blank labels, dried botanical leaves and roots; Article 4 — herbal tea, glass jar, scoop, fresh leaves and linen. All are 1536 × 1024 native source pixels, professional natural light, forest green/cream/gold, no people, text or medical claims. The corresponding files are demo-article-2.webp through demo-article-4.webp.


## V2.5.2 original hero portrait

`static/images/dr-ntuli-original.png` is the exact user-supplied 415 × 392 PNG, copied without any pixel edits, colour changes, cropping, background removal, retouching or AI generation. The hero uses CSS containment to resize it for display. Its original backdrop remains visible. The desktop portrait panel covers the AI portrait in the previous composite; mobile displays only the original photograph above the live hero copy.


## V2.5.3 colour-enhanced hero crop

Final workspace asset: `static/images/dr-ntuli-hero-enhanced.png` (1536 × 1024). Built-in image editing was used with the user-supplied photograph as the edit target. The source file remains unchanged separately. The derivative is AI edited, not a claim of recovered camera detail. Its panel uses responsive CSS cover cropping; no dark side gutters remain. Outer hero corners are clipped to 28px on desktop and 20px on mobile.

Final edit prompt: “Use case: identity-preserve. Edit target: the supplied original photograph of Dr Ntuli speaking with a microphone. Perform only photographic colour correction and cropping for a website hero photo panel. Preserve his EXACT identity, facial proportions, expression, gaze, skin texture, headwear, suit, necklaces, microphone, fingers and pose. Do not redraw, reconstruct, beautify, change clothing, replace backdrop or add objects. Keep the original brick and blue/yellow/pink event backdrop. Modestly improve exposure, natural skin tone, blue suit richness and contrast. Crop to landscape 3:2, framing from just above the top of his head to his waist, keeping his open left hand and microphone hand in frame. Preserve original photographic detail without invented fine detail. No text overlays, no logos added, no border. This is a photo crop and colour enhancement ONLY, not a new portrait.”


## V2.5.4 continuous landscape composite

Project asset: `static/images/hero-landscape-composite.webp`. Built-in image editing composited the supplied left pose and speaking portrait into the meadow/mountain setting. This is an AI-edited composite; it must not be represented as an unmodified original photograph. Supplied sources remain in `dr-ntuli-left-original.png` and `dr-ntuli-original.png`. The separate indoor portrait panel is no longer rendered. Corners are 10px desktop / 8px mobile.

Edit prompt: Use case compositing, identity-preserve. Create a continuous 3:1 panoramic hero using the old landscape only as the setting reference, replacing both generated subjects with the supplied original left and right photographic references. Keep the left subject's bowed head, crossed arms, black outfit, headwear, brown shoulder bag and red/yellow staff; keep the speaking subject's identity, expression, blue suit, necklaces, microphone, open hand and pose. Remove their source backgrounds and blend lighting/edges into one meadow/mountain backdrop. Centre 32–70% stays clear for live HTML. Enhance colour naturally; no added people, bottles, slogans, text, borders or baked-in rounding.


## V2.5.5 exact original left photograph

`static/images/dr-ntuli-left-original-v2.png` is the exact supplied 519 × 656 PNG, unchanged bytes. No image-generation edit was used for this replacement. The inline SVG viewport `0 110 519 546` crops out only the text-bearing top section for display. CSS applies saturation 1.12, contrast 1.04 and brightness 1.02. A narrow right-edge mask blends the photo into the backdrop. Face, clothing, pose, staff and all other photographed details remain the source pixels. The source still contains its original lettering outside the displayed crop; that lettering is not visible in the hero. Full custom owner-uploaded hero images suppress this default-photo overlay.


## V2.5.6 poolside story placeholder

`static/images/story-video-placeholder.png` is the latest supplied poolside video screenshot copied byte-for-byte, without AI edits or retouching. The existing white play triangle is retained as the watermark; no duplicate overlay is added for this default photo. CSS containment preserves the scene and proportions in the 16:9 video frame. The Video coming soon label covers the screenshot's lower playback strip until a real clip is configured. Custom owner-uploaded covers remain selected and receive the separate CSS play-circle decoration when no actual clip is configured. The same story source and poster now appear on the homepage and About page.


## V2.5.7 natural shorter hero

`static/images/hero-natural-meadow.webp` is a background-only extension made with the built-in image editor using the supplied left photograph as the scene reference. No people were generated for this backdrop. Its edit brief: remove the person, bag, staff and text; extend the same muted grassy field, patches of pale sandy soil, tree line and misty blue-grey hills into a 3:1 panorama, under soft overcast light, with restrained contrast and no vivid sky, tropical foreground, products or extra people. It was encoded as WebP at its native dimensions for delivery.

The original left and right PNG files are now layered directly in the page. An SVG silhouette mask removes the right source backdrop at display time; the source photograph itself is unchanged. Its CSS saturation is .92 and contrast .98. The left source has no colour filter. This preserves the photographed person rather than using the previously generated figure. The desktop banner ratio is 5:1 with a 230px minimum, versus the previous 3.8:1 ratio. The original source files remain intact.


## V2.5.8 supplied audio-testimony covers

`static/images/testimony-audio-cover-1.png` through `-4.png` are the four supplied image files copied unchanged, displayed with containment to preserve their lettering and proportions. These are covers only; no audio recordings, customer quotes or evidence of health outcomes were created. Their embedded claims remain user-provided image content, not verified medical claims. Owner-uploaded replacement posters are preserved. Legacy default portrait filenames redirect to these covers.


## V2.5.10 hero blending and colour

The original photo files remain byte-for-byte unchanged. The display-only right portrait mask was tightened around shoulders and the raised-hand gap to exclude source-backdrop remnants, with a 0.65px SVG edge feather and a bottom fade over the final 6% of the banner. The backdrop uses CSS saturation 1.12 / contrast 1.035 / brightness 1.015; the left photo 1.08 / 1.025 / 1.015; the right photo 1.04 / 1.015 / 1.01. No face or clothing generation/retouching was used for this update.
