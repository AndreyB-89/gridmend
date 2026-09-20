import { useCallback, useEffect, useRef, useState } from 'react';
import type { VideoFeature, VideoState } from './types.ts';
import { ModePill, StateMark } from './components/Bits.tsx';
import { RingViewer } from './components/RingViewer.tsx';
import { SectionView } from './components/SectionView.tsx';

const TERMINAL = new Set(['ACCEPTED', 'FAILED', 'RETRY_EXHAUSTED', 'TIME_LIMIT', 'PROVIDER_LIMIT', 'STALE', 'MOCK_REFERENCE_READY']);
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || `Request failed (${res.status}).`);
  return data as T;
}
const post = <T,>(url: string, data: unknown) => request<T>(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});

export function useVideo() {
  const [job, setJob] = useState<VideoState | null>(null);
  const [active, setActive] = useState(!!localStorage.getItem('gridmend-video-job'));
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const current = useRef<VideoState | null>(null);
  const pending = useRef(false);
  const update = useCallback((data: VideoState) => { current.current = data; setJob(data); }, []);
  useEffect(() => {
    const id = localStorage.getItem('gridmend-video-job');
    const g = generation.current;
    if (id) void request<VideoState>(`/api/reconstructions/${id}`).then(data => { if (g === generation.current) update(data); }).catch(e => setError(String(e.message)));
  }, [update]);
  useEffect(() => {
    if (!job || TERMINAL.has(job.status)) return;
    let alive = true;
    let timer: number;
    const g = generation.current;
    const poll = async () => {
      try {
        const data = await request<VideoState>(`/api/reconstructions/${job.job_id}`);
        if (alive && g === generation.current && !pending.current && data.revision >= (current.current?.revision ?? 0)) update(data);
      } catch (e) { if (alive) setError((e as Error).message); }
      if (alive) timer = window.setTimeout(poll, 2000);
    };
    timer = window.setTimeout(poll, 1000);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [job?.job_id, job?.status, update]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const clear = async () => {
    generation.current++;
    const old = current.current;
    current.current = null; setJob(null); setActive(false); setPreview(null); setError(null);
    localStorage.removeItem('gridmend-video-job');
    if (old) await post(`/api/reconstructions/${old.job_id}/invalidate`, {});
  };
  const upload = async (file: File) => {
    try {
      await clear();
      const g = generation.current;
      setActive(true); setBusy(true); setPreview(URL.createObjectURL(file));
      const fd = new FormData(); fd.append('video', file);
      const data = await request<VideoState>('/api/reconstructions', {method: 'POST', body: fd});
      if (g !== generation.current) { await post(`/api/reconstructions/${data.job_id}/invalidate`, {}); return; }
      localStorage.setItem('gridmend-video-job', data.job_id); update(data);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };
  const send = async (text: string) => {
    const j = current.current;
    if (!j || pending.current) return;
    pending.current = true; setBusy(true); setError(null);
    const g = generation.current;
    update({...j, reference: [], result: []});
    try {
      const data = await post<VideoState>(`/api/reconstructions/${j.job_id}/messages`, {revision: j.revision, message: text, request_id: crypto.randomUUID()});
      if (g === generation.current) update(data);
    } catch (e) { setError((e as Error).message); }
    finally { pending.current = false; setBusy(false); }
  };
  const confirm = async () => {
    const j = current.current;
    if (!j || pending.current) return;
    pending.current = true; setBusy(true); setError(null);
    const g = generation.current;
    try { const data = await post<VideoState>(`/api/reconstructions/${j.job_id}/confirm`, {revision: j.revision}); if (g === generation.current) update(data); }
    catch (e) { setError((e as Error).message); }
    finally { pending.current = false; setBusy(false); }
  };
  return {job, active, preview, busy, error, upload, clear, send, confirm};
}
export type VideoControl = ReturnType<typeof useVideo>;

export function VideoPreview({video, onUpload}: {video: VideoControl; onUpload: (file: File | undefined) => void}) {
  return <><div className="canvas-wrap">{video.preview ? <video src={video.preview} controls playsInline style={{width: '100%', maxHeight: 350, display: 'block'}} /> : <p className="small-note">Original video stored with this reconstruction.</p>}</div>
    <p className="small-note">Video shows shape and damage. Supply the intact object’s measurements in chat. Up to 512 MiB and 180 seconds.</p>
    <div className="change-photo"><label className="link file-link">Change photo or video<input type="file" accept="image/*,video/*,.mov,.mkv" onChange={e => onUpload(e.target.files?.[0])}/></label></div></>;
}
function shapeLabel(family: VideoState['spec']['family'] | undefined) {
  return family === 'open_frustum' ? 'open-top truncated cone (cup)' : family ?? 'shape unknown';
}
function featureKeys(job: VideoState | null): VideoFeature[] {
  const s = job?.spec;
  if (s?.family === 'open_frustum') return ['bottom_diameter', 'top_diameter', 'height', 'wall_thickness', 'bottom_thickness'];
  let keys: VideoFeature[] = s?.family === 'box' ? ['length', 'width', 'height'] : s?.family === 'cylinder' ? ['diameter', 'height'] : ['outer_diameter', 'inner_diameter', 'height'];
  if (s?.family !== 'ring' && s?.cavity && s.cavity !== 'solid') keys.push(s.family === 'box' ? 'wall_thickness' : 'inner_diameter');
  if (s?.cavity === 'blind') keys.push('cavity_depth');
  if (s?.profile === 'inner_groove') keys.push('groove_depth', 'groove_width');
  return keys;
}
export function VideoDimensions({job}: {job: VideoState | null}) {
  return <div className="panel dims"><div className="dims-head"><h2>Dimensions</h2><small>{job?.spec.confirmed ? 'Confirmed' : job?.spec.family === 'open_frustum' ? 'Measurements and design defaults' : 'From your measurements'}</small></div>
    {featureKeys(job).map(k => {const dim=job?.spec.dimensions[k]; return <div className={`dim ${dim?.confirmed ? 'ok' : dim?.value_mm ? 'draft' : 'unknown'}`} key={k}><span className="name">{k.replaceAll('_',' ')}{dim?.source === 'design_default' ? ' (design default)' : ''}</span><span className="val">{dim?.value_mm ?? '?'}<small>mm</small></span><span className="meta"><StateMark state={dim?.confirmed ? 'ok' : dim?.value_mm ? 'draft' : 'unknown'}/></span></div>;})}
    <p className="small-note">Intact {shapeLabel(job?.spec.family)} · {job?.spec.cavity ?? 'cavity not yet specified'} · {job?.spec.profile ?? 'profile not yet specified'}</p>
    {job?.spec.family === 'open_frustum' && <p className="small-note">Outer diameters · radial wall thickness · closed base at Z = 0 · open top at Z = height.</p>}</div>;
}
export function VideoChat({video}: {video: VideoControl}) {
  return <>{video.job?.messages.map((m,i) => <div className={`msg ${m.role === 'user' ? 'me' : 'ai'}`} key={m.id ?? i}><div className="av" aria-hidden="true">{m.role === 'user' ? 'You' : 'AI'}</div><div className="bubble"><p style={{whiteSpace:'pre-wrap'}}>{m.text}</p>{m.role !== 'user' && <ModePill label="Video workflow" mode={m.mode ?? video.job!.mode}/>}</div></div>)}
    {!video.job && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Uploading your video…</p></div></div>}
    {video.job?.status === 'INGESTING' && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Decoding the video and preparing frames for validation…</p></div></div>}
    {video.job?.status === 'AWAITING_CONFIRMATION' && <div className="msg ai draft"><div className="av">AI</div><div className="bubble"><p>Confirm the measurements and intact shape shown above. I will build the complete reference and start reconstruction.</p><div className="bubble-actions"><button className="btn go" disabled={video.busy} onClick={() => void video.confirm()}>Confirm and build</button></div></div></div>}
    {video.error && <div className="msg ai warn"><div className="av">!</div><div className="bubble"><p role="alert">{video.error}</p></div></div>}
    {video.busy && <div className="msg ai"><div className="av">AI</div><div className="bubble"><p>Reading your answer…</p></div></div>}
  </>;
}
const DOWNLOAD_LABEL: Record<string,string> = {'reference_full.stl':'Complete reference STL', 'reference_full.step':'Complete reference STEP', 'specification.json':'Confirmed specification', 'repair_part_aligned.stl':'Missing part STL', 'summary.json':'Reconstruction summary', 'generation.py':'Generation script (download only)', 'requirements.txt':'Script dependencies', 'README.md':'Reproduction instructions', 'evidence.json':'Reconstruction evidence', 'surviving_estimate.stl':'Surviving estimate STL', 'validator.json':'Validation report'};
export function VideoResult({video}: {video: VideoControl}) {
  const j = video.job;
  const full = j?.reference.find(a => a.name === 'reference_full.stl');
  const repair = j?.status === 'ACCEPTED' ? j.result.find(a => a.name === 'repair_part_aligned.stl') : null;
  const d = j?.spec.dimensions;
  const val = (k:VideoFeature) => d?.[k]?.value_mm ?? null;
  return <><div className={`viewer ${full ? 'has-model' : ''}`}><div className="v-top"><div><h2>{repair ? 'Proposed missing part' : full ? 'Complete reference' : 'Reconstruction'}</h2><p className="sub">{j?.status.replaceAll('_',' ').toLowerCase() ?? 'Waiting for video'}</p></div>{j && <ModePill label="Video workflow" mode={j.mode}/>}</div>
    {full ? <RingViewer ringUrl={full.url} segmentUrl={repair?.url ?? null} referenceMode/> : <div className="viewer-empty"><p>No 3D model yet. Confirm the intact shape and measurements first.</p></div>}
    {full && <div className="legend"><span className="pill"><span className="sw y"/>Complete reference</span>{repair && <span className="pill"><span className="sw"/>Proposed missing material</span>}</div>}</div>
    <div className="panel sec-panel">{j?.spec.family === 'ring' ? <SectionView wall={{value: val('outer_diameter') && val('inner_diameter') ? (val('outer_diameter')!-val('inner_diameter')!)/2 : null, state: j.spec.confirmed ? 'ok' : 'unknown'}} thickness={{value:val('height'),state:j.spec.confirmed?'ok':'unknown'}} groove={j.spec.profile==='inner_groove' ? {depth:val('groove_depth'),width:val('groove_width'),state:j.spec.confirmed?'ok':'unknown'} : null} grooveKnown={j.spec.profile==='plain'} profileConfirmed={j.spec.confirmed}/> : <p className="small-note">Complete reference: {shapeLabel(j?.spec.family)}, {j?.spec.cavity ?? 'solid or hollow to confirm'}. Reference dimensions use your measurements and any confirmed design defaults.</p>}</div>
    <div className="panel build"><button className="build-btn" disabled={j?.status !== 'AWAITING_CONFIRMATION' || video.busy} onClick={() => void video.confirm()}>Confirm and build CAD</button>
    {j && <p className="build-note">Candidate {j.attempt} · corrections {j.retries}/{j.max_retries}. Wall limit {Number(j.limits.wall_seconds)/3600} h. {j.limits.max_acu ? `ACU cap ${j.limits.max_acu}.` : 'Uses the configured Devin account limits.'}</p>}
    {full && <div className="dl">{[...(j?.reference ?? []), ...(j?.status === 'ACCEPTED' ? j.result : [])].map(a => <a key={a.url} className={a.name==='repair_part_aligned.stl'?'red':undefined} href={a.url} download>{DOWNLOAD_LABEL[a.name] ?? a.name}</a>)}</div>}
    <p className="honest">70% silhouette overlap required on two views. Proposed missing material is shown in red. No physical fit tested.</p></div></>;
}
