"""Synthetic photo evidence and offline provider doubles; no live calls."""
import json
import struct
from pathlib import Path

import cv2
import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient

from api.main import app
from api.routes.reconstruction import service as reconstruction_service
from api.schemas import ReferenceSpec
from engine.providers import video_nebius
from engine.providers.common import ProviderError
from engine.reconstruction.media import MAX_PHOTO_BYTES, inspect_photo
from engine.reconstruction.service import Reconstruction
from engine.reconstruction.specification import values
from engine.reconstruction.store import Store, digest
from engine.reconstruction.validator import project, validate, visual_checks
from test_reconstruction import Double, ReferenceModelDouble, run_until
from test_reconstruction import offline as offline


@pytest.fixture
def photo_media(tmp_path):
    survivor = trimesh.creation.box([10, 16, 6])
    survivor.apply_translation([-5, 0, 3])
    repair = trimesh.creation.box([10, 16, 6])
    repair.apply_translation([5, 0, 3])
    view = {
        'K': [[600., 0, 160.], [0, 600., 120.], [0, 0, 1.]],
        'R': np.diag([1., -1., -1.]).tolist(), 't_mm': [0, 0, 80.],
    }
    image = np.full((240, 320, 3), 255, np.uint8)
    image[project(survivor, view, image.shape[:2])] = (10, 160, 210)
    path = tmp_path/'synthetic.png'
    assert cv2.imwrite(str(path), image)
    return inspect_photo(path, tmp_path/'frames'), view, repair, survivor


@pytest.fixture
def photo_api(tmp_path, monkeypatch):
    monkeypatch.setattr(reconstruction_service, 'store', Store(tmp_path/'runs'))
    with TestClient(app) as client:
        yield client


class PhotoDouble(Double):
    def download(self, url, path):
        if url.rsplit('/', 1)[-1] != 'evidence.json':
            return super().download(url, path)
        metadata, view, _, _ = self.media
        evidence = {
            'image_decode': {
                **{k: metadata[k] for k in ('sha256', 'width', 'height')},
                'decoder': 'OFFLINE PHOTO DOUBLE',
            },
            'views': [{**view, 'frame_index': 0}],
        }
        Path(path).write_text(json.dumps(evidence))


def photo_service(tmp_path, photo_media):
    provider = PhotoDouble(photo_media)
    service = Reconstruction(Store(tmp_path/'runs'), provider_factory=provider)
    job = service.new()
    job.update(status='INGESTING', upload_path=photo_media[0]['path'], media_kind='photo')
    service.store.save(job)
    service.tick(job['job_id'])
    return service, provider, job['job_id']


@pytest.mark.parametrize('extension,media_type', [
    ('.png', 'image/png'), ('.jpg', 'image/jpeg'), ('.webp', 'image/webp'),
])
def test_photo_decoding_preserves_original_and_bounds_frame(tmp_path, extension, media_type):
    path = tmp_path/('synthetic'+extension)
    assert cv2.imwrite(str(path), np.full((800, 1200, 3), 200, np.uint8))
    metadata = inspect_photo(path, tmp_path/'frames')
    assert metadata['sha256'] == digest(path)
    assert metadata['media_type'] == media_type
    assert (metadata['width'], metadata['height']) == (1200, 800)
    assert metadata['kind'] == 'photo' and 'duration_s' not in metadata
    assert len(metadata['frames']) == 1
    frame = metadata['frames'][0]
    assert frame['index'] == 0 and max(frame['width'], frame['height']) == 640
    assert cv2.imread(frame['path']).shape[:2] == (frame['height'], frame['width'])


@pytest.mark.parametrize('content', [b'', b'not an image', b'\x89PNG\r\n\x1a\nbroken'])
def test_invalid_photo_is_rejected(tmp_path, content):
    path = tmp_path/'bad.png'
    path.write_bytes(content)
    with pytest.raises(ValueError):
        inspect_photo(path, tmp_path/'frames')


def test_oversized_photo_is_rejected_before_decoding(tmp_path):
    path = tmp_path/'large.png'
    with path.open('wb') as file:
        file.truncate(MAX_PHOTO_BYTES + 1)
    with pytest.raises(ValueError, match='20 MiB'):
        inspect_photo(path, tmp_path/'frames')


def test_photo_evidence_uses_exif_oriented_dimensions(tmp_path):
    image = np.full((24, 40, 3), 200, np.uint8)
    encoded, buffer = cv2.imencode('.jpg', image)
    assert encoded
    jpeg = buffer.tobytes()
    exif = b'Exif\x00\x00II'+struct.pack('<HIH', 42, 8, 1)+struct.pack('<HHIHHI', 0x0112, 3, 1, 6, 0, 0)
    path = tmp_path/'oriented.jpg'
    path.write_bytes(jpeg[:2]+b'\xff\xe1'+struct.pack('>H', len(exif)+2)+exif+jpeg[2:])
    metadata = inspect_photo(path, tmp_path/'frames')
    assert (metadata['width'], metadata['height']) == (24, 40)
    assert cv2.imread(metadata['frames'][0]['path']).shape[:2] == (40, 24)
    assert metadata['sha256'] == digest(path)


def test_tiny_photo_is_rejected(tmp_path):
    path = tmp_path/'tiny.png'
    assert cv2.imwrite(str(path), np.zeros((8, 8, 3), np.uint8))
    with pytest.raises(ValueError, match='16 pixels'):
        inspect_photo(path, tmp_path/'frames')


def test_photo_api_measures_only_from_chat_and_invalidates_edits(photo_api, photo_media):
    original = Path(photo_media[0]['path']).read_bytes()
    response = photo_api.post('/api/reconstructions', files={'photo': ('part.png', original, 'image/png')})
    assert response.status_code == 200
    job_id = response.json()['job_id']
    job = run_until(reconstruction_service, job_id, {'AWAITING_INPUT'})
    assert job['messages'][-1]['text'] == 'Photo received. What would you like me to do?'
    assert values(ReferenceSpec.model_validate(job['spec'])) == {}
    assert not job['reference'] and not job['result']
    assert photo_api.post(f'/api/reconstructions/{job_id}/confirm', json={'revision': job['revision']}).status_code == 422

    response = photo_api.post(f'/api/reconstructions/{job_id}/messages', json={
        'revision': job['revision'], 'request_id': 'photo-measurements',
        'message': 'Build the missing part of this plain ring: outer diameter 4 cm, inner diameter 3.4 cm, height 0.9 cm.',
    })
    assert response.status_code == 200
    draft = response.json()
    assert draft['status'] == 'AWAITING_CONFIRMATION'
    assert values(ReferenceSpec.model_validate(draft['spec'])) == {'outer_diameter': 40, 'inner_diameter': 34, 'height': 9}
    assert not draft['spec']['confirmed'] and not draft['reference']
    assert photo_api.post(f'/api/reconstructions/{job_id}/confirm', json={'revision': draft['revision']}).status_code == 200
    ready = run_until(reconstruction_service, job_id)
    assert ready['status'] == 'MOCK_REFERENCE_READY'
    assert ready['session_id'] is None and not ready['result']
    folder = reconstruction_service.store.revision_dir(ready)/'reference'
    sidecar = json.loads((folder/'specification.json').read_text())
    assert sidecar['photo_sha256'] == photo_media[0]['sha256']
    assert 'video_sha256' not in sidecar and not sidecar['physical_fit_verified']
    mesh = trimesh.load_mesh(folder/'reference_full.stl')
    assert np.allclose(mesh.extents, [40, 40, 9], atol=.1)

    url = f'/api/reconstructions/{job_id}/files/original-photo.bin'
    preview = photo_api.get(url)
    assert preview.content == original and preview.headers['content-type'] == 'image/png'
    assert photo_api.get(f'/api/reconstructions/{job_id}').json()['job_id'] == job_id
    reference_url = next(a['url'] for a in ready['reference'] if a['name'] == 'reference_full.stl')
    assert photo_api.get(reference_url).status_code == 200
    edited = photo_api.post(f'/api/reconstructions/{job_id}/messages', json={
        'revision': ready['revision'], 'request_id': 'photo-correction', 'message': 'Correct height to 10 mm.',
    }).json()
    assert edited['revision'] > ready['revision']
    assert not edited['reference'] and not edited['result'] and not edited['spec']['confirmed']
    assert photo_api.get(reference_url).status_code == 404
    Path(ready['upload_path']).write_bytes(original+b'tampered')
    assert photo_api.get(url).status_code == 404


def test_upload_requires_exactly_one_source(photo_api):
    assert photo_api.post('/api/reconstructions').status_code == 422
    response = photo_api.post('/api/reconstructions', files={
        'video': ('clip.mp4', b'video'), 'photo': ('photo.png', b'photo'),
    })
    assert response.status_code == 422
    assert 'exactly one' in response.json()['message']


def test_invalid_photo_upload_does_not_produce_a_reference(photo_api):
    response = photo_api.post('/api/reconstructions', files={'photo': ('part.png', b'not an image', 'image/png')})
    job = run_until(reconstruction_service, response.json()['job_id'])
    assert job['status'] == 'FAILED' and not job['reference'] and not job['result']
    assert job['video'] is None


@pytest.fixture
def completed_photo(tmp_path, photo_media, monkeypatch):
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', ReferenceModelDouble)
    service, provider, job_id = photo_service(tmp_path, photo_media)
    assert not provider.created
    job = service.store.load(job_id)
    draft = service.turn(job_id, job['revision'], 'Build the missing part of this solid box, length 20 mm, width 16 mm, height 6 mm.', 'measurements')
    assert draft.status == 'AWAITING_CONFIRMATION'
    service.confirm(job_id, draft.revision)
    ready = run_until(service, job_id)
    assert ready['status'] == 'ACCEPTED'
    return service, provider, ready


def test_photo_reconstruction_validates_single_view_without_claiming_video(completed_photo):
    service, provider, ready = completed_photo
    assert len(provider.created) == 1
    assert '"kind": "photo"' in provider.created[0] and 'image_decode' in provider.created[0]
    assert provider.uploads[0][1] == ready['video']['sha256']
    report = ready['validation']
    assert report['accepted'] and report['mesh_validity'] and report['reference_consistency']
    assert report['visual_reconstruction_confidence'] == 'SUPPORTED_BY_SINGLE_PHOTO'
    assert report['thresholds']['min_clear_views'] == 1 and not report['physical_fit_verified']
    assert any('Single-photo' in limit for limit in report['limitations'])
    assert all(check['passed'] for check in report['checks'])
    assert 'single-photo' in ready['terminal_reason']
    assert all('video' not in check['name'] for check in report['checks'])
    assert (service.store.revision_dir(ready)/'attempts/1/repair_part_aligned.stl').is_file()


@pytest.mark.parametrize('failure', ['wrong_hash', 'missing_view', 'wrong_pose', 'invalid_mesh'])
def test_photo_validation_rejects_unsubstantiated_repairs(completed_photo, failure):
    service, _, ready = completed_photo
    folder = service.store.revision_dir(ready)/'attempts/1'
    evidence = json.loads((folder/'evidence.json').read_text())
    if failure == 'wrong_hash':
        evidence['image_decode']['sha256'] = 'not-the-original-photo'
    elif failure == 'missing_view':
        evidence['views'] = []
    elif failure == 'wrong_pose':
        evidence['views'][0]['t_mm'] = [200, 0, 80]
    else:
        (folder/'repair_part.stl').write_bytes(b'INVALID SYNTHETIC MESH')
    (folder/'evidence.json').write_text(json.dumps(evidence))
    report = validate(folder, service.store.revision_dir(ready)/'reference', ready)
    assert not report['accepted']
    assert any(not check['passed'] for check in report['checks'])


def test_video_still_requires_multiple_views(tmp_path, photo_media):
    metadata, view, repair, survivor = photo_media
    reference = trimesh.util.concatenate([repair, survivor])
    evidence = {'views': [{**view, 'frame_index': 0}]}
    assert visual_checks(reference, repair, survivor, evidence, metadata, tmp_path)[0]
    assert not visual_checks(reference, repair, survivor, evidence, {**metadata, 'kind': 'video'}, tmp_path)[0]


def test_live_photo_provider_failure_never_falls_back_to_mock(tmp_path, photo_media, monkeypatch):
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    llm = ReferenceModelDouble(replies=[ProviderError('PROVIDER_FAILED', 'Injected failure')])
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service, provider, job_id = photo_service(tmp_path, photo_media)
    job = service.store.load(job_id)
    with pytest.raises(ProviderError):
        service.turn(job_id, job['revision'], 'plain ring outer diameter 40 mm', 'failed-turn')
    failed = service.store.load(job_id)
    assert failed['mode'] == 'LIVE' and not failed['reference'] and not failed['result']
    assert not provider.created
