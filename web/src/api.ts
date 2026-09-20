import type {
  ApiError,
  GenerateRequest,
  GenerateResult,
  InspectContext,
  InspectResult,
  Mode,
  Point,
  ProfileEditRequest,
  ProfileEditResult,
  VoiceResult,
} from "./types.ts";

/** Error shown in the red banner. */
export class ApiFailure extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiFailure(0, "NETWORK", `Cannot reach the API (${url}). Is the backend running on port 8000?`);
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const err = body as Partial<ApiError> | null;
    const code = err?.error ?? `HTTP_${res.status}`;
    const message = err?.message ?? (typeof (body as { detail?: unknown })?.detail === "string"
      ? String((body as { detail: string }).detail)
      : text.slice(0, 300) || res.statusText);
    throw new ApiFailure(res.status, code, message);
  }
  if (body === null) {
    throw new ApiFailure(res.status, "BAD_RESPONSE", `The API returned no JSON for ${url}.`);
  }
  return body as T;
}

export interface Health {
  status: string;
  modes: { nebius: Mode; slng: Mode } & Record<string, Mode>;
}

export interface DemoClicks {
  corners_px: [Point, Point, Point, Point];
  outer_edge_points_px: Point[];
  inner_edge_points_px: Point[];
  card_size_mm: [number, number] | null;
  image_url?: string | null; // optional: lets the UI load the demo photo too
}

export interface AutoDetect {
  corners_px: [Point, Point, Point, Point] | null;
  outer_edge_points_px: Point[];
  inner_edge_points_px: Point[];
  confidence: "HIGH" | "LOW" | "NONE";
  warnings: string[];
}

export const api = {
  autoDetect: (image: Blob, filename: string) => {
    const fd = new FormData();
    fd.append("top_image", image, filename);
    return request<AutoDetect>("/api/auto-detect", { method: "POST", body: fd });
  },
  health: () => request<Health>("/api/health"),
  demoClicks: () => request<DemoClicks>("/api/demo-clicks"),
  inspect: (image: Blob, filename: string, context: InspectContext, side?: { image: Blob; filename: string } | null) => {
    const fd = new FormData();
    fd.append("top_image", image, filename);
    if (side) fd.append("side_image", side.image, side.filename); // shape observations only
    fd.append("context", JSON.stringify(context));
    return request<InspectResult>("/api/inspect", { method: "POST", body: fd });
  },
  voice: (audio: Blob, filename: string) => {
    const fd = new FormData();
    fd.append("audio", audio, filename);
    return request<VoiceResult>("/api/voice", { method: "POST", body: fd });
  },
  profileEdit: (req: ProfileEditRequest) =>
    request<ProfileEditResult>("/api/profile-edit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }),
  generate: (req: GenerateRequest) =>
    request<GenerateResult>("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }),
};

export function errorMessage(e: unknown): string {
  // The server writes plain-English messages; the code is for logs, not for the engineer.
  if (e instanceof ApiFailure) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
