import type {
  Brand, BrandInput, Job, JobDetail, Media, Output, Overview, Project, SystemStatus,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Can't reach the KINOVA server. Is it running?");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const msg = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg).join("; ")
      : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({ method, body: JSON.stringify(data ?? {}) });

export const api = {
  status: () => request<SystemStatus>("/api/system/status"),
  overview: () => request<Overview>("/api/overview"),
  checkClaude: () => request<{ ok: boolean; model?: string; error?: string }>("/api/system/check-claude", json("POST")),

  brands: () => request<Brand[]>("/api/brands"),
  createBrand: (b: Partial<BrandInput>) => request<Brand>("/api/brands", json("POST", b)),
  updateBrand: (id: string, b: Partial<BrandInput>) => request<Brand>(`/api/brands/${id}`, json("PATCH", b)),
  deleteBrand: (id: string) => request<void>(`/api/brands/${id}`, { method: "DELETE" }),

  projects: (status = "active") => request<Project[]>(`/api/projects?status=${status}`),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (p: { name: string; topic?: string; description?: string; brand_id?: string | null }) =>
    request<Project>("/api/projects", json("POST", p)),
  updateProject: (id: string, p: Partial<Project>) => request<Project>(`/api/projects/${id}`, json("PATCH", p)),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: "DELETE" }),

  media: (params: { project_id?: string; kind?: string; q?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]);
    return request<Media[]>(`/api/media?${qs}`);
  },
  deleteMedia: (id: string) => request<void>(`/api/media/${id}`, { method: "DELETE" }),

  jobs: (projectId?: string) => request<Job[]>(`/api/jobs${projectId ? `?project_id=${projectId}` : ""}`),
  job: (id: string) => request<JobDetail>(`/api/jobs/${id}`),
  createJob: (projectId: string, body: {
    source_asset_ids: string[]; brand_id?: string | null; topic?: string; goal?: string; platform?: string;
    variations?: number; music?: string; broll?: boolean;
  }) => request<JobDetail>(`/api/projects/${projectId}/jobs`, json("POST", body)),
  retryJob: (id: string) => request<JobDetail>(`/api/jobs/${id}/retry`, json("POST")),
  rerunJob: (id: string) => request<JobDetail>(`/api/jobs/${id}/rerun`, json("POST")),

  music: () => request<Media[]>("/api/music"),

  outputs: (projectId?: string) => request<Output[]>(`/api/outputs${projectId ? `?project_id=${projectId}` : ""}`),
  updateOutput: (id: string, o: Partial<Output>) => request<Output>(`/api/outputs/${id}`, json("PATCH", o)),
};

export async function uploadMusic(file: File, title: string, mood: string): Promise<Media> {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  form.append("mood", mood);
  return request<Media>("/api/music", { method: "POST", body: form });
}

/** Upload with real progress (fetch can't report upload progress). */
export function uploadMedia(projectId: string, file: File, onProgress: (pct: number) => void): Promise<Media> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/projects/${projectId}/media`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: { detail?: string } | Media | null = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* not json */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as Media);
      else reject(new ApiError(xhr.status, (body as { detail?: string })?.detail ?? `Upload failed (${xhr.status})`));
    };
    xhr.onerror = () => reject(new ApiError(0, "Upload failed — connection lost."));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
