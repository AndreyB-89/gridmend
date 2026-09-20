"""Video endpoints reuse the current app/chat; all long reconstruction work is background."""
import asyncio
from pathlib import Path
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from api.schemas import VideoConfirm, VideoState, VideoTurn
from engine.providers.common import ProviderError
from engine.reconstruction.media import MAX_BYTES
from engine.reconstruction.service import Reconstruction
from engine.reconstruction.store import digest

router = APIRouter(prefix='/api/reconstructions')
service = Reconstruction()


def error(exc):
    if isinstance(exc, ProviderError):
        return JSONResponse({'error': exc.code, 'message': str(exc)}, status_code=504 if exc.code == 'TIMEOUT' else 502)
    return JSONResponse({'error': 'INVALID_INPUT', 'message': str(exc)}, status_code=422)


@router.post('', response_model=VideoState)
async def upload_video(video: UploadFile = File(...)):
    job = service.new()
    path = service.store.directory(job['job_id'])/'original-video.bin'
    total = 0
    try:
        with path.open('xb') as file:
            while chunk := await video.read(1024*1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError('Video exceeds 512 MiB. Please trim the clip.')
                file.write(chunk)
        if total == 0:
            raise ValueError('The video is empty.')
        job['upload_path'] = str(path)
        service.store.event(job, 'video_uploaded', original_name=video.filename, claimed_type=video.content_type,
                            path=str(path), size_bytes=total, sha256=digest(path))
        service.store.transition(job, 'INGESTING')
        return service.public(job)
    except ValueError as exc:
        service.store.transition(job, 'FAILED', str(exc))
        return error(exc)
    finally:
        await video.close()


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
        # Only current registered validated artifacts, never raw inputs, private provider data or old attempts.
        url = f'/api/reconstructions/{job_id}/files/{relative}'
        allowed = job['reference'] + (job['result'] if job['status'] == 'ACCEPTED' else [])
        artifact = next((a for a in allowed if a['url'] == url), None)
        if not artifact or not path.is_relative_to(service.store.directory(job_id)) or not path.is_file() or digest(path) != artifact['sha256']:
            raise ValueError('Artifact is not a current validated download.')
        return FileResponse(path, filename=path.name, media_type='application/octet-stream')
    except (ValueError, FileNotFoundError):
        return JSONResponse({'error': 'INVALID_INPUT', 'message': 'Artifact is not a current validated download.'}, status_code=404)
