import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiFailure, api, errorMessage, type AutoDetect, type DemoClicks, type Health } from "./api.ts";
import type {
  Dimension,
  GenerateRequest,
  GenerateResult,
  InspectContext,
  InspectResult,
  Point,
  ProfileEditResult,
  Trace,
  VoiceResult,
} from "./types.ts";
import { PhotoCanvas, SET_COLORS, SET_LABEL, type ClickSet, type Clicks } from "./components/PhotoPanel.tsx";
import { TalkBar } from "./components/TalkBar.tsx";
import { RingViewer } from "./components/RingViewer.tsx";
import { MissingPartDownload } from "./components/MissingPartDownload.tsx";
import { Icon, ModePill, SourceChip, TraceTag, originOf, type Origin } from "./components/Bits.tsx";

import { useVideo, VideoPreview, VideoChat, VideoResult } from "./video.tsx";

type DimKey = "outer_diameter" | "inner_diameter" | "thickness";
const DIM_KEYS: DimKey[] = ["outer_diameter", "inner_diameter", "thickness"];
const DIM_LABEL: Record<DimKey, string> = {
  outer_diameter: "Outer diameter",
  inner_diameter: "Inner diameter",
  thickness: "Thickness",
};

const EMPTY_DIM: Dimension = { value_mm: null, source: null, confirmed: false };
const INITIAL_ACCEPTED: GenerateRequest = {
  outer_diameter: EMPTY_DIM,
  inner_diameter: EMPTY_DIM,
  thickness: EMPTY_DIM,
  groove: null,
  profile_rz_mm: null,
  profile_basis: "SIMPLIFIED_RECTANGLE",
  profile_confirmed: false,
  missing_arc_deg: null,
  purpose: "DEMO_CAD_ONLY",
};
const EMPTY_CLICKS: Clicks = { corners: [], outer: [], inner: [] };
const SET_MIN: Record<ClickSet, number> = { corners: 4, outer: 3, inner: 3 };
const SET_MAX: Record<ClickSet, number> = { corners: 4, outer: 60, inner: 60 };
const CORNER_NAMES = ["top-left", "top-right", "bottom-right", "bottom-left"];

type TalkOrigin = "voice" | "typed";
type Item =
  | { id: number; kind: "ai"; text: string; tone?: "warn" | "question" }
  | { id: number; kind: "detect"; det: AutoDetect }
  | { id: number; kind: "inspect"; res: InspectResult }
  | { id: number; kind: "me"; text: string; origin: TalkOrigin; trace: Trace | null; status: "review" | "sent" | "discarded" }
  | {
      id: number;
      kind: "draft";
      res: ProfileEditResult;
      origin: TalkOrigin;
      base: GenerateRequest;
      status: "pending" | "confirmed" | "cancelled";
    };

type NewItem = Item extends infer T ? (T extends Item ? Omit<T, "id"> : never) : never;

interface ErrorState {
  msg: string;
  retry?: () => void;
}

function mm(v: number | null | undefined, digits = 1) {
  return v === null || v === undefined ? "?" : v.toFixed(digits);
}

function sameGroove(a: GenerateRequest["groove"], b: GenerateRequest["groove"]) {
  if (a === null || b === null) return a === b;
  return a.depth_mm === b.depth_mm && a.width_mm === b.width_mm;
}

let nextId = 1;

export default function App() {
  const video = useVideo();
  // ---- global ----
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);

  // ---- photo + points ----
  const [photoFile, setPhotoFile] = useState<Blob | null>(null);
  const [photoName, setPhotoName] = useState("photo.jpg");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [sidePhoto, setSidePhoto] = useState<{ image: Blob; filename: string } | null>(null);
  const [sideUrl, setSideUrl] = useState<string | null>(null);
  const [clicks, setClicks] = useState<Clicks>(EMPTY_CLICKS);
  const [history, setHistory] = useState<Clicks[]>([]);
  const [activeSet, setActiveSet] = useState<ClickSet>("corners");
  const [detecting, setDetecting] = useState(false);
  const [demo, setDemo] = useState<DemoClicks | null>(null);
  const [wholePhoto, setWholePhoto] = useState(false);
  const [cardW, setCardW] = useState("85.60");
  const [cardH, setCardH] = useState("53.98");
  const [sizeConfirmed, setSizeConfirmed] = useState(false);
  const [samePlane, setSamePlane] = useState(false);

  // ---- inspect ----
  const [inspecting, setInspecting] = useState(false);
  const [inspect, setInspect] = useState<InspectResult | null>(null);
  const [inspectItemId, setInspectItemId] = useState<number | null>(null);
  const [showFit, setShowFit] = useState(true);

  // ---- accepted model + conversation ----
  const [accepted, setAccepted] = useState<GenerateRequest>(INITIAL_ACCEPTED);
  const [previous, setPrevious] = useState<GenerateRequest[]>([]);
  const [log, setLog] = useState<Item[]>([]);
  const [editing, setEditing] = useState(false);
  const [typeOpen, setTypeOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [limitations, setLimitations] = useState<string[]>([]);

  // ---- generate ----
  const [generating, setGenerating] = useState(false);
  const [gen, setGen] = useState<GenerateResult | null>(null);
  const dlRef = useRef<HTMLDivElement | null>(null);
  // After a build, bring the downloads into view (short projector screens).
  useEffect(() => {
    if (!gen) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    dlRef.current?.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
  }, [gen]);

  const threadRef = useRef<HTMLDivElement>(null);
  const typeRef = useRef<HTMLInputElement>(null);

  const push = useCallback((item: NewItem) => {
    const id = nextId++;
    setLog((l) => [...l, { ...item, id } as Item]);
    return id;
  }, []);

  const fail = useCallback((what: string, e: unknown, retry?: () => void) => {
    const retryable = e instanceof ApiFailure && (e.status === 502 || e.status === 504 || e.status === 0);
    setError({ msg: `${what}: ${errorMessage(e)}`, retry: retryable ? retry : undefined });
  }, []);

  const showError = useCallback((msg: string) => setError({ msg }), []);

  // ---- health polling ----
  useEffect(() => {
    let alive = true;
    const poll = () =>
      api
        .health()
        .then((h) => {
          if (!alive) return;
          setHealth(h);
          setHealthError(false);
        })
        .catch(() => alive && setHealthError(true));
    void poll();
    const id = window.setInterval(poll, 15000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (!sidePhoto) {
      setSideUrl(null);
      return;
    }
    const url = URL.createObjectURL(sidePhoto.image);
    setSideUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sidePhoto]);

  useEffect(() => {
    if (!photoFile) return;
    const url = URL.createObjectURL(photoFile);
    setPhotoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photoFile]);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [log, inspecting, editing, video.job?.messages.length]);

  /** Every accepted change goes through here: keeps Undo and clears stale CAD. */
  const applyAccepted = (next: GenerateRequest) => {
    setPrevious((p) => [...p, accepted]);
    setAccepted(next);
    setGen(null);
  };
  const undoAccepted = () => {
    if (!previous.length) return;
    setAccepted(previous[previous.length - 1]);
    setPrevious(previous.slice(0, -1));
    setGen(null);
  };

  // ---- points ----
  const pointsChanged = (next: Clicks) => {
    setHistory((h) => [...h.slice(-40), clicks]);
    setClicks(next);
    if (inspect) {
      setInspect(null);
      setInspectItemId(null);
      setGen(null);
    }
  };

  const addPoint = (p: Point) => {
    const set = activeSet;
    if (clicks[set].length >= SET_MAX[set]) return;
    const next = { ...clicks, [set]: [...clicks[set], p] };
    pointsChanged(next);
    if (set === "corners" && next.corners.length === 4) setActiveSet(next.outer.length < 3 ? "outer" : "inner");
  };
  const movePoint = (set: ClickSet, i: number, p: Point) => {
    const arr = clicks[set].slice();
    arr[i] = p;
    setClicks({ ...clicks, [set]: arr });
    if (inspect) {
      setInspect(null);
      setInspectItemId(null);
      setGen(null);
    }
  };
  const removePoint = (set: ClickSet, i: number) => {
    pointsChanged({ ...clicks, [set]: clicks[set].filter((_, k) => k !== i) });
  };
  const undoPoint = () => {
    if (!history.length) return;
    setClicks(history[history.length - 1]);
    setHistory((h) => h.slice(0, -1));
    if (inspect) {
      setInspect(null);
      setInspectItemId(null);
      setGen(null);
    }
  };

  // ---- photo ----
  const runDetect = async (blob: Blob, name: string, demoData: DemoClicks | null) => {
    setDetecting(true);
    try {
      const det = await api.autoDetect(blob, name);
      const next: Clicks = {
        corners: det.corners_px ?? [],
        outer: det.outer_edge_points_px,
        inner: det.inner_edge_points_px,
      };
      setClicks(next);
      setHistory([]);
      setActiveSet(next.corners.length < 4 ? "corners" : next.outer.length < 3 ? "outer" : "inner");
      push({ kind: "detect", det });
      if (demoData && det.confidence !== "HIGH") {
        push({ kind: "ai", text: "This is the demo photo. You can also use the saved demo points below the photo." });
      }
    } catch (e) {
      fail("Find points", e, () => void runDetect(blob, name, demoData));
      setActiveSet("corners");
    } finally {
      setDetecting(false);
    }
  };

  const newPhoto = (blob: Blob, name: string, demoData: DemoClicks | null) => {
    void video.clear().catch(e => showError(e.message));
    setPhotoFile(blob);
    setPhotoName(name);
    setSidePhoto(null);
    setClicks(EMPTY_CLICKS);
    setHistory([]);
    setInspect(null);
    setInspectItemId(null);
    setAccepted(INITIAL_ACCEPTED);
    setPrevious([]);
    setLimitations([]);
    setGen(null);
    setWholePhoto(false);
    setShowFit(true);
    setError(null);
    setDemo(demoData);
    setLog([]);
    push({ kind: "ai", text: "Thanks. I am looking for the card and the edges of the ring now." });
    void runDetect(blob, name, demoData);
  };

  const onUpload = (file: File | undefined) => {
    if (!file) return;
    if (file.type.startsWith("video/") || /\.(mp4|mov|webm|mkv)$/i.test(file.name)) {
      setGen(null); setPhotoFile(null); setPhotoUrl(null); setLog([]); setTypeOpen(true);
      void video.upload(file);
      return;
    }
    newPhoto(file, file.name || "photo.jpg", null);
  };

  const useDemoPhoto = async () => {
    setError(null);
    try {
      const d = await api.demoClicks();
      const url = d.image_url ?? "/api/demo-photo";
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Could not load the demo photo (HTTP ${res.status}).`);
      const blob = await res.blob();
      if (d.card_size_mm) {
        setCardW(d.card_size_mm[0].toFixed(2));
        setCardH(d.card_size_mm[1].toFixed(2));
      }
      newPhoto(blob, "demo-photo.jpg", d);
    } catch (e) {
      fail("Demo photo", e, () => void useDemoPhoto());
    }
  };

  const useSavedDemoPoints = () => {
    if (!demo) return;
    pointsChanged({ corners: demo.corners_px, outer: demo.outer_edge_points_px, inner: demo.inner_edge_points_px });
    setActiveSet("inner");
    push({ kind: "ai", text: "I loaded the saved demo points. Check them, then press Analyse photo." });
  };

  // ---- inspect ----
  const cardSize: [number, number] | null = useMemo(() => {
    const w = parseFloat(cardW.replace(",", "."));
    const h = parseFloat(cardH.replace(",", "."));
    return w > 0 && h > 0 ? [w, h] : null;
  }, [cardW, cardH]);

  const clicksReady = clicks.corners.length === 4 && clicks.outer.length >= 3 && clicks.inner.length >= 3;

  const runInspect = async () => {
    if (!photoFile || !clicksReady) return;
    setError(null);
    setInspecting(true);
    const ctx: InspectContext = {
      top_calibration: {
        card_size_mm: cardSize,
        size_confirmed: sizeConfirmed,
        corners_px: clicks.corners as [Point, Point, Point, Point],
        same_plane_confirmed: samePlane,
      },
      side_calibration: null,
      top_roi_px: null,
      outer_edge_points_px: clicks.outer,
      inner_edge_points_px: clicks.inner,
      reviewed_voice_text: "",
      operator_note: demo ? "demo photo" : "",
    };
    try {
      const res = await api.inspect(photoFile, photoName, ctx, sidePhoto);
      setInspect(res);
      setGen(null);
      setShowFit(true);
      const id = push({ kind: "inspect", res });
      setInspectItemId(id);
      if (res.warnings.length) push({ kind: "ai", tone: "warn", text: res.warnings.join(" ") });
    } catch (e) {
      fail("Analyse photo", e, () => void runInspect());
    } finally {
      setInspecting(false);
    }
  };

  const photoValue = (key: "outer_diameter" | "inner_diameter"): number | null => {
    if (!inspect) return null;
    const fitVal = inspect.fit ? (key === "outer_diameter" ? inspect.fit.outer_diameter_mm : inspect.fit.inner_diameter_mm) : null;
    return inspect[key].value_mm ?? fitVal;
  };

  const confirmPhotoDims = (keys: ("outer_diameter" | "inner_diameter")[]) => {
    if (!inspect) return;
    const next: GenerateRequest = { ...accepted, missing_arc_deg: inspect.fit?.missing_arc_deg ?? accepted.missing_arc_deg };
    let n = 0;
    for (const key of keys) {
      const v = photoValue(key);
      if (v === null) continue;
      next[key] = { value_mm: v, source: "PHOTO", confirmed: true };
      n++;
    }
    if (n) applyAccepted(next);
  };

  const photoConfirmed = (key: "outer_diameter" | "inner_diameter") => {
    const v = photoValue(key);
    const a = accepted[key];
    return v !== null && a.confirmed && a.source === "PHOTO" && a.value_mm === v;
  };

  // ---- talk ----
  const pendingDraft = [...log].reverse().find((i): i is Extract<Item, { kind: "draft" }> => i.kind === "draft" && i.status === "pending") ?? null;

  const sendEdit = async (text: string, origin: TalkOrigin) => {
    if (video.active) { await video.send(text); return; }
    setError(null);
    setEditing(true);
    try {
      const res = await api.profileEdit({ accepted, reviewed_voice_text: text });
      setLog((l) => l.map((i) => (i.kind === "draft" && i.status === "pending" ? { ...i, status: "cancelled" } : i)));
      push({ kind: "draft", res, origin, base: accepted, status: "pending" });
    } catch (e) {
      fail("Read your answer", e, () => void sendEdit(text, origin));
    } finally {
      setEditing(false);
    }
  };

  const onTranscript = useCallback(
    (res: VoiceResult) => {
      setLog((l) => l.map((i) => (i.kind === "me" && i.status === "review" ? { ...i, status: "discarded" } : i)));
      push({ kind: "me", text: res.transcript, origin: "voice", trace: res.trace, status: "review" });
    },
    [push],
  );

  const useTranscript = (id: number, text: string) => {
    const t = text.trim();
    if (!t) return;
    setLog((l) => l.map((i) => (i.id === id && i.kind === "me" ? { ...i, text: t, status: "sent" } : i)));
    void sendEdit(t.slice(0, 2000), "voice");
  };

  const sendTyped = () => {
    const t = typed.trim();
    if (!t) return;
    push({ kind: "me", text: t, origin: "typed", trace: null, status: "sent" });
    setTyped("");
    setTypeOpen(false);
    void sendEdit(t.slice(0, 2000), "typed");
  };

  const openType = () => {
    setTypeOpen(true);
    setTimeout(() => typeRef.current?.focus(), 30);
  };

  const confirmDraft = (item: Extract<Item, { kind: "draft" }>) => {
    const c = item.res.candidate;
    if (!c) return;
    const next: GenerateRequest = { ...accepted };
    const saved: string[] = [];
    for (const k of DIM_KEYS) {
      const changed = c[k].value_mm !== accepted[k].value_mm || c[k].source !== accepted[k].source;
      if (!changed) continue;
      // Typed text is the operator's own entry, not speech.
      const source = item.origin === "typed" && c[k].source === "SPOKEN_MEASUREMENT" ? "MANUAL_MEASUREMENT" : c[k].source;
      next[k] = { value_mm: c[k].value_mm, source, confirmed: c[k].value_mm !== null };
      saved.push(`${DIM_LABEL[k].toLowerCase()} ${mm(c[k].value_mm)} mm`);
    }
    if (!sameGroove(c.groove, accepted.groove)) {
      saved.push(c.groove ? `inner groove ${mm(c.groove.depth_mm)} × ${mm(c.groove.width_mm)} mm` : "no groove");
    }
    next.groove = c.groove;
    next.profile_basis = c.profile_basis;
    next.profile_rz_mm = c.profile_rz_mm;
    // The profile is confirmed only by its own explicit answer below.
    next.profile_confirmed = sameGroove(c.groove, accepted.groove) ? accepted.profile_confirmed : false;
    next.missing_arc_deg = accepted.missing_arc_deg;
    applyAccepted(next);
    if (item.res.limitations.length) {
      setLimitations((l) => [...l, ...item.res.limitations.filter((x) => !l.includes(x))]);
    }
    setLog((l) => l.map((i) => (i.id === item.id && i.kind === "draft" ? { ...i, status: "confirmed" } : i)));
    push({ kind: "ai", text: saved.length ? `Saved: ${saved.join(", ")}.` : "Saved. Nothing changed in the values." });
  };

  const cancelDraft = (item: Extract<Item, { kind: "draft" }>) => {
    setLog((l) => l.map((i) => (i.id === item.id && i.kind === "draft" ? { ...i, status: "cancelled" } : i)));
    push({ kind: "ai", text: "Nothing was saved. Say it again, or type it." });
  };

  const answerProfile = (withGroove: boolean) => {
    if (withGroove) {
      applyAccepted({ ...accepted, profile_confirmed: true });
      push({ kind: "ai", text: "Profile confirmed, with the inner groove." });
    } else {
      applyAccepted({ ...accepted, groove: null, profile_basis: "SIMPLIFIED_RECTANGLE", profile_rz_mm: null, profile_confirmed: true });
      push({ kind: "ai", text: "Profile confirmed: plain rectangle, no groove." });
    }
  };

  // ---- generate ----
  const missing: string[] = [];
  for (const k of DIM_KEYS) if (!(accepted[k].confirmed && accepted[k].value_mm !== null)) missing.push(DIM_LABEL[k].toLowerCase());
  if (!accepted.profile_confirmed) missing.push("profile");
  const canBuild = missing.length === 0;
  const missingArc = inspect?.fit?.missing_arc_deg ?? accepted.missing_arc_deg;

  const runGenerate = async () => {
    if (!canBuild) return;
    setError(null);
    setGenerating(true);
    setGen(null);
    try {
      const res = await api.generate({ ...accepted, missing_arc_deg: missingArc });
      setGen(res);
    } catch (e) {
      fail("Reconstruct the missing part", e, () => void runGenerate());
    } finally {
      setGenerating(false);
    }
  };

  // ---- derived display values ----
  const step = !photoUrl ? 1 : !inspect ? 2 : !canBuild ? 3 : 4;
  const stepText = ["Add a photo", "Check the points", "Answer and confirm", "Build the part"][step - 1];

  const showProfileAsk =
    !!inspect && !pendingDraft && !editing && !accepted.profile_confirmed && (accepted.thickness.confirmed || accepted.groove !== null);

  const nebiusMode = healthError ? "OFFLINE" : (health?.modes?.nebius ?? null);
  const slngMode = healthError ? "OFFLINE" : (health?.modes?.slng ?? null);

  // ---------------------------------------------------------------- render
  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
            <path d="M15 3a12 12 0 0 1 0 24" fill="none" stroke="#FFD21F" strokeWidth="5" />
            <path d="M15 27A12 12 0 0 1 15 3" fill="none" stroke="#E63B2E" strokeWidth="5" />
          </svg>
          <h1>GridMend</h1>
        </div>
        <p className="job">Rebuild a broken part from a photo or video</p>
        <div className="status" aria-label="Provider connections">
          {healthError ? (
            <span className="live mode-offline">
              <i />
              API offline
            </span>
          ) : (
            <>
              <ModePill label="Nebius" mode={nebiusMode} />
              <ModePill label="SLNG" mode={slngMode} />
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <Icon name="warn" size={22} />
          <p>{error.msg}</p>
          {error.retry && (
            <button
              type="button"
              className="btn small"
              onClick={() => {
                const r = error.retry;
                setError(null);
                r?.();
              }}
            >
              Retry
            </button>
          )}
          <button type="button" className="btn small ghost-dark" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      <main className="cols">
        {/* ---------------- LEFT: photo or video ---------------- */}
        <section className="col left" aria-label="Photo or video">
          <div className="panel photo">
            {video.active ? <VideoPreview video={video} onUpload={onUpload}/> : !photoUrl ? (
              <div className="photo-empty">
                <p className="big">Take a top-down photo of the broken part with a bank card next to it.</p>
                <label className="btn primary file-btn">
                  <Icon name="up" size={22} />
                  Upload photo or video
                  <input type="file" accept="image/*,video/*,.mov,.mkv" onChange={(e) => onUpload(e.target.files?.[0])} />
                </label>
                <button type="button" className="btn" onClick={() => void useDemoPhoto()}>
                  Use demo photo
                </button>
              </div>
            ) : (
              <>
                <div className="canvas-wrap">
                  <PhotoCanvas
                    photoUrl={photoUrl}
                    overlayUrl={inspect?.top_overlay_url ?? null}
                    showOverlay={showFit}
                    clicks={clicks}
                    activeSet={activeSet}
                    wholePhoto={wholePhoto}
                    onAddPoint={addPoint}
                    onMovePoint={movePoint}
                    onRemovePoint={removePoint}
                    onDragStart={() => setHistory((h) => [...h.slice(-40), clicks])}
                  />
                  {detecting && <div className="canvas-msg">Finding the card and the ring…</div>}
                  {inspect?.fit && showFit && inspect.top_overlay_url && (
                    <div className="photo-tag">
                      <span className="pill">
                        <Icon name="ok" />
                        Fit {mm(inspect.fit.rms_residual_mm, 2)} mm error
                      </span>
                      <span className="pill">
                        <span className="sw" />
                        {Math.round(((inspect.fit.missing_arc_deg[1] - inspect.fit.missing_arc_deg[0]) % 360 + 360) % 360)}° missing
                      </span>
                    </div>
                  )}
                </div>

                <div className="photo-tools">
                  {inspect?.top_overlay_url ? (
                    <div className="seg" role="group" aria-label="Photo view">
                      <button type="button" aria-pressed={showFit} onClick={() => setShowFit(true)}>
                        Fit
                      </button>
                      <button type="button" aria-pressed={!showFit} onClick={() => setShowFit(false)}>
                        Photo
                      </button>
                    </div>
                  ) : (
                    <span className="tools-note">{clicksReady ? "Drag a point to correct it." : "Click the photo to add points."}</span>
                  )}
                  <button type="button" className="btn small" aria-pressed={wholePhoto} onClick={() => setWholePhoto((w) => !w)}>
                    {wholePhoto ? "Zoom to part" : "Whole photo"}
                  </button>
                </div>

                {!(showFit && inspect?.top_overlay_url) && (
                  <div className="sets">
                    <div className="set-row" role="group" aria-label="Where a click adds a point">
                      {(["corners", "outer", "inner"] as ClickSet[]).map((s) => {
                        const n = clicks[s].length;
                        return (
                          <button
                            type="button"
                            key={s}
                            className={`set ${n >= SET_MIN[s] ? "done" : ""}`}
                            aria-pressed={activeSet === s}
                            style={{ ["--c" as string]: SET_COLORS[s] }}
                            onClick={() => setActiveSet(s)}
                          >
                            <i />
                            {SET_LABEL[s]} <b>{n}</b>
                          </button>
                        );
                      })}
                    </div>
                    <p className="hint">
                      {activeSet === "corners" && clicks.corners.length < 4
                        ? `Click the card corner: ${CORNER_NAMES[clicks.corners.length]}.`
                        : activeSet === "corners"
                          ? "The card has 4 corners. Drag one to correct it."
                          : `A click adds a point on the ${activeSet} edge. Spread them wide.`}{" "}
                      <button type="button" className="link" onClick={undoPoint} disabled={!history.length}>
                        Undo point
                      </button>
                      {demo && (
                        <>
                          {" "}
                          <button type="button" className="link" onClick={useSavedDemoPoints}>
                            Use saved demo points
                          </button>
                        </>
                      )}
                    </p>
                  </div>
                )}

                <div className="card-row">
                  <span className="card-lbl">Card</span>
                  <label className="sr" htmlFor="cw">
                    Card width in mm
                  </label>
                  <input id="cw" value={cardW} onChange={(e) => setCardW(e.target.value)} inputMode="decimal" />
                  <span aria-hidden="true">×</span>
                  <label className="sr" htmlFor="ch">
                    Card height in mm
                  </label>
                  <input id="ch" value={cardH} onChange={(e) => setCardH(e.target.value)} inputMode="decimal" />
                  <span>mm</span>
                </div>
                <label className="check">
                  <input type="checkbox" checked={sizeConfirmed} onChange={(e) => setSizeConfirmed(e.target.checked)} />I measured the card
                </label>
                <label className="check">
                  <input type="checkbox" checked={samePlane} onChange={(e) => setSamePlane(e.target.checked)} />
                  Card lies flat, next to the part
                </label>

                <div className="side-photo">
                  {sidePhoto && sideUrl ? (
                    <>
                      <img src={sideUrl} alt="Side photo" />
                      <span>
                        <b>Side photo added.</b> The AI uses it to describe the shape. It does not measure sizes.
                      </span>
                      <button type="button" className="link" onClick={() => setSidePhoto(null)}>
                        Remove
                      </button>
                    </>
                  ) : (
                    <>
                      <label className="btn small file-btn">
                        <Icon name="up" size={16} />
                        Add a side photo (optional)
                        <input
                          type="file"
                          accept="image/*"
                          capture="environment"
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) setSidePhoto({ image: f, filename: f.name || "side.jpg" });
                          }}
                        />
                      </label>
                      <span className="small-note">Photo from the side, at ring height. It helps the AI see a groove, a step or wear.</span>
                    </>
                  )}
                </div>

                <button type="button" className="btn primary wide" disabled={!clicksReady || inspecting || detecting} onClick={() => void runInspect()}>
                  {inspecting ? "Analysing…" : inspect ? "Analyse again" : "Analyse photo"}
                </button>
                {!clicksReady && !detecting && (
                  <p className="small-note">Needs 4 card corners, and 3 or more points on each edge.</p>
                )}
                <div className="change-photo">
                  <label className="link file-link">
                    Change photo
                    <input type="file" accept="image/*,video/*,.mov,.mkv" onChange={(e) => onUpload(e.target.files?.[0])} />
                  </label>
                </div>
              </>
            )}
          </div>

        </section>

        {/* ---------------- CENTRE: conversation ---------------- */}
        <section className="panel chat" aria-label="Conversation">
          <div className="chat-head">
            <h2>Talk it through</h2>
            <span className="step">
              {video.active ? "Video → intact reference → missing material" : <>Step {step} of 4: <b>{stepText.toLowerCase()}</b></>}
            </span>
          </div>
          <div className="thread" ref={threadRef} aria-live="polite">
            {video.active ? <><VideoChat video={video}/>{log.filter((i): i is Extract<Item, {kind:"me"}> => i.kind === "me" && i.status === "review").map(item => <MeBubble key={item.id} item={item} busy={video.busy} onUse={useTranscript} onDiscard={id => setLog(l => l.filter(i => i.id !== id))}/>)}</> : <>
            <Ai>
              <p>
                Hello. I rebuild broken parts from one photo. I never guess a size: you confirm every value before I build.
              </p>
            </Ai>
            {!photoUrl && (
              <Ai>
                <p className="q">Please take a top-down photo of the broken part, with a bank card next to it for scale.</p>
              </Ai>
            )}

            {log.map((item) => {
              switch (item.kind) {
                case "ai":
                  return (
                    <Ai key={item.id} tone={item.tone}>
                      <p className={item.tone === "question" ? "q" : undefined}>{item.text}</p>
                    </Ai>
                  );
                case "detect": {
                  const d = item.det;
                  const card = d.corners_px !== null;
                  return (
                    <Ai key={item.id} tone={d.confidence === "HIGH" ? undefined : "warn"} who="Point finder" whoNote={`confidence ${d.confidence.toLowerCase()}`}>
                      <p>
                        {card ? "I found the card. " : "I did not find the card. Please click its 4 corners. "}
                        {d.outer_edge_points_px.length >= 3
                          ? `I put ${d.outer_edge_points_px.length} points on the outer edge and ${d.inner_edge_points_px.length} on the inner edge.`
                          : "I did not find the ring edges. Please click 3 or more points on each edge."}
                      </p>
                      <p className="soft">Drag a point to correct it. Then press Analyse photo.</p>
                      {d.warnings.length > 0 && <p className="warn-line">{d.warnings.join(" ")}</p>}
                    </Ai>
                  );
                }
                case "inspect": {
                  const r = item.res;
                  const current = item.id === inspectItemId;
                  const ov = r.outer_diameter.value_mm ?? r.fit?.outer_diameter_mm ?? null;
                  const iv = r.inner_diameter.value_mm ?? r.fit?.inner_diameter_mm ?? null;
                  const both = current && ov !== null && iv !== null && !(photoConfirmed("outer_diameter") && photoConfirmed("inner_diameter"));
                  return (
                    <div key={item.id} className="group">
                      <Ai trace={r.trace} who="Nebius" whoNote="looked at your photo">
                        {!current && <p className="stale">Old result. The points changed after this.</p>}
                        {r.status === "UNSUPPORTED" && <p className="warn-line">This part is not supported yet.</p>}
                        {r.observations.map((o, i) => (
                          <p key={i}>{o}</p>
                        ))}
                        <div className="chips">
                          <SourceChip origin="photo" label={`Outer ${mm(ov)} mm`} />
                          <SourceChip origin="photo" label={`Inner ${mm(iv)} mm`} />
                          {cardSize && <SourceChip origin="photo" label={`Card ${cardW} × ${cardH} mm${sizeConfirmed ? ", measured" : ", not measured"}`} />}
                        </div>
                        {current && ov !== null && iv !== null && (
                          <div className="bubble-actions">
                            {both ? (
                              <button type="button" className="btn go" onClick={() => confirmPhotoDims(["outer_diameter", "inner_diameter"])}>
                                <Icon name="ok" size={22} />
                                Confirm both diameters
                              </button>
                            ) : (
                              <span className="state ok">
                                <Icon name="ok" />
                                Diameters confirmed
                              </span>
                            )}
                          </div>
                        )}
                      </Ai>
                      {r.question && current && (
                        <Ai who="Nebius" whoNote="needs something the photo cannot show">
                          <p className="q">{r.question}</p>
                          <p className="soft">Tap the yellow bar below and say the answer.</p>
                        </Ai>
                      )}
                    </div>
                  );
                }
                case "me":
                  return <MeBubble key={item.id} item={item} busy={editing} onUse={useTranscript} onDiscard={(id) => setLog((l) => l.map((i) => (i.id === id && i.kind === "me" ? { ...i, status: "discarded" } : i)))} />;
                case "draft":
                  return (
                    <DraftCard
                      key={item.id}
                      item={item}
                      onConfirm={() => confirmDraft(item)}
                      onCancel={() => cancelDraft(item)}
                      onType={openType}
                    />
                  );
              }
            })}

            {inspecting && (
              <Ai>
                <p className="soft">Measuring the photo and asking Nebius…</p>
              </Ai>
            )}
            {editing && (
              <Ai>
                <p className="soft">Reading your answer…</p>
              </Ai>
            )}

            {showProfileAsk && (
              <Ai who="GridMend" whoNote="one last check">
                <p className="q">Is this the ring profile?</p>
                <p>
                  {accepted.groove
                    ? `Rectangle wall with an inner groove, ${mm(accepted.groove.depth_mm)} mm deep and ${mm(accepted.groove.width_mm)} mm wide.`
                    : "A plain rectangle wall, with no groove. To add a groove, say its depth and width."}
                </p>
                <div className="bubble-actions">
                  {accepted.groove ? (
                    <>
                      <button type="button" className="btn go" onClick={() => answerProfile(true)}>
                        <Icon name="ok" size={22} />
                        Yes, this profile
                      </button>
                      <button type="button" className="btn" onClick={() => answerProfile(false)}>
                        No groove (plain rectangle)
                      </button>
                    </>
                  ) : (
                    <button type="button" className="btn go" onClick={() => answerProfile(false)}>
                      <Icon name="ok" size={22} />
                      Yes, plain rectangle
                    </button>
                  )}
                </div>
              </Ai>
            )}
            {canBuild && !gen && !generating && (
              <Ai>
                <p>All values are confirmed. You can now reconstruct the missing part.</p>
                {!missingArc && <p className="soft">Check the photo points and analyse it to identify the missing arc first.</p>}
                <div className="bubble-actions">
                  <button type="button" className="btn go" disabled={!missingArc} onClick={() => void runGenerate()}>
                    Reconstruct missing part
                  </button>
                </div>
              </Ai>
            )}
            {generating && <Ai><p>Reconstructing the missing part…</p></Ai>}
            {gen && (
              <Ai>
                <p>
                  {gen.missing_segment_stl_url ? "Your missing part is ready. Download the STL file on the right." : "No missing-part STL was produced. Check the photo fit and missing arc."}
                </p>
              </Ai>
            )}
            {previous.length > 0 && (
              <button type="button" className="link undo" onClick={undoAccepted}>Undo last change</button>
            )}
            {(gen?.limitations.length || limitations.length) > 0 && (
              <Ai tone="warn"><p>{[...new Set([...(gen?.limitations ?? []), ...limitations])].join(" ")}</p></Ai>
            )}
            </>}
          </div>

          <p className="talk-hint">
            {video.active
              ? 'Describe what to build and include your measurements in one message. You can give ring radii and a rectangular cross section. Review the readback and press Confirm and build; the result appears on the right.'
              : <>Say or type one size, for example “thickness is 6 mm”. Nothing is used until you press Confirm.</>}
          </p>
          {(typeOpen || video.active) && (
            <form
              className="typebox"
              onSubmit={(e) => {
                e.preventDefault();
                sendTyped();
              }}
            >
              <label className="sr" htmlFor="typeIn">
                {video.active ? "Describe the reconstruction and measurements" : "Type one value"}
              </label>
              <input
                id="typeIn"
                ref={typeRef}
                value={typed}
                maxLength={2000}
                placeholder={video.active ? "Build the missing part; include radii and cross section" : "For example: thickness is 6 mm"}
                onChange={(e) => setTyped(e.target.value)}
                onKeyDown={(e) => e.key === "Escape" && setTypeOpen(false)}
              />
              <button type="submit" className="btn" disabled={!typed.trim() || editing || video.busy || (video.active && (!video.job || video.job.status === "INGESTING"))}>
                Send
              </button>
              {!video.active && <button type="button" className="btn ghost" onClick={() => setTypeOpen(false)}>
                Close
              </button>}
            </form>
          )}
          <TalkBar busy={editing || video.busy} onError={showError} onTranscript={onTranscript} onTypeInstead={openType} />
        </section>

        {/* ---------------- RIGHT: 3D + download ---------------- */}
        <section className="col right" aria-label="Rebuilt part">
          {video.active ? <VideoResult video={video}/> : <>
          <div className={`viewer ${gen ? "has-model" : ""}`}>
            <div className="v-top">
              <div>
                <h2>Rebuilt ring</h2>
                <p className="sub">{gen ? "From confirmed values" : generating ? "Building…" : "Not built yet"}</p>
              </div>
              {gen && <span className="v-hint">Drag to turn</span>}
            </div>
            {gen ? (
              <RingViewer key={gen.design_id} ringUrl={gen.stl_url} segmentUrl={gen.missing_segment_stl_url} />
            ) : (
              <div className="viewer-empty">
                <svg width="64" height="64" viewBox="0 0 64 64" aria-hidden="true">
                  <circle cx="32" cy="32" r="22" fill="none" stroke="currentColor" strokeWidth="6" strokeDasharray="6 6" />
                </svg>
                <p>No 3D model yet. Confirm your measurements in the conversation to reconstruct the missing part.</p>
              </div>
            )}
            {gen && (
              <div className="legend">
                <span className="pill">
                  <span className="sw y" />
                  Your part
                </span>
                {gen.missing_segment_stl_url && (
                  <span className="pill">
                    <span className="sw" />
                    Restored segment
                  </span>
                )}
              </div>
            )}
          </div>

          <div ref={dlRef}>
            <MissingPartDownload
              url={gen?.missing_segment_stl_url ?? null}
              message={gen?.missing_segment_stl_url
                ? "Your missing part is ready to download."
                : generating
                  ? "Reconstructing the missing part…"
                  : "The STL file will be available here once the missing part is reconstructed and checked."}
            />
          </div>
          </>}
        </section>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------- chat parts

function Ai({
  children,
  tone,
  trace,
  who,
  whoNote,
}: {
  children: ReactNode;
  tone?: "warn" | "question";
  trace?: Trace;
  who?: string;
  whoNote?: string;
}) {
  return (
    <div className={`msg ai ${tone === "warn" ? "warn" : ""}`}>
      <div className="av" aria-hidden="true">
        {tone === "warn" ? "!" : "AI"}
      </div>
      <div className="bubble">
        {(who || trace) && (
          <div className="who">
            {who && <b>{who}</b>}
            {whoNote && <span>{whoNote}</span>}
            {trace && <TraceTag trace={trace} />}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

function MeBubble({
  item,
  busy,
  onUse,
  onDiscard,
}: {
  item: Extract<Item, { kind: "me" }>;
  busy: boolean;
  onUse: (id: number, text: string) => void;
  onDiscard: (id: number) => void;
}) {
  const [text, setText] = useState(item.text);
  const review = item.status === "review";
  return (
    <div className={`msg me ${item.status === "discarded" ? "discarded" : ""}`}>
      <div className="av" aria-hidden="true">
        You
      </div>
      <div className="bubble">
        <div className="voice-line">
          <SourceChip origin={item.origin === "voice" ? "voice" : "typed"} label={item.origin === "voice" ? "Voice" : "Typed"} />
          {item.trace && <TraceTag trace={item.trace} />}
          {item.status === "discarded" && <span className="soft">Not used</span>}
        </div>
        {review ? (
          <>
            <label className="sr" htmlFor={`t${item.id}`}>
              Check and correct what I heard
            </label>
            <textarea id={`t${item.id}`} value={text} maxLength={2000} rows={2} onChange={(e) => setText(e.target.value)} />
            <p className="soft">Check the words. Fix them if needed.</p>
            <div className="bubble-actions">
              <button type="button" className="btn dark" disabled={busy || !text.trim()} onClick={() => onUse(item.id, text)}>
                Use this
              </button>
              <button type="button" className="btn ghost" onClick={() => onDiscard(item.id)}>
                Discard
              </button>
            </div>
          </>
        ) : (
          <p className="said">“{item.text}”</p>
        )}
        {item.trace && item.origin === "voice" && (
          <div className="who foot">Transcribed by SLNG in {(item.trace.latency_ms / 1000).toFixed(1)} s</div>
        )}
      </div>
    </div>
  );
}

function DraftCard({
  item,
  onConfirm,
  onCancel,
  onType,
}: {
  item: Extract<Item, { kind: "draft" }>;
  onConfirm: () => void;
  onCancel: () => void;
  onType: () => void;
}) {
  const { res, base, origin, status } = item;
  const c = res.candidate;
  const rows: { name: string; was: string; now: string; src: Origin }[] = [];
  if (c) {
    for (const k of DIM_KEYS) {
      if (c[k].value_mm !== base[k].value_mm || c[k].source !== base[k].source) {
        rows.push({
          name: DIM_LABEL[k],
          was: base[k].value_mm === null ? "unknown" : `${mm(base[k].value_mm)} mm`,
          now: c[k].value_mm === null ? "?" : `${mm(c[k].value_mm)} mm`,
          src: origin === "typed" ? "typed" : (originOf(c[k].source) ?? "voice"),
        });
      }
    }
    if (!sameGroove(c.groove, base.groove)) {
      rows.push({
        name: "Inner groove",
        was: base.groove ? `${mm(base.groove.depth_mm)} × ${mm(base.groove.width_mm)} mm` : "none",
        now: c.groove ? `${mm(c.groove.depth_mm)} × ${mm(c.groove.width_mm)} mm` : "none",
        src: origin === "typed" ? "typed" : "voice",
      });
    }
  }
  const cls = status === "confirmed" ? "done" : status === "cancelled" ? "cancelled" : "";
  return (
    <div className={`msg ai draft ${cls}`}>
      <div className="av" aria-hidden="true">
        AI
      </div>
      <div className="bubble">
        <div className="draft-top">
          {status === "confirmed" ? (
            <>
              <span className="state ok">
                <Icon name="ok" size={20} />
              </span>
              <span>
                <b>Confirmed.</b> Saved to the part.
              </span>
            </>
          ) : status === "cancelled" ? (
            <span>
              <b>Cancelled.</b> Nothing was saved.
            </span>
          ) : (
            <>
              <span className="state draft">
                <i />
              </span>
              {c ? (
                <span>
                  <b>Draft, not saved yet.</b> Is this what you meant?
                </span>
              ) : (
                <span>
                  <b>Nothing to save yet.</b> I need one more detail.
                </span>
              )}
            </>
          )}
          <span className="draft-trace">
            {origin === "typed" && <span className="typed-tag">Typed, not voice</span>}
            <TraceTag trace={res.trace} />
          </span>
        </div>
        <div className="draft-body">
          <p className="readback">{res.readback}</p>
          {rows.length > 0 && (
            <div className="draft-rows">
              {rows.map((r) => (
                <div className="drow" key={r.name}>
                  <span className="n">{r.name}</span>
                  <span className="v">
                    <s>{r.was}</s>
                    {r.now}
                  </span>
                  <SourceChip origin={r.src} label={r.src === "typed" ? "You" : undefined} />
                </div>
              ))}
            </div>
          )}
          {!c && res.question && <p className="q">{res.question}</p>}
          {res.limitations.length > 0 && (
            <ul className="limits">
              {res.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          )}
        </div>
        {status === "pending" && (
          <div className="draft-actions">
            {c && (
              <button type="button" className="btn go" onClick={onConfirm}>
                <Icon name="ok" size={24} />
                {rows.length === 1 ? `Confirm ${rows[0].name.toLowerCase()}` : "Confirm these values"}
              </button>
            )}
            <button type="button" className="btn" onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className="btn ghost" onClick={onType}>
              Type instead
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
