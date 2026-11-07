export type JobStatus = "queued" | "running" | "succeeded" | "partial" | "failed";

export interface Brand {
  id: string;
  name: string;
  industry: string;
  audience: string;
  voice: string;
  personality: string;
  products: string;
  goals: string;
  editing_style: string;
  instructions: string;
  colors: string[];
  fonts: string[];
  created_at: string;
  updated_at: string;
}
export type BrandInput = Omit<Brand, "id" | "created_at" | "updated_at">;

export interface Project {
  id: string;
  name: string;
  description: string;
  topic: string;
  status: "active" | "archived";
  brand_id: string | null;
  created_at: string;
  updated_at: string;
  asset_count: number;
  output_count: number;
  cover_url: string | null;
  latest_job_status: JobStatus | null;
}

export interface Media {
  id: string;
  project_id: string | null;
  kind: "video" | "image";
  filename: string;
  content_type: string;
  size_bytes: number;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  has_audio: boolean;
  created_at: string;
  url: string | null;
  thumbnail_url: string | null;
}

export interface QcCheck { name: string; ok: boolean; detail: string }

export interface Output {
  id: string;
  job_id: string;
  project_id: string;
  variation_key: string;
  style: string;
  aspect: string;
  status: "rendering" | "ready" | "failed";
  approved: boolean;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  title: string;
  hook: string;
  caption: string;
  hashtags: string[];
  cta: string;
  edit_plan: { reason?: string; hook_text?: string; clips?: { start: number; end: number }[] };
  qc: { passed?: boolean; checks?: QcCheck[]; error?: string };
  created_at: string;
  url: string | null;
  download_url: string | null;
  thumbnail_url: string | null;
}

export interface Trends {
  topic: string;
  sample_size: number;
  note?: string;
  median_duration_s?: number | null;
  shorts_share?: number;
  median_short_duration_s?: number | null;
  title_patterns?: { question_share: number; number_share: number; median_title_chars: number };
  top_keywords?: string[];
  top_tags?: string[];
  top_videos?: { title: string; channel: string; views: number; duration_s: number }[];
}

export interface Job {
  id: string;
  project_id: string;
  source_asset_id: string;
  brand_id: string | null;
  status: JobStatus;
  stage: string | null;
  progress: number;
  settings: { topic?: string; goal?: string; platform?: string; variations?: number };
  error: string | null;
  cost_usd: number;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  planner: "claude" | "heuristic" | null;
  plan_summary: string | null;
  trends: Trends | null;
  warnings: string[];
  skipped_stages: string[];
  source: { duration: number; width: number; height: number; has_audio: boolean } | null;
}

export interface JobEvent { stage: string; status: string; message: string; created_at: string }

export interface JobDetail extends Job {
  events: JobEvent[];
  outputs: Output[];
  source_media: Media | null;
  project_name: string;
}

export interface SystemStatus {
  mode: string;
  organization: { id: string; name: string; plan: string };
  worker: { online: boolean; count: number };
  integrations: {
    claude: { configured: boolean; models: { fast: string; smart: string }; env: string };
    youtube: { configured: boolean; region: string; env: string };
    whisper: { configured: boolean; model: string; env: string };
  };
  limits: { max_upload_mb: number; max_video_seconds: number; max_job_cost_usd: number };
}

export interface Overview {
  stats: {
    projects: number;
    uploads: number;
    clips_ready: number;
    clips_approved: number;
    jobs_running: number;
    brands: number;
    ai_spend_month_usd: number;
    footage_minutes: number;
  };
  active_job: Job | null;
  latest_job: Job | null;
  recent_jobs: Job[];
  recent_outputs: Output[];
  projects: Project[];
  brand: { id: string; name: string; voice: string; colors: string[] } | null;
}
