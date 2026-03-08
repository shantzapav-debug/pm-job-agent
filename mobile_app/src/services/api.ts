import Constants from 'expo-constants';
import axios from 'axios';

// In production (APK), reads from app.json extra.apiBase (your Render URL).
// In dev (Expo Go on same WiFi), falls back to local IP.
export const API_BASE: string =
  Constants.expoConfig?.extra?.apiBase ?? 'http://192.168.1.8:8000';

const api = axios.create({ baseURL: API_BASE, timeout: 30000 });

export interface Job {
  id: number;
  title: string;
  company: string;
  location: string;
  source: string;
  job_url: string;
  experience_required: string;
  salary_range: string;
  posted_date: string;
  skills_required: string[];
  description: string;
  change_percentage: number;
  keywords_added: string[];
  status: 'pending' | 'applied' | 'manual' | 'failed';
  applied_at: string | null;
  apply_note: string | null;
  created_at: string;
}

export interface JobDetail extends Job {
  tailored_resume_text: string;
  original_resume_text: string;
  changes_log: Array<{
    type: string;
    section?: string;
    original: string;
    updated: string;
    reason?: string;
  }>;
}

export interface ResumeData {
  job_id: number;
  title: string;
  company: string;
  tailored_resume_text: string;
  original_resume_text: string;
  changes_log: JobDetail['changes_log'];
  change_percentage: number;
  keywords_added: string[];
}

export interface StatusData {
  pipeline: {
    running: boolean;
    progress: string;
    jobs_found: number;
    jobs_tailored: number;
    jobs_applied: number;
  };
  stats: {
    total_jobs: number;
    applied: number;
    manual_apply_needed: number;
    pending: number;
    tailored: number;
  };
}

export const jobsApi = {
  list: (params?: { status?: string; source?: string; search?: string }) =>
    api.get<{ total: number; jobs: Job[] }>('/api/jobs', { params }),

  detail: (id: number) => api.get<JobDetail>(`/api/jobs/${id}`),

  resume: (id: number) => api.get<ResumeData>(`/api/jobs/${id}/resume`),

  search: (body: { keyword?: string; location?: string; max_jobs?: number; auto_apply?: boolean }) =>
    api.post('/api/jobs/search', body),

  markApplied: (id: number, note?: string) =>
    api.post(`/api/jobs/${id}/apply`, { note: note || 'Applied manually' }),

  retailor: (id: number) => api.post(`/api/jobs/${id}/retailor`, {}),

  delete: (id: number) => api.delete(`/api/jobs/${id}`),

  status: () => api.get<StatusData>('/api/status'),
};
