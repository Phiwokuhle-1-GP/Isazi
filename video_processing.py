"""Bounded, local-only upload conversion; publish only complete MP4 renditions."""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading

_encoder_slot = threading.BoundedSemaphore(1)


def ffmpeg_executable():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        executable = shutil.which('ffmpeg')
        if executable:
            return executable
        raise ValueError('Video processing is unavailable. Install the updated requirements and try again.')


def transcode_upload(upload, directory):
    """Return desktop/mobile filenames. No originals or partial files are public."""
    if not _encoder_slot.acquire(blocking=False):
        raise ValueError('Another video is processing. Please wait and try again.')
    outputs = []
    try:
        encoder = ffmpeg_executable()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        token = secrets.token_hex(16)
        # Keep raw uploads and in-progress encodes outside the public upload route.
        with tempfile.TemporaryDirectory(prefix='isazi-video-') as scratch:
            original = Path(scratch) / ('input' + Path(upload.filename).suffix.lower())
            upload.save(original)
            for label, width, height, rate in [('desktop',1280,720,'2500k'),('mobile',854,480,'1200k')]:
                encoded = Path(scratch) / (label + '.mp4')
                command = [encoder,'-nostdin','-hide_banner','-loglevel','error','-y',
                           '-protocol_whitelist','file,pipe','-threads','1','-i',str(original),
                           '-map','0:v:0','-map','0:a:0?','-map_metadata','-1','-map_chapters','-1',
                           '-vf',f"scale=w='min({width},iw)':h='min({height},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
                           '-c:v','libx264','-preset','fast','-crf','23','-maxrate',rate,
                           '-bufsize',rate,'-pix_fmt','yuv420p','-threads','1',
                           '-c:a','aac','-b:a','96k','-ac','2','-movflags','+faststart',str(encoded)]
                try:
                    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                            timeout=240, check=False)
                except subprocess.TimeoutExpired:
                    raise ValueError('Video processing took too long. Please upload a shorter video and try again.')
                if result.returncode or not encoded.exists() or encoded.stat().st_size < 100:
                    raise ValueError('This video could not be processed. Upload a playable MP4 or WebM file.')
            # Only expose files after both conversions succeed. Random names are immutable.
            for label in ('desktop','mobile'):
                name = f'upload-video-{token}-{label}.mp4'
                destination = directory / name
                outputs.append(destination)
                # Same-directory staging also makes cross-filesystem copies atomic.
                staging = directory / ('.processing-' + token + '-' + label)
                try:
                    shutil.copyfile(Path(scratch)/(label+'.mp4'), staging)
                    os.replace(staging, destination)
                finally:
                    staging.unlink(missing_ok=True)
        return tuple(path.name for path in outputs)
    except Exception:
        for path in outputs:
            path.unlink(missing_ok=True)
        raise
    finally:
        _encoder_slot.release()
