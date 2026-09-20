"""OFFLINE provider doubles and explicitly synthetic media. Never sponsor evidence."""
import json
import time
from pathlib import Path
import cv2
import httpx
from langchain_core.messages import AIMessage
import numpy as np
import pytest
import trimesh
from api.schemas import ReferenceSpec, SuppliedMeasurement
from cad.reference import build_reference, in_reference
from engine.providers import video_nebius
from engine.providers.common import ProviderError
from engine.providers.devin import ARTIFACT_NAMES, Devin
from engine.providers.video_nebius import supplied_edit
from engine.reconstruction.media import inspect_video
from engine.reconstruction.service import Reconstruction, TERMINAL
from engine.reconstruction.specification import empty_spec, questions, required, values
from engine.reconstruction.store import Store, digest, redact
from engine.reconstruction.validator import project, visual_checks


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'MOCK')
    monkeypatch.setenv('NEBIUS_API_KEY', '')
    monkeypatch.setenv('DEVIN_API_KEY', 'offline-test-credential')
    monkeypatch.setenv('DEVIN_MAX_RETRIES', '100')
    monkeypatch.setenv('DEVIN_MAX_WALL_SECONDS', '14400')
    monkeypatch.delenv('DEVIN_MAX_ACU', raising=False)


def spec_for(family='box', cavity='solid'):
    d = {'box': dict(length=20, width=16, height=6), 'ring': dict(outer_diameter=40, inner_diameter=30, height=6),
         'cylinder': dict(diameter=20, height=6)}[family]
    if cavity != 'solid' and family == 'box': d['wall_thickness'] = 2
    if cavity != 'solid' and family == 'cylinder': d['inner_diameter'] = 12
    if cavity == 'blind': d['cavity_depth'] = 4
    return ReferenceSpec(family=family, cavity='through' if family=='ring' else cavity, profile='plain', confirmed=True,
        dimensions={k: SuppliedMeasurement(value_mm=v, original_value=v, original_unit='mm', source_text=f'{k} {v} mm', message_id='synthetic', confirmed=True) for k,v in d.items()})


def synthetic_video(path, survivor=None):
    """Plain-background synthetic test clip, not a captured real object."""
    r = np.diag([1., -1., -1.])
    view = {'K': [[600.,0,160.],[0,600.,120.],[0,0,1.]], 'R': r.tolist(), 't_mm': [0,0,80.]}
    image = np.full((240,320,3), 255, np.uint8)
    if survivor is None:
        cv2.rectangle(image,(75,55),(150,170),(10,160,210),-1)
    else:
        image[project(survivor,view,image.shape[:2])] = (10,160,210)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (320,240))
    for _ in range(10): writer.write(image)
    writer.release()
    return view


@pytest.fixture
def media(tmp_path):
    survivor = trimesh.creation.box([10,16,6]); survivor.apply_translation([-5,0,3])
    repair = trimesh.creation.box([10,16,6]); repair.apply_translation([5,0,3])
    path = tmp_path/'synthetic.mp4'
    view = synthetic_video(path,survivor)
    metadata = inspect_video(path,tmp_path/'frames')
    return metadata, view, repair, survivor


class Double:
    """In-process remote double. All failures deliberately injected as tests."""
    def __init__(self, media, bad_first=False, always_bad=False):
        self.media, self.bad_first, self.always_bad = media, bad_first, always_bad
        self.created, self.messages, self.uploads, self.stops = [], [], [], []
        self.needs_input = False
        self.missing_artifact = None
        self.fail_create = False
        self.poll_error = False
    def __call__(self, store, job):
        self.store, self.job = store, job
        return self
    def upload(self,path):
        self.uploads.append((Path(path).name, digest(Path(path))))
        return 'https://api.devin.ai/v1/attachments/test/'+Path(path).name
    def create(self,prompt):
        self.created.append(prompt)
        if self.fail_create: raise ProviderError('TIMEOUT','Injected uncertain create')
        return {'session_id':'test-session','url':'https://app.devin.ai/test'}
    def recover(self): return 'test-session' if self.created else None
    def terminate(self): self.stops.append(self.job['session_id'])
    def message(self,message): self.messages.append(message)
    def poll(self):
        if self.poll_error: raise ProviderError('PROVIDER_FAILED','Injected transport failure')
        return {'status_enum':'working', 'structured_output': {'status':'needs_input' if self.needs_input else 'candidate_ready', 'attempt':self.job['attempt'], 'missing_inputs':['Show the hidden boundary.'] if self.needs_input else [],
            'artifacts':{n:None if n==self.missing_artifact else 'https://api.devin.ai/v1/attachments/test/'+n for n in ARTIFACT_NAMES}}}
    def download(self,url,path):
        name = url.rsplit('/',1)[-1]
        metadata, view, repair, survivor = self.media
        folder = self.store.revision_dir(self.job)/'reference'
        if name == 'repair_part.stl':
            if self.always_bad or (self.bad_first and self.job['attempt']==1):
                Path(path).write_bytes(b'DELIBERATELY INVALID TEST ARTIFACT')
            else: Path(path).write_bytes(repair.export(file_type='stl'))
        elif name == 'surviving_estimate.stl': Path(path).write_bytes(survivor.export(file_type='stl'))
        elif name == 'summary.json':
            data = {'status':'candidate_ready','units':'mm','supplied_dimensions':values(ReferenceSpec.model_validate(self.job['spec'])),
                'observed_geometry':['SYNTHETIC TEST BOX'], 'assumptions':[], 'coordinate_frame':{'artifact_to_reference':np.eye(4).tolist()},
                'candidate_dimensions_mm':dict(zip(['x','y','z'],repair.extents)), 'missing_inputs':[], 'changes_from_previous':['test correction'] if self.job['attempt']>1 else [], 'artifacts':{},
                'reference_sha256':digest(folder/'reference_full.stl'), 'reference_revision':self.job['revision'], 'attempt':self.job['attempt'], 'limitations':['synthetic provider double'], 'unresolved_uncertainty':[]}
            Path(path).write_text(json.dumps(data))
        elif name == 'evidence.json':
            Path(path).write_text(json.dumps({'video_decode':{'sha256':metadata['sha256'],'duration_s':metadata['duration_s'], 'decoder':'OFFLINE DOUBLE', 'decoded_frame_count':10, 'frames':[{'timestamp_s':.1,'sha256':'test'}]},
                'views':[{**view,'frame_index':0},{**view,'frame_index':8}]}))
        else:
            Path(path).write_text('# SYNTHETIC TEST: inert artifact.\nraise RuntimeError("NEVER EXECUTE ON SERVER")\n')


def ready_service(tmp_path, media, **options):
    fake = Double(media, **options)
    service = Reconstruction(Store(tmp_path/'runs'), provider_factory=fake)
    job = service.new()
    job.update(video=media[0], spec=spec_for().model_dump(), status='AWAITING_CONFIRMATION', user_goal='SYNTHETIC: missing box half')
    job['spec']['confirmed'] = False
    service.store.save(job)
    service.confirm(job['job_id'],job['revision'])
    return service, fake, job['job_id']


def run_until(service, job_id, statuses=TERMINAL, max_steps=1200):
    for _ in range(max_steps):
        job = service.store.load(job_id)
        if job['status'] in statuses: return job
        job['next_poll'] = 0
        service.store.save(job)
        service.tick(job_id)
    raise AssertionError('State machine did not settle: '+str(service.store.load(job_id)['status']))


@pytest.mark.parametrize('text', ['Create the missing part of this ring', 'The ring looks like 40 mm', 'ring OD 40', 'ring OD maybe 40 mm', 'ring OD 40 mm or 42 mm'])
def test_no_unmeasured_dimensions(text):
    spec, issues = supplied_edit(empty_spec(),text,'message1')
    assert all(d.value_mm is None for d in spec.dimensions.values())
    assert questions(spec) or issues


def test_measurement_grounding_units_and_confirmation():
    spec, issues = supplied_edit(empty_spec(),'plain ring outer diameter 4 cm, inner diameter 30 mm, height 0.25 inch','message1')
    assert not issues and not questions(spec)
    assert values(spec)=={'outer_diameter':40,'inner_diameter':30,'height':6.35}
    assert not spec.confirmed and not any(d.confirmed for d in spec.dimensions.values())
    assert spec.dimensions['height'].message_id=='message1'
    spec, issues = supplied_edit(spec,'outer diameter 42 mm','message2')
    assert issues and spec.dimensions['outer_diameter'].value_mm is None
    spec, issues = supplied_edit(spec,'correct outer diameter to 42 mm','message3')
    assert not issues and spec.dimensions['outer_diameter'].value_mm==42


@pytest.mark.parametrize('section', [
    'rectangular cross section 0.9cmx0.6cm',
    'rectangular section 9 x 6 mm',
    'rectangular section 6mm × 0.9cm',
    'rectangular section 0,6 x 0,9 cm',
])
def test_ring_radii_and_section_keep_metric_provenance(section):
    text = 'Build the missing part of this ring of outer radius 4cm inner radius 3.4cm and '+section
    spec, issues = supplied_edit(empty_spec(), text, 'measured-request')
    assert not issues and not questions(spec)
    assert values(spec) == {'outer_diameter': 80, 'inner_diameter': 68, 'height': 9}
    assert spec.profile == 'plain' and spec.cavity == 'through'
    outer = spec.dimensions['outer_diameter']
    assert outer.original_value == 4 and outer.original_unit == 'cm'
    assert outer.source_text.strip() == 'outer radius 4cm'
    assert outer.message_id == 'measured-request'
    assert spec.dimensions['height'].source_text == text
    assert not spec.confirmed and not any(d.confirmed for d in spec.dimensions.values())


def test_radius_and_diameter_must_agree():
    spec, issues = supplied_edit(empty_spec(),
        'plain ring outer radius 4 cm outer diameter 70 mm inner radius 3.4 cm height 9 mm', 'conflict')
    assert issues and spec.dimensions['outer_diameter'].value_mm is None
    spec, issues = supplied_edit(spec, 'correct outer radius to 4 cm', 'correction')
    assert not issues and not questions(spec)
    assert spec.dimensions['outer_diameter'].value_mm == 80


def test_square_section_and_rejected_rectangular_clarification():
    spec, issues = supplied_edit(empty_spec(),
        'ring outer radius 4cm inner radius 3.4cm square section 6x6mm', 'square-section')
    assert not issues and not questions(spec)
    assert spec.dimensions['height'].value_mm == 6
    spec, issues = supplied_edit(spec, 'not rectangular', 'rejected-profile')
    assert issues and spec.profile is None and questions(spec)
    spec, issues = supplied_edit(spec, 'rectangular, not square', 'corrected-profile')
    assert not issues and not questions(spec)


def test_pending_section_resolves_when_radii_arrive():
    spec, issues = supplied_edit(empty_spec(), 'ring rectangular section 9 x 6 mm', 'section-first')
    assert issues and spec.dimensions['height'].value_mm is None
    spec, issues = supplied_edit(spec, 'outer radius 4 cm inner radius 3.4 cm', 'radii-later')
    assert not issues and not questions(spec)
    assert spec.dimensions['height'].value_mm == 9
    assert spec.dimensions['height'].message_id == 'section-first'


@pytest.mark.parametrize('section', ['9 x 8 mm', '9 x 6', '0 x 6 mm'])
def test_section_cannot_silently_supply_inconsistent_or_unmeasured_height(section):
    spec, issues = supplied_edit(empty_spec(),
        'ring outer radius 4cm inner radius 3.4cm rectangular section '+section, 'bad-section')
    assert issues and spec.dimensions['height'].value_mm is None
    spec, issues = supplied_edit(spec, 'Thanks', 'unrelated-reply')
    assert issues or questions(spec)
    assert spec.dimensions['height'].value_mm is None


def test_cross_section_and_explicit_height_must_agree():
    spec, issues = supplied_edit(empty_spec(),
        'ring outer radius 4cm inner radius 3.4cm rectangular section 9x6mm height 10mm', 'height-conflict')
    assert issues and spec.dimensions['height'].value_mm is None


def test_radius_edit_rechecks_existing_cross_section():
    spec, issues = supplied_edit(empty_spec(),
        'ring outer radius 4cm inner radius 3.4cm rectangular section 9x6mm', 'initial-section')
    assert not issues and not questions(spec)
    spec, issues = supplied_edit(spec, 'correct outer radius to 4.1 cm', 'radius-edit')
    assert questions(spec)
    spec, issues = supplied_edit(spec, 'Thanks', 'unrelated-reply')
    assert questions(spec)
    spec, issues = supplied_edit(spec, 'correct rectangular section to 9x7mm', 'section-edit')
    assert not issues and not questions(spec)


def test_video_instruction_clarification_confirmation_and_reference(tmp_path, media):
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    job.update(status='INGESTING', upload_path=media[0]['path'])
    service.store.save(job)
    service.tick(job['job_id'])
    uploaded = service.store.load(job['job_id'])
    assert uploaded['status'] == 'AWAITING_INPUT'
    assert uploaded['messages'][-1]['text'] == 'Video received. What would you like me to do?'
    assert all(d['value_mm'] is None for d in uploaded['spec']['dimensions'].values())

    instruction = 'build the missing part of this ring of outer radius 4cm inner radius 3.4cm and square cross section 0.9cmx0.6cm'
    draft = service.turn(job['job_id'], uploaded['revision'], instruction, 'instruction-1')
    assert values(draft.spec) == {'outer_diameter': 80, 'inner_diameter': 68, 'height': 9}
    assert draft.status == 'AWAITING_INPUT' and draft.spec.profile is None
    assert any('rectangular, not square' in q for q in draft.questions)
    assert not draft.reference and not draft.result and draft.session_id is None
    with pytest.raises(ValueError):
        service.confirm(job['job_id'], draft.revision)
    clarified = service.turn(job['job_id'], draft.revision, 'rectangular section', 'clarification-1')
    assert clarified.status == 'AWAITING_CONFIRMATION' and not clarified.questions
    assert not clarified.spec.confirmed and not clarified.reference
    service.confirm(job['job_id'], clarified.revision)
    ready = run_until(service, job['job_id'])
    assert ready['status'] == 'MOCK_REFERENCE_READY'
    assert {a['name'] for a in ready['reference']} == {'reference_full.stl', 'reference_full.step', 'specification.json'}
    assert ready['session_id'] is None and not ready['result']
    assert not any('Sending the original video' in m['text'] for m in ready['messages'])
    mesh = trimesh.load_mesh(service.store.revision_dir(ready)/'reference/reference_full.stl')
    assert np.allclose(mesh.extents, [80, 80, 9], atol=.1)


class ReferenceModelDouble:
    def __init__(self, replies=None):
        self.replies = replies
        self.tools = []
        self.calls = []

    def bind_tools(self, tools, **options):
        self.tools.append((tools[0], options))
        return self

    def invoke(self, messages):
        self.calls.append(list(messages))
        if self.replies is not None:
            reply = self.replies[len(self.calls)-1]
            if isinstance(reply, Exception):
                raise reply
            return reply
        return AIMessage(content='', id='offline-reference-model',
            tool_calls=[{'name': self.tools[-1][0].name, 'args': {}, 'id': 'offline-tool-call'}])


def test_live_video_greeting_does_not_wait_for_nebius(tmp_path, media, monkeypatch):
    def unavailable():
        raise AssertionError('Video ingestion must not call Nebius.')

    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', unavailable)
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    job.update(status='INGESTING', upload_path=media[0]['path'])
    service.store.save(job)
    service.tick(job['job_id'])
    uploaded = service.store.load(job['job_id'])
    assert uploaded['status'] == 'AWAITING_INPUT'
    assert uploaded['messages'][-1]['text'] == 'Video received. What would you like me to do?'
    assert uploaded['video']['sha256'] == media[0]['sha256']
    assert len(uploaded['video']['frames']) == 12
    assert not uploaded['observations'] and not uploaded['reference']
    assert uploaded['session_id'] is None


def test_live_missing_part_request_builds_full_reference_via_agent_before_devin(tmp_path, media, monkeypatch):
    llm = ReferenceModelDouble()
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    devin = Double(media)
    service = Reconstruction(Store(tmp_path/'runs'), provider_factory=devin)
    job = service.new()
    job.update(status='AWAITING_INPUT', video=media[0])
    service.store.save(job)
    instruction = 'Build the missing part of this ring with rectangular cross section, outer diameter 40 mm, inner diameter 36 mm and height 9 mm.'
    draft = service.turn(job['job_id'], job['revision'], instruction, 'operator-measurements')
    assert draft.status == 'AWAITING_CONFIRMATION'
    assert draft.user_goal == instruction and not draft.reference and not draft.spec.confirmed
    assert values(draft.spec) == {'outer_diameter': 40, 'inner_diameter': 36, 'height': 9}
    assert all(draft.spec.dimensions[key].message_id == 'operator-measurements' for key in required(draft.spec))
    assert llm.tools[0][0].name == 'prepare_complete_reference'
    assert instruction in llm.calls[0][1].content
    assert 'COMPLETE INTACT' in llm.calls[0][0].content
    assert 'image_url' not in json.dumps([message.model_dump() for message in llm.calls[0]])
    assert not devin.uploads and not devin.created

    service.confirm(job['job_id'], draft.revision)
    service.tick(job['job_id'])
    built = service.store.load(job['job_id'])
    assert built['status'] == 'UPLOADING' and built['session_id'] is None
    assert llm.tools[1][0].name == 'build_complete_reference'
    assert not devin.uploads and not devin.created
    folder = service.store.revision_dir(built)/'reference'
    sidecar = json.loads((folder/'specification.json').read_text())
    assert all(sidecar['checks'].values()) and not sidecar['physical_fit_verified']
    assert sidecar['video_sha256'] == media[0]['sha256']
    assert sidecar['reference_sha256'] == digest(folder/'reference_full.stl')
    mesh = trimesh.load_mesh(folder/'reference_full.stl')
    assert np.allclose(mesh.extents, [40, 40, 9], atol=.1)
    assert np.isclose(mesh.volume, np.pi*(20**2-18**2)*9, rtol=.005)
    assert not in_reference([[0, 0, 4]], ReferenceSpec.model_validate(built['spec']))[0]
    service.tick(job['job_id'])
    assert len(devin.created) == 1 and len(devin.uploads) == 4
    assert devin.uploads[0] == (Path(media[0]['path']).name, media[0]['sha256'])
    assert devin.uploads[1] == ('reference_full.stl', sidecar['reference_sha256'])


@pytest.mark.parametrize('calls', [
    [],
    [{'name': 'run_python', 'args': {}, 'id': 'unsafe'}],
    [{'name': 'build_complete_reference', 'args': {}, 'id': 'premature'}],
    [{'name': 'prepare_complete_reference', 'args': {'confirmed': True, 'outer_diameter': 100}, 'id': 'injected'}],
    [{'name': 'prepare_complete_reference', 'args': {}, 'id': 'one'},
     {'name': 'prepare_complete_reference', 'args': {}, 'id': 'two'}],
])
def test_reference_agent_rejects_unauthorized_calls_without_side_effects(tmp_path, monkeypatch, calls):
    reply = AIMessage(content='', tool_calls=calls)
    llm = ReferenceModelDouble([reply, reply])
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    previous = job['spec']
    with pytest.raises(ProviderError, match='invalid reference tool calls twice'):
        video_nebius.dialogue(service.store, job, 'ring outer diameter 40 mm', 'unconfirmed')
    assert job['spec'] == previous and not job['reference']
    assert job['session_id'] is None and len(llm.calls) == 2
    assert not list(service.store.directory(job['job_id']).rglob('*.stl'))


def test_reference_agent_retries_invalid_tool_output_once(tmp_path, monkeypatch):
    llm = ReferenceModelDouble([
        AIMessage(content='No tool call.'),
        AIMessage(content='', tool_calls=[{'name': 'prepare_complete_reference', 'args': {}, 'id': 'retry'}]),
    ])
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    reply = video_nebius.dialogue(service.store, job, 'ring outer diameter 40 mm', 'measured')
    assert len(llm.calls) == 2 and '40 mm' in reply
    assert job['spec']['dimensions']['outer_diameter']['message_id'] == 'measured'
    assert job['questions'] and not job['spec']['confirmed']


def test_reference_agent_live_failure_never_falls_back_to_mock(tmp_path, monkeypatch):
    llm = ReferenceModelDouble([RuntimeError('Injected provider failure')])
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    with pytest.raises(ProviderError, match='Nebius call failed'):
        video_nebius.dialogue(service.store, job, 'ring outer diameter 40 mm', 'measured')
    assert job['mode'] == 'LIVE' and len(llm.calls) == 1
    assert not job['reference'] and job['spec']['dimensions']['outer_diameter']['value_mm'] is None


def test_reference_agent_cannot_build_without_operator_confirmation(tmp_path, monkeypatch):
    llm = ReferenceModelDouble()
    monkeypatch.setenv('RECONSTRUCTION_MODE', 'LIVE')
    monkeypatch.setattr(video_nebius, 'reference_model', lambda: llm)
    service = Reconstruction(Store(tmp_path/'runs'))
    job = service.new()
    job.update(status='QUEUED', spec=spec_for().model_dump())
    job['spec']['confirmed'] = False
    with pytest.raises(ValueError, match='Confirm the complete specification'):
        video_nebius.construct_reference(service.store, job, build_reference)
    assert not list(service.store.directory(job['job_id']).rglob('*.stl'))


@pytest.mark.parametrize('family,cavity', [('ring','through'),('cylinder','solid'),('cylinder','through'),('cylinder','blind'),('box','solid'),('box','through'),('box','blind')])
def test_complete_reference_templates(tmp_path,family,cavity):
    spec=spec_for(family,cavity)
    sidecar=build_reference(spec,tmp_path,7,'test-video')
    assert all(sidecar['checks'].values())
    assert sidecar['reference_revision']==7
    assert sidecar['provenance'].startswith('Only independently supplied')
    if cavity=='through': assert not in_reference([[0,0,3]],spec)[0]
    if cavity=='blind': assert in_reference([[0,0,1]],spec)[0] and not in_reference([[0,0,4]],spec)[0]


def test_reference_rejects_missing_unconfirmed_and_hollow_ambiguity(tmp_path):
    spec,issues=supplied_edit(empty_spec(),'hollow cylinder diameter 20 mm height 6 mm','m')
    assert spec.cavity is None and questions(spec)
    with pytest.raises(ValueError): build_reference(spec,tmp_path,1,'video')
    spec=spec_for();spec.confirmed=False
    with pytest.raises(ValueError): build_reference(spec,tmp_path,1,'video')


def test_media_real_bytes_and_metadata(media,tmp_path):
    metadata=media[0]
    assert len(metadata['frames'])==12 and metadata['duration_s']==1
    assert all(Path(f['path']).exists() for f in metadata['frames'])
    bad=tmp_path/'not-video.mp4';bad.write_text('not video')
    with pytest.raises(ValueError,match='cannot be decoded'): inspect_video(bad,tmp_path/'bad')
    with bad.open('wb') as f: f.truncate(512*1024*1024+1)
    with pytest.raises(ValueError,match='512'): inspect_video(bad,tmp_path/'large')


def test_validated_complete_reference_is_uploaded_before_devin_starts(tmp_path, media, monkeypatch):
    service, fake, job_id = ready_service(tmp_path, media)
    assert service.store.load(job_id)['status'] == 'QUEUED'
    assert not fake.uploads and not fake.created

    service.tick(job_id)
    built = service.store.load(job_id)
    assert built['status'] == 'UPLOADING' and built['session_id'] is None
    assert not fake.uploads and not fake.created
    folder = service.store.revision_dir(built)
    reference = folder/'reference'
    sidecar = json.loads((reference/'specification.json').read_text())
    assert all(sidecar['checks'].values())
    assert sidecar['specification'] == built['spec']
    assert sidecar['reference_revision'] == built['revision']
    assert sidecar['video_sha256'] == media[0]['sha256']
    assert sidecar['reference_sha256'] == digest(reference/'reference_full.stl')
    assert np.allclose(trimesh.load_mesh(reference/'reference_full.stl').extents, [20, 16, 6])
    assert not built['result']

    create = fake.create

    def create_with_complete_proof(prompt):
        expected = [Path(media[0]['path']), reference/'reference_full.stl',
                    reference/'specification.json', folder/'frame-manifest.json']
        assert fake.uploads == [(path.name, digest(path)) for path in expected]
        assert all(f'ATTACHMENT:"https://api.devin.ai/v1/attachments/test/{path.name}"' in prompt
                   for path in expected)
        assert 'COMPLETE INTACT object' in prompt
        assert 'Reconstruct missing = intact reference minus observed surviving material.' in prompt
        return create(prompt)

    monkeypatch.setattr(fake, 'create', create_with_complete_proof)
    service.tick(job_id)
    assert service.store.load(job_id)['status'] == 'WORKING'
    assert len(fake.created) == 1


@pytest.mark.parametrize('reason', [
    'Reference generation failed.',
    "Reference validation failed: {'closed': False}",
])
def test_failed_reference_stops_before_devin_handoff(tmp_path, media, monkeypatch, reason):
    service, fake, job_id = ready_service(tmp_path, media)

    def failed_reference(spec, folder, revision, video_hash):
        raise ValueError(reason)

    monkeypatch.setattr('engine.reconstruction.service.build_reference', failed_reference)
    service.tick(job_id)
    job = service.store.load(job_id)
    assert job['status'] == 'FAILED' and reason in job['terminal_reason']
    assert not job['reference'] and job['session_id'] is None
    assert not fake.uploads and not fake.created


def test_measurement_change_before_handoff_requires_a_new_reference(tmp_path, media):
    service, fake, job_id = ready_service(tmp_path, media)
    service.tick(job_id)
    built = service.store.load(job_id)
    assert built['status'] == 'UPLOADING'
    changed = service.turn(job_id, built['revision'], 'correct length to 22 mm', 'before-handoff')
    assert changed.status == 'AWAITING_CONFIRMATION' and not changed.reference
    assert changed.revision == built['revision'] + 1
    service.tick(job_id)
    assert not fake.uploads and not fake.created
    service.confirm(job_id, changed.revision)
    service.tick(job_id)
    rebuilt = service.store.load(job_id)
    assert rebuilt['status'] == 'UPLOADING' and not fake.uploads
    reference = service.store.revision_dir(rebuilt)/'reference'
    assert np.allclose(trimesh.load_mesh(reference/'reference_full.stl').extents, [22, 16, 6])


def test_full_feedback_path_with_injected_invalid_stl(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media,bad_first=True)
    job=run_until(service,id)
    assert job['status']=='ACCEPTED',job.get('validation')
    assert job['attempt']==2 and job['retries']==1 and len(fake.created)==1 and len(fake.messages)==1
    assert len(fake.uploads)==4
    assert ('synthetic.mp4',media[0]['sha256']) in fake.uploads
    root=service.store.revision_dir(job)
    report=(root/'attempts/1/validator.json').read_text()
    assert report in fake.messages[0]
    assert (root/'attempts/1/repair_part.stl').read_bytes()==b'DELIBERATELY INVALID TEST ARTIFACT'
    assert (root/'attempts/2/generation.py').exists()
    assert job['validation']['visual_reconstruction_confidence']=='SUPPORTED_BY_SAMPLED_VIEWS'
    events=[json.loads(l) for l in (service.store.directory(id)/'events.jsonl').read_text().splitlines()]
    assert {'reference_built','runtime_prompt','session_created','candidate_fetched','validation','correction'} <= {e['event'] for e in events}
    assert all('reference_revision' in e and 'retry' in e for e in events)
    assert next(i for i,e in enumerate(events) if e['event']=='reference_built') < next(i for i,e in enumerate(events) if e['event']=='session_created')


def test_early_success_no_correction(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    job=run_until(service,id)
    assert job['status']=='ACCEPTED',job['validation']
    assert job['attempt']==1 and job['retries']==0 and not fake.messages


@pytest.mark.parametrize(('pixel_offset', 'accepted'), [(12, True), (20, False)])
def test_demo_silhouettes_allow_approximation_but_reject_large_offsets(tmp_path, media, pixel_offset, accepted):
    video, view, repair, survivor = media
    reference = trimesh.util.concatenate([repair, survivor])
    camera = {**view, 'K': np.asarray(view['K']).copy()}
    camera['K'][0, 2] += pixel_offset
    evidence = {'views': [{**camera, 'frame_index': i} for i in (0, 8)]}
    passed, views = visual_checks(reference, repair, survivor, evidence, video, tmp_path)
    assert passed is accepted
    assert len(views) == 2
    if accepted:
        assert all(.70 <= result['silhouette_iou'] < .85 for result in views)
    else:
        assert all(result['silhouette_iou'] < .70 for result in views)


@pytest.mark.parametrize('missing_inputs', [[], ['Show the hidden boundary.']])
def test_demo_retains_uncertainty_without_accepting_outstanding_input(tmp_path, media, missing_inputs):
    service, fake, id = ready_service(tmp_path, media)
    job = run_until(service, id, {'VALIDATING'})
    path = Path(job['candidate'])/'summary.json'
    summary = json.loads(path.read_text())
    summary['unresolved_uncertainty'] = ['Fracture surface approximated from the visible outline.']
    summary['missing_inputs'] = missing_inputs
    path.write_text(json.dumps(summary))
    job = run_until(service, id, {'ACCEPTED', 'CORRECTION_PENDING'})
    assert job['status'] == ('CORRECTION_PENDING' if missing_inputs else 'ACCEPTED')
    assert job['validation']['validation_profile'] == 'approximate_demo'
    assert job['validation']['unresolved_uncertainty'] == summary['unresolved_uncertainty']
    assert job['validation']['physical_fit_verified'] is False
    assert job['validation']['mesh_validity'] and job['validation']['reference_consistency']


def test_100_retry_boundary_and_restart(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media,always_bad=True)
    # Cheap double validator here: counter persistence, not mesh performance.
    failing=lambda f,r,j: {'accepted':False,'checks':[{'name':'INJECTED_TEST_FAILURE','passed':False,'measured':1,'tolerance':0,'units':'mm'}],'attempt':j['attempt'],'alignment':None,'units':'mm'}
    service.validator=failing
    run_until(service,id,{'CORRECTION_PENDING'})
    before=service.store.load(id)
    assert before['retries']==1
    service=Reconstruction(service.store,provider_factory=fake,validator=failing)
    job=run_until(service,id)
    assert job['status']=='RETRY_EXHAUSTED'
    assert job['attempt']==101 and job['retries']==100
    assert len(fake.messages)==100 and len(fake.created)==1
    assert len(list((service.store.revision_dir(job)/'attempts').iterdir()))==101


def test_duplicate_confirmation_and_uncertain_create(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    fake.fail_create=True
    revision=service.store.load(id)['revision']
    service.confirm(id,revision);service.confirm(id,revision)
    run_until(service,id,{'SESSION_UNCERTAIN'})
    service=Reconstruction(service.store,provider_factory=fake)
    job=run_until(service,id)
    assert job['status']=='ACCEPTED' and len(fake.created)==1


def test_stale_input_hides_results_and_preserves_history(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    old=run_until(service,id)
    changed=service.turn(id,old['revision'],'correct length to 22 mm','request-change-1')
    assert changed.revision==old['revision']+1 and not changed.result and not changed.reference
    assert changed.session_id is None and not changed.spec.confirmed
    assert (service.store.directory(id)/'revisions'/str(old['revision'])/'attempts/1/repair_part.stl').exists()
    assert service.turn(id,old['revision'],'correct length to 22 mm','request-change-1').revision==changed.revision
    with pytest.raises(ValueError):service.confirm(id,old['revision'])


def test_wait_for_missing_evidence_does_not_burn_retry(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    fake.needs_input=True
    job=run_until(service,id,{'WAITING_INPUT'})
    for _ in range(5):service.tick(id)
    assert service.store.load(id)['retries']==0
    resumed=service.turn(id,job['revision'],'The back boundary is visible near the end.','additional-evidence')
    assert resumed.status=='RESUME_PENDING' and resumed.session_id=='test-session' and resumed.revision==job['revision']
    fake.needs_input=False
    accepted=run_until(service,id)
    assert accepted['status']=='ACCEPTED' and accepted['retries']==0


def test_missing_artifact_routes_to_same_session(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    fake.missing_artifact='surviving_estimate.stl'
    job=run_until(service,id,{'CORRECTION_PENDING'})
    assert job['retries']==1 and not job['result']
    assert 'surviving_estimate.stl' in job['validation']['checks'][0]['measured']
    fake.missing_artifact=None
    assert run_until(service,id)['status']=='ACCEPTED'


@pytest.mark.parametrize('uncertain_delivery', [False, True])
def test_resume_ignores_answered_input_while_working_after_restart(tmp_path, media, monkeypatch, uncertain_delivery):
    service, fake, id = ready_service(tmp_path, media)
    fake.needs_input = True
    before = run_until(service, id, {'WAITING_INPUT'})
    reference_hash = digest(service.store.revision_dir(before)/'reference/reference_full.stl')
    service.turn(id, before['revision'], 'Use the confirmed dimensions unchanged for an approximate reconstruction.', 'clarification')
    assert 'Resuming reconstruction' in service.store.load(id)['messages'][-1]['text']
    if uncertain_delivery:
        def message(text):
            fake.messages.append(text)
            raise ProviderError('TIMEOUT', 'Injected uncertain clarification delivery')
        monkeypatch.setattr(fake, 'message', message)
    run_until(service, id, {'WORKING'})
    service = Reconstruction(service.store, provider_factory=fake)
    for _ in range(3):
        job = service.store.load(id)
        job['next_poll'] = 0
        service.store.save(job)
        service.tick(id)
        assert service.store.load(id)['status'] == 'WORKING'
        assert service.store.load(id)['questions'] == []
    fake.needs_input = False
    accepted = run_until(service, id)
    assert accepted['status'] == 'ACCEPTED'
    assert accepted['revision'] == before['revision'] and accepted['session_id'] == before['session_id']
    assert accepted['attempt'] == before['attempt'] and accepted['retries'] == before['retries']
    assert digest(service.store.revision_dir(accepted)/'reference/reference_full.stl') == reference_hash
    assert len(fake.created) == 1 and len(fake.messages) == 1
    assert 'answered_input' not in accepted


@pytest.mark.parametrize(('remote_status', 'question'), [
    ('working', 'Show the opposite face.'),
    ('blocked', 'Show the hidden boundary.'),
])
def test_resumed_session_can_request_more_input(tmp_path, media, monkeypatch, remote_status, question):
    service, fake, id = ready_service(tmp_path, media)
    fake.needs_input = True
    before = run_until(service, id, {'WAITING_INPUT'})
    service.turn(id, before['revision'], 'The back boundary is visible near the end.', 'clarification')
    run_until(service, id, {'WORKING'})
    original_poll = fake.poll
    def poll():
        response = original_poll()
        response['status_enum'] = remote_status
        response['structured_output']['missing_inputs'] = [question]
        return response
    monkeypatch.setattr(fake, 'poll', poll)
    waiting = run_until(service, id, {'WAITING_INPUT'})
    assert waiting['questions'] == [question] and waiting['retries'] == 0
    assert len(fake.created) == 1 and len(fake.messages) == 1


def test_wall_time_and_provider_errors_are_not_exhaustion(tmp_path,media):
    service,fake,id=ready_service(tmp_path,media)
    job=service.store.load(id);job['started_at']=time.time()-20000;service.store.save(job)
    service.tick(id)
    assert service.store.load(id)['status']=='TIME_LIMIT' and not fake.created
    service,fake,id=ready_service(tmp_path/'other',media)
    run_until(service,id,{'WORKING'});fake.poll_error=True
    job=run_until(service,id)
    assert job['status']=='FAILED' and job['retries']==0 and len(fake.created)==1


def test_secret_redaction_retains_usage(monkeypatch):
    secret='test-secret-value-that-must-not-leak'
    monkeypatch.setenv('NEBIUS_API_KEY',secret)
    data=redact({'Authorization':'Bearer '+secret,'body':secret+' https://storage.googleapis.com/b/f?X-Goog-Signature=abc',
                 'image':'data:image/jpeg;base64,YWJj','usage':{'prompt_tokens':12,'completion_tokens':8}})
    assert secret not in json.dumps(data) and 'Signature=abc' not in json.dumps(data) and 'YWJj' not in json.dumps(data)
    assert data['usage']['prompt_tokens']==12


def test_live_devin_fails_without_mock_fallback(tmp_path,media,monkeypatch):
    service,fake,id=ready_service(tmp_path,media)
    job=service.store.load(id)
    client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(503,json={'error':'test failure'})))
    provider=Devin(service.store,job,client=client)
    with pytest.raises(ProviderError):provider.create('test')
    assert 'provider_response' in (service.store.directory(id)/'events.jsonl').read_text()


@pytest.mark.parametrize('url',['http://localhost/private','https://evil.example/a','https://api.devin.ai/v1/secrets','https://api.devin.ai/v1/attachments/test/name?token=abc'])
def test_artifact_url_restrictions(tmp_path,media,url):
    service,fake,id=ready_service(tmp_path,media)
    p=Devin(service.store,service.store.load(id))
    with pytest.raises(ValueError):p.download(url,tmp_path/'output')
