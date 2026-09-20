"""Photo/video reconstruction endpoints; long work runs in the background."""
import asyncio
from functools import lru_cache
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from api.schemas import VideoConfirm, VideoState, VideoTurn
from engine.providers.common import ProviderError
from engine.reconstruction.media import MAX_BYTES, MAX_PHOTO_BYTES, photo_media_type
from engine.reconstruction.service import Reconstruction
from engine.reconstruction.store import digest

router = APIRouter(prefix='/api/reconstructions')
service = Reconstruction()


def video_media_type(path):
    with path.open('rb') as stream:
        header = stream.read(4096)
    if len(header) >= 12 and header[4:8] == b'ftyp':
        return 'video/mp4'
    if header.startswith(b'\x1a\x45\xdf\xa3'):
        return 'video/webm' if b'webm' in header.lower() else 'video/x-matroska'
    if header.startswith(b'RIFF') and header[8:12] == b'AVI ':
        return 'video/x-msvideo'
    if header.startswith(b'OggS'):
        return 'video/ogg'
    return 'application/octet-stream'


@lru_cache(maxsize=64)
def source_digest_matches(path, size, modified_ns, expected):
    return digest(path) == expected


def error(exc):
    if isinstance(exc, ProviderError):
        return JSONResponse({'error': exc.code, 'message': str(exc)}, status_code=504 if exc.code == 'TIMEOUT' else 502)
    return JSONResponse({'error': 'INVALID_INPUT', 'message': str(exc)}, status_code=422)


@router.post('', response_model=VideoState)
async def upload_video(video: UploadFile | None = File(None), photo: UploadFile | None = File(None)):
    if (video is None) == (photo is None):
        for upload in (video, photo):
            if upload is not None:
                await upload.close()
        return error(ValueError('Upload exactly one photo or video.'))
    upload = photo if photo is not None else video
    assert upload is not None
    kind = 'photo' if photo is not None else 'video'
    job = service.new()
    job['media_kind'] = kind
    path = service.store.directory(job['job_id'])/f'original-{kind}.bin'
    total = 0
    try:
        with path.open('xb') as file:
            while chunk := await upload.read(1024*1024):
                total += len(chunk)
                if total > (MAX_PHOTO_BYTES if photo is not None else MAX_BYTES):
                    raise ValueError('Photo exceeds 20 MiB.' if photo is not None else 'Video exceeds 512 MiB. Please trim the clip.')
                file.write(chunk)
        if total == 0:
            raise ValueError(f'The {kind} is empty.')
        job['upload_path'] = str(path)
        service.store.event(job, f'{kind}_uploaded', original_name=upload.filename, claimed_type=upload.content_type,
                            path=str(path), size_bytes=total, sha256=digest(path))
        service.store.transition(job, 'INGESTING')
        return service.public(job)
    except ValueError as exc:
        service.store.transition(job, 'FAILED', str(exc))
        return error(exc)
    finally:
        await upload.close()


@router.get('/{job_id}', response_model=VideoState)
def get_job(job_id: str):
    try:
        return service.public(service.store.load(job_id))
    except (ValueError, FileNotFoundError):
        return JSONResponse({'error': 'INVALID_INPUT', 'message': 'Unknown reconstruction.'}, status_code=404)


@router.post('/{job_id}/messages', response_model=VideoState)
async def turn(job_id: str, req: VideoTurn):
    try:
        return await asyncio.to_thread(service.turn, job_id, req.revision, req.message, req.request_id)
    except (ValueError, ProviderError) as exc:
        return error(exc)


@router.post('/{job_id}/confirm', response_model=VideoState)
async def confirm(job_id: str, req: VideoConfirm):
    try:
        return await asyncio.to_thread(service.confirm, job_id, req.revision)
    except (ValueError, ProviderError) as exc:
        return error(exc)


@router.post('/{job_id}/invalidate')
async def invalidate(job_id: str):
    try:
        await asyncio.to_thread(service.invalidate, job_id)
        return {'status': 'STALE'}
    except (ValueError, FileNotFoundError) as exc:
        return error(exc)


@router.get('/{job_id}/files/{relative:path}')
def download(job_id: str, relative: str):
    try:
        job = service.store.load(job_id)
        path = (service.store.directory(job_id)/relative).resolve()
        url = f'/api/reconstructions/{job_id}/files/{relative}'
        allowed = job['reference'] + (job['result'] if job['status'] == 'ACCEPTED' else [])
        source_media = relative == f'original-{job.get("media_kind", "video")}.bin' and job.get('video')
        if source_media:
            allowed = allowed + [{'url': url, 'sha256': job['video']['sha256']}]
        artifact = next((a for a in allowed if a['url'] == url), None)
        valid = bool(artifact) and path.is_relative_to(service.store.directory(job_id)) and path.is_file()
        if valid and source_media:
            stat = path.stat()
            valid = source_digest_matches(path, stat.st_size, stat.st_mtime_ns, artifact['sha256'])
        elif valid:
            valid = digest(path) == artifact['sha256']
        if not valid:
            raise ValueError('Artifact is not a current validated download.')
        if source_media:
            media_type = photo_media_type(path) if job.get('media_kind') == 'photo' else video_media_type(path)
            return FileResponse(path, media_type=media_type, content_disposition_type='inline')
        return FileResponse(path, filename=path.name, media_type='application/octet-stream')
    except (ValueError, FileNotFoundError):
        return JSONResponse({'error': 'INVALID_INPUT', 'message': 'Artifact is not a current validated download.'}, status_code=404)
