"""Automatic builds from operator measurements; all providers are offline doubles."""
import json

import numpy as np
import pytest
import trimesh

from engine.providers import video_nebius
from engine.providers.common import ProviderError
from engine.reconstruction.service import Reconstruction
from engine.reconstruction.specification import required, values
from engine.reconstruction.store import Store
from test_reconstruction import Double, ReferenceModelDouble, run_until
from test_reconstruction import media as media
from test_reconstruction import offline as offline


PROMPT = 'Build the missing part of this ring with rectangle cross section : outer diamter 4cm, inner diameter 3.4cm, height 0.9cm'


def uploaded_service(tmp_path, media, provider=None):
    service = Reconstruction(Store(tmp_path/'runs'), provider_factory=provider)
    job = service.new()
    job.update(status='AWAITING_INPUT', video=media[0])
    service.store.save(job)
    return service, job


@pytest.mark.parametrize('prompt', [PROMPT, PROMPT.replace('inner diameter', 'inner diamter')])
def test_exact_request_builds_checked_reference_without_confirmation(tmp_path, media, prompt):
    service, job = uploaded_service(tmp_path, media)
    queued = service.turn(job['job_id'], job['revision'], prompt, 'exact-build-request')
    assert queued.status == 'QUEUED' and queued.spec.confirmed and not queued.questions
    assert (queued.spec.family, queued.spec.cavity, queued.spec.profile) == ('ring', 'through', 'plain')
    assert values(queued.spec) == {'outer_diameter': 40, 'inner_diameter': 34, 'height': 9}
    for key, original in [('outer_diameter', 4), ('inner_diameter', 3.4), ('height', .9)]:
        measured = queued.spec.dimensions[key]
        assert measured.confirmed and measured.source == 'operator'
        assert measured.original_value == original and measured.original_unit == 'cm'
        assert measured.source_text and measured.source_text in prompt
        assert measured.message_id == 'exact-build-request'
    assert any(m['role'] == 'user' and m['text'] == prompt for m in queued.messages)
    assert not any('Confirm these values' in m['text'] for m in queued.messages)
    ready = run_until(service, job['job_id'])
    assert ready['status'] == 'MOCK_REFERENCE_READY' and ready['session_id'] is None
    folder = service.store.revision_dir(ready)/'reference'
    sidecar = json.loads((folder/'specification.json').read_text())
    assert all(sidecar['checks'].values()) and not sidecar['physical_fit_verified']
    mesh = trimesh.load_mesh(folder/'reference_full.stl')
    assert np.allclose(mesh.extents, [40, 40, 9], atol=.1)
    assert np.isclose(mesh.volume, np.pi*(20**2-17**2)*9, rtol=.005)
    assert not ready['result']


def test_automatic_live_handoff_is_idempotent_and_invalidates_stale_cad(tmp_path, media, monkeypatch):
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    llm = ReferenceModelDouble()
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    provider = Double(media)
    service, job = uploaded_service(tmp_path, media, provider)
    queued = service.turn(job['job_id'], job['revision'], PROMPT, 'build-request')
    assert queued.status == 'QUEUED' and not provider.created and not provider.uploads
    repeated = service.turn(job['job_id'], job['revision'], PROMPT, 'build-request')
    assert repeated.revision == queued.revision and len(llm.calls) == 1
    assert service.confirm(job['job_id'], queued.revision).status == 'QUEUED'
    working = run_until(service, job['job_id'], {'WORKING'})
    assert len(provider.created) == 1 and len(provider.uploads) == 4
    assert all(working['spec']['dimensions'][k]['confirmed'] for k in required(queued.spec))
    assert [tool.name for tool, _ in llm.tools] == ['prepare_complete_reference', 'build_complete_reference']
    repeated = service.turn(job['job_id'], job['revision'], PROMPT, 'build-request')
    assert repeated.status == 'WORKING' and len(provider.created) == 1
    with pytest.raises(ValueError, match='older reference'):
        service.turn(job['job_id'], job['revision'], PROMPT, 'stale-request')
    edited = service.turn(job['job_id'], working['revision'], 'Correct height to 10 mm.', 'correction-request')
    assert edited.status == 'AWAITING_CONFIRMATION' and not edited.spec.confirmed
    assert not edited.reference and not edited.result and edited.session_id is None
    service.tick(job['job_id'])
    assert len(provider.created) == 1 and provider.stops == ['test-session']


@pytest.mark.parametrize('prompt', [
    PROMPT.replace(', height 0.9cm', ''),
    PROMPT.replace('4cm', 'maybe 4cm'),
    PROMPT.replace('4cm', '4cm or 4.2cm'),
    PROMPT.replace('4cm', '3cm'),
    PROMPT.replace('4cm', '4'),
    PROMPT.replace('rectangle cross section', 'square cross section 9mm x 3mm'),
    PROMPT.replace('rectangle cross section', 'rectangle cross section 9mm x 4mm'),
])
def test_ambiguous_or_incomplete_build_requests_still_ask_questions(tmp_path, media, prompt):
    service, job = uploaded_service(tmp_path, media)
    reply = service.turn(job['job_id'], job['revision'], prompt, 'needs-clarification')
    assert reply.status == 'AWAITING_INPUT' and reply.questions and not reply.spec.confirmed
    service.tick(job['job_id'])
    saved = service.store.load(job['job_id'])
    assert not saved['reference'] and saved['session_id'] is None


@pytest.mark.parametrize('prompt', [
    PROMPT.replace('Build the missing part of this', 'This is a'),
    PROMPT + ', but do not build yet.',
    PROMPT + ', but wait for confirmation.',
    PROMPT + ', later.',
    PROMPT + '?',
])
def test_description_or_deferred_request_retains_manual_confirmation(tmp_path, media, prompt):
    service, job = uploaded_service(tmp_path, media)
    reply = service.turn(job['job_id'], job['revision'], prompt, 'description-request')
    assert reply.status == 'AWAITING_CONFIRMATION' and not reply.questions
    assert not reply.spec.confirmed and not reply.reference
    assert service.confirm(job['job_id'], reply.revision).status == 'QUEUED'


def test_followup_without_all_measurements_retains_manual_confirmation(tmp_path, media):
    service, job = uploaded_service(tmp_path, media)
    draft = service.turn(job['job_id'], job['revision'], PROMPT.replace(', height 0.9cm', ''), 'first-request')
    reply = service.turn(job['job_id'], draft.revision, 'Build it with height 0.9cm.', 'followup-request')
    assert reply.status == 'AWAITING_CONFIRMATION' and not reply.spec.confirmed
    assert not reply.questions and values(reply.spec) == {'outer_diameter': 40, 'inner_diameter': 34, 'height': 9}


def test_complete_build_request_does_not_hide_live_provider_failure(tmp_path, media, monkeypatch):
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    llm = ReferenceModelDouble([RuntimeError('Injected provider failure')])
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service, job = uploaded_service(tmp_path, media)
    with pytest.raises(ProviderError, match='Nebius call failed'):
        service.turn(job['job_id'], job['revision'], PROMPT, 'failed-request')
    reply = service.public(service.store.load(job['job_id']))
    assert reply.mode == 'LIVE' and reply.status == 'DIALOGUE_ERROR'
    assert reply.questions and not reply.spec.confirmed and not reply.reference
    assert reply.session_id is None and len(llm.calls) == 1
