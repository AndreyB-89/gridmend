"""Offline regression coverage for the reports exchanged with Devin."""
import json

import pytest

from api.schemas import ReferenceSpec
from engine.reconstruction.specification import values
from engine.reconstruction.store import digest
from engine.reconstruction.validator import validate
from test_reconstruction import ready_service, run_until, spec_for
from test_reconstruction import media as media, offline as offline


@pytest.mark.parametrize('family,cavity', [
    ('box', 'solid'), ('ring', 'through'), ('cylinder', 'blind'),
])
def test_initial_prompt_supplies_exact_report_metadata(tmp_path, media, family, cavity):
    service, provider, job_id = ready_service(tmp_path, media)
    job = service.store.load(job_id)
    job['spec'] = spec_for(family, cavity).model_dump()
    service.store.save(job)
    job = run_until(service, job_id, {'WORKING'})

    prompt = provider.created[0]
    metadata = json.loads(prompt.split('```json\n', 1)[1].split('\n```', 1)[0])
    reference = service.store.revision_dir(job)/'reference'
    assert metadata == {
        'units': 'mm',
        'supplied_dimensions': values(ReferenceSpec.model_validate(job['spec'])),
        'reference_sha256': digest(reference/'reference_full.stl'),
        'reference_revision': job['revision'],
        'attempt': job['attempt'],
    }
    assert 'frames: nonempty array of objects with timestamp_s' in prompt
    assert 'Use the exact key frames, NOT extracted_frames.' in prompt
    assert 'Never modify the validator or thresholds.' in prompt
    assert len(provider.uploads) == 4


@pytest.mark.parametrize('bad_field', ['supplied_dimensions', 'video_decode'])
def test_malformed_reports_still_fail_independent_validation(tmp_path, media, bad_field):
    service, provider, job_id = ready_service(tmp_path, media)
    job = run_until(service, job_id)
    assert job['status'] == 'ACCEPTED'
    revision = service.store.revision_dir(job)
    folder = revision/'attempts'/str(job['attempt'])
    if bad_field == 'supplied_dimensions':
        path = folder/'summary.json'
        summary = json.loads(path.read_text())
        summary['supplied_dimensions'] = {
            f'{key}_mm': value for key, value in summary['supplied_dimensions'].items()
        }
        path.write_text(json.dumps(summary))
        failed_check = 'supplied_dimensions_unchanged'
    else:
        path = folder/'evidence.json'
        evidence = json.loads(path.read_text())
        decode = evidence['video_decode']
        decode['extracted_frames'] = decode.pop('frames')
        path.write_text(json.dumps(evidence))
        failed_check = 'video_decode_report'

    report = validate(folder, revision/'reference', job)
    assert not report['accepted']
    assert [check['name'] for check in report['checks'] if not check['passed']] == [failed_check]
    assert report['thresholds'] == job['validation']['thresholds']
    assert report['physical_fit_verified'] is False
