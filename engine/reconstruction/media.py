"""Bounded deterministic media decoding. Never interprets filenames as commands."""
import json
import math
import subprocess
from pathlib import Path
import cv2
import numpy as np
from engine.fit import FitError, decode_image
from engine.reconstruction.store import digest

MAX_BYTES = 512 * 1024 * 1024  # includes the project's previously documented 271 MB clip
MAX_SECONDS = 180
FRAME_COUNT = 12
MAX_PHOTO_BYTES = 20 * 1024 * 1024


def photo_media_type(path: Path):
    with path.open('rb') as stream:
        header = stream.read(12)
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'image/webp'
    raise ValueError('Please upload a JPEG, PNG or WebP photo.')


def inspect_photo(path: Path, folder: Path):
    size = path.stat().st_size
    if not 0 < size <= MAX_PHOTO_BYTES:
        raise ValueError('Photo must be nonempty and at most 20 MiB.')
    media_type = photo_media_type(path)
    try:
        image = decode_image(path.read_bytes())
    except FitError as exc:
        raise ValueError(str(exc)) from exc
    height, width = image.shape[:2]
    if min(width, height) < 16:
        raise ValueError('Photo must be at least 16 pixels wide and high.')
    scale = min(1, 640 / max(width, height))
    image = cv2.resize(image, (max(1, round(width * scale)), max(1, round(height * scale))))
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'frame-00.jpg'
    if not cv2.imwrite(str(target), image):
        raise ValueError('Could not prepare the photo for validation.')
    frame = {'index': 0, 'timestamp_s': 0, 'path': str(target), 'sha256': digest(target),
             'width': image.shape[1], 'height': image.shape[0],
             'sharpness': float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())}
    return {'kind': 'photo', 'path': str(path), 'sha256': digest(path), 'size_bytes': size,
            'media_type': media_type, 'width': width, 'height': height, 'frames': [frame]}


def command(args, timeout=30):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise ValueError('Video support needs ffmpeg and ffprobe installed on the server.') from None
    except subprocess.TimeoutExpired:
        raise ValueError('Video decoding exceeded the media time limit.') from None
    if r.returncode:
        raise ValueError('The video cannot be decoded. Export a normal MP4, MOV or WebM clip.')
    return r.stdout


def inspect_video(path: Path, folder: Path):
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError('Video must be nonempty and at most 512 MiB.')
    data = json.loads(command(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_format', '-show_streams', '-of', 'json', str(path)]))
    streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')]
    if not streams:
        raise ValueError('This file has no video stream.')
    s = streams[0]
    try:
        duration = float(data.get('format', {}).get('duration', s.get('duration', 0)))
        width, height = int(s['width']), int(s['height'])
        n, d = s.get('avg_frame_rate', '0/1').split('/')
        fps = float(n) / float(d)
    except (TypeError, ValueError, ZeroDivisionError, KeyError):
        raise ValueError('The video has unreadable duration or frame metadata.') from None
    if not math.isfinite(duration) or not 0.2 <= duration <= MAX_SECONDS:
        raise ValueError('Video duration must be between 0.2 and 180 seconds.')
    if not 16 <= width <= 4096 or not 16 <= height <= 4096 or width * height > 4096 * 2160 or not 0 < fps <= 120:
        raise ValueError('Use a video up to 4K and 120 frames per second.')
    # Decode the whole bounded stream, not just the thumbnail/header. -xerror rejects corrupt media.
    command(['ffmpeg', '-v', 'error', '-xerror', '-threads', '2', '-protocol_whitelist', 'file,pipe',
        '-i', str(path), '-map', '0:v:0', '-an', '-f', 'null', '-'], timeout=180)
    frames = []
    folder.mkdir(parents=True, exist_ok=True)
    for i, timestamp in enumerate(np.linspace(min(duration * .05, max(0, duration-2/fps)), max(0, duration-2/fps), FRAME_COUNT)):
        target = folder / f'frame-{i:02d}.jpg'
        command(['ffmpeg', '-v', 'error', '-nostdin', '-threads', '2', '-protocol_whitelist', 'file,pipe',
            '-ss', f'{timestamp:.6f}', '-i', str(path), '-map', '0:v:0', '-frames:v', '1',
            '-vf', "scale=w='min(640,iw)':h='min(640,ih)':force_original_aspect_ratio=decrease", '-q:v', '3', '-y', str(target)])
        image = cv2.imread(str(target))
        if image is None:
            raise ValueError('The video contains an unreadable sampled frame.')
        frames.append({'index': i, 'timestamp_s': round(float(timestamp), 6), 'path': str(target),
            'sha256': digest(target), 'width': image.shape[1], 'height': image.shape[0],
            'sharpness': float(cv2.Laplacian(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())})
    return {'path': str(path), 'sha256': digest(path), 'size_bytes': size, 'duration_s': duration,
            'width': width, 'height': height, 'fps': fps, 'codec': s.get('codec_name'), 'frames': frames}
