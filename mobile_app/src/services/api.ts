import Constants from 'expo-constants';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const API_BASE: string =
  Constants.expoConfig?.extra?.apiBase ?? 'http://192.168.1.8:8000';

const api = axios.create({ baseURL: API_BASE, timeout: 30000 });

// Attach JWT token to every request
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('auth_token');
  if (token) {
    config.headers = config.headers ?? {};
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// ─── Types ───────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  target_role: string;
  target_location: string;
  has_resume: boolean;
}

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
  scrape_cooldown: {
    can_scrape: boolean;
    next_scrape_at: string;
    cooldown_minutes: number;
  };
}

export interface ResumeAnalysis {
  summary: string;
  strengths: string[];
  recommended_roles: string[];
  skill_gaps: string[];
  suggested_keywords: string[];
}

// ─── Auth API ────────────────────────────────────────────────────

export const authApi = {
  signup: (email: string, password: string, name: string) =>
    api.post<{ token: string; user: User }>('/api/auth/signup', { email, password, name }),

  login: (email: string, password: string) =>
    api.post<{ token: string; user: User }>('/api/auth/login', { email, password }),

  me: () => api.get<User>('/api/auth/me'),

  uploadResume: async (fileUri: string, fileName: string, targetRole: string, targetLocation: string) => {
    const form = new FormData();
    form.append('file', { uri: fileUri, name: fileName, type: 'application/pdf' } as any);
    form.append('target_role', targetRole);
    form.append('target_location', targetLocation);
    return api.post<{ message: string; word_count: number; analysis: ResumeAnalysis }>(
      '/api/resume/upload',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
  },
};

// ─── Jobs API ────────────────────────────────────────────────────

export const jobsApi = {
  list: (params?: { status?: string; source?: string; search?: string }) =>
    api.get<{ total: number; jobs: Job[] }>('/api/jobs', { params }),

  detail: (id: number) => api.get<JobDetail>(`/api/jobs/${id}`),

  resume: (id: number) => api.get<ResumeData>(`/api/jobs/${id}/resume`),

  search: (body: {
    keyword?: string;
    location?: string;
    max_jobs?: number;
    auto_apply?: boolean;
    additional_requirements?: string;
  }) => api.post('/api/jobs/search', body),

  markApplied: (id: number, note?: string) =>
    api.post(`/api/jobs/${id}/apply`, { note: note || 'Applied manually' }),

  retailor: (id: number) => api.post(`/api/jobs/${id}/retailor`, {}),

  delete: (id: number) => api.delete(`/api/jobs/${id}`),

  status: () => api.get<StatusData>('/api/status'),
};
