import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — refresh or redirect to login
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// --- Auth ---
export const authApi = {
  register: (data: { email: string; password: string; name: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
};

// --- Events ---
export const eventsApi = {
  list: () => api.get('/events'),
  create: (data: any) => api.post('/events', data),
  get: (id: string) => api.get(`/events/${id}`),
  update: (id: string, data: any) => api.patch(`/events/${id}`, data),
  delete: (id: string) => api.delete(`/events/${id}`),
  archive: (id: string) => api.post(`/events/${id}/archive`),
};

// --- Links ---
export const linksApi = {
  list: (eventId: string) => api.get(`/events/${eventId}/links`),
  create: (eventId: string, data?: any) => api.post(`/events/${eventId}/links`, data),
  deactivate: (eventId: string, linkId: string) =>
    api.delete(`/events/${eventId}/links/${linkId}`),
};

// --- Storage ---
export const storageApi = {
  get: (eventId: string) => api.get(`/events/${eventId}/storage`),
  set: (eventId: string, data: any) => api.put(`/events/${eventId}/storage`, data),
  verify: (eventId: string) => api.post(`/events/${eventId}/storage/verify`),
  provisionManaged: (eventId: string, data?: any) =>
    api.post(`/events/${eventId}/storage/managed`, data),
};

// --- Uploads ---
export const uploadsApi = {
  list: (eventId: string, page = 1) =>
    api.get(`/events/${eventId}/uploads`, { params: { page } }),
  stats: (eventId: string) => api.get(`/events/${eventId}/uploads/stats`),
  delete: (eventId: string, uploadId: string) =>
    api.delete(`/events/${eventId}/uploads/${uploadId}`),
};

// --- Guest (no auth) ---
export const guestApi = {
  resolveLink: (shortCode: string) => api.get(`/e/${shortCode}`),
  verifyPin: (shortCode: string, pin: string) =>
    api.post(`/e/${shortCode}/verify-pin`, { pin }),
  upload: (shortCode: string, formData: FormData) =>
    api.post(`/e/${shortCode}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
};

// --- Billing ---
export const billingApi = {
  tiers: () => api.get('/billing/tiers'),
  checkout: (data: { event_id: string; tier: string }) =>
    api.post('/billing/checkout', data),
  payments: () => api.get('/billing/payments'),
};
