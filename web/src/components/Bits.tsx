import type { Dimension, Trace } from "../types.ts";

export function Icon({ name, size = 16 }: { name: "cam" | "mic" | "hand" | "ok" | "warn" | "up"; size?: number }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", "aria-hidden": true as const };
  switch (name) {
    case "cam":
      return (
        <svg {...p}>
          <path fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" d="M4 8h3l2-3h6l2 3h3v11H4z" />
          <circle cx="12" cy="13" r="3.4" fill="none" stroke="currentColor" strokeWidth="2.4" />
        </svg>
      );
    case "mic":
      return (
        <svg {...p}>
          <rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor" />
          <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
    case "hand":
      return (
        <svg {...p}>
          <path d="M4 18h16M6 14l8-8 3 3-8 8H6z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      );
    case "ok":
      return (
        <svg {...p}>
          <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "warn":
      return (
        <svg {...p}>
          <path d="M12 3l10 18H2z" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" />
          <path d="M12 10v5M12 18v.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      );
    case "up":
      return (
        <svg {...p}>
          <path d="M12 16V4M6 10l6-6 6 6M4 20h16" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
}

export type Origin = "photo" | "voice" | "typed";

export function originOf(source: Dimension["source"]): Origin | null {
  if (source === "PHOTO") return "photo";
  if (source === "SPOKEN_MEASUREMENT") return "voice";
  if (source === "MANUAL_MEASUREMENT") return "typed";
  return null;
}

/** Provenance chip: where a value came from. */
export function SourceChip({ origin, label }: { origin: Origin; label?: string }) {
  if (origin === "photo")
    return (
      <span className="chip photo">
        <Icon name="cam" />
        {label ?? "Photo"}
      </span>
    );
  if (origin === "voice")
    return (
      <span className="chip voice">
        <Icon name="mic" />
        {label ?? "Voice"}
      </span>
    );
  return (
    <span className="chip you">
      <Icon name="hand" />
      {label ?? "You, typed"}
    </span>
  );
}

export function StateMark({ state }: { state: "ok" | "draft" | "open" | "unknown" }) {
  if (state === "ok")
    return (
      <span className="state ok">
        <Icon name="ok" />
        Confirmed
      </span>
    );
  if (state === "draft")
    return (
      <span className="state draft">
        <i />
        Draft
      </span>
    );
  if (state === "open")
    return (
      <span className="state open">
        <i />
        Not confirmed
      </span>
    );
  return <span className="state unknown">Unknown</span>;
}

export function TraceTag({ trace }: { trace: Trace }) {
  const name = trace.provider === "NEBIUS" ? "Nebius" : trace.provider === "SLNG" ? "SLNG" : "Local";
  const cls = trace.mode === "LIVE" ? "live" : "fake";
  return (
    <span className={`trace ${cls}`} title={`${trace.provider}, ${trace.model || "no model"}, ${Math.round(trace.latency_ms)} ms`}>
      {name} {trace.mode === "LIVE" ? "live" : trace.mode}
    </span>
  );
}
