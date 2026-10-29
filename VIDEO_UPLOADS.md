# Video uploads (v2.6.13)

In Owner → Videos & Testimonials, select an MP4 or WebM (maximum 250 MB), then Save. Keep the page open while it uploads and converts. The save publishes only after both complete files exist. Invalid files, processing timeouts or a busy encoder leave the previously published media unchanged. Only one conversion runs at a time per application process.

Uploaded videos become H.264 MP4 with AAC stereo audio (when present), 30 fps and fast-start metadata for progressive playback. Desktop output fits within 1280 × 720; mobile output fits within 854 × 480. Portrait orientation and aspect ratio are preserved, without upscaling. Encoding uses CRF 27 and bounded video bitrates (desktop 1.8 Mb/s, mobile 750 kb/s), plus up to 96 kb/s audio. A file already compressed very efficiently may not become smaller.

Phones up to 760 CSS pixels select the mobile version. Desktop and browsers without JavaScript use the desktop version. Playback waits for the viewer; videos are not preloaded. Byte-range seeking remains supported.

The updated requirements install imageio-ffmpeg 0.6.0, whose Windows/Linux wheels include FFmpeg. No separate Windows FFmpeg installation is required on supported platforms. A system FFmpeg is a fallback. Conversion happens locally, with no third-party upload. Raw uploads and in-progress files use temporary storage and are deleted after success or failure. Completed versions are saved on the existing persistent uploads disk. Replaced published files are retained so active playback is not interrupted.

Uploads are processed during the save request, not by a background queue. Allow up to eight minutes for the two encodes (four-minute limit per rendition). Render/Gunicorn startup scripts allow a 600-second worker timeout; an upstream connection timeout can still interrupt the browser response. For long videos, shorten the source or use an externally hosted, already optimized direct HTTPS MP4 URL. Linked external files and older uploads are not automatically converted: upload the file again to create both versions.

Apply the update, restart with START_WINDOWS.ps1 (installs requirements), and push using PUSH_GITHUB_WINDOWS.ps1 for Render. Existing accounts, orders, inventory and media are preserved through an additive database migration. No payment-mode settings change.
