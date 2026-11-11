import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — redirect to login
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.clear();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;

// ─── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) => {
    const form = new URLSearchParams();
    form.append('username', email);
    form.append('password', password);
    return api.post('/api/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },
};

// ─── Admin ─────────────────────────────────────────────────────────────────────
export const adminApi = {
  getStats: () => api.get('/api/admin/stats'),
  listFaculty: () => api.get('/api/admin/faculty'),
  createFaculty: (data: any) => api.post('/api/admin/faculty', data),
  updateFaculty: (id: number, data: any) => api.put(`/api/admin/faculty/${id}`, data),
  listStudents: () => api.get('/api/admin/students'),
  createStudent: (data: any) => api.post('/api/admin/students', data),
  updateStudent: (id: number, data: any) => api.put(`/api/admin/students/${id}`, data),
  listSubjects: () => api.get('/api/admin/subjects'),
  createSubject: (data: any) => api.post('/api/admin/subjects', data),
  updateSubject: (id: number, data: any) => api.put(`/api/admin/subjects/${id}`, data),
  assignFaculty: (subjectId: number, facultyUserId: number) =>
    api.post(`/api/admin/subjects/${subjectId}/assign-faculty/${facultyUserId}`),
  enrollStudent: (subjectId: number, studentUserId: number) =>
    api.post(`/api/admin/subjects/${subjectId}/enroll-student/${studentUserId}`),
  getAuditLogs: () => api.get('/api/admin/audit-logs'),
  getAllSubmissions: () => api.get('/api/admin/submissions'),
};

// ─── Faculty ───────────────────────────────────────────────────────────────────
export const facultyApi = {
  getSubjects: () => api.get('/api/faculty/subjects'),
  uploadCourseDoc: (subjectId: number, file: File, docType: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('doc_type', docType);
    return api.post(`/api/faculty/subjects/${subjectId}/course-documents`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  listCourseDocs: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/course-documents`),
  buildIndex: (subjectId: number) => api.post(`/api/faculty/subjects/${subjectId}/build-index`),
  addTopic: (subjectId: number, data: any) => api.post(`/api/faculty/subjects/${subjectId}/topics`, data),
  listTopics: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/topics`),
  createAssessment: (data: any) => api.post('/api/faculty/assessments', data),
  listAssessments: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/assessments`),
  createRubric: (assessmentId: number, data: any) =>
    api.post(`/api/faculty/assessments/${assessmentId}/rubric`, data),
  getRubric: (assessmentId: number) => api.get(`/api/faculty/assessments/${assessmentId}/rubric`),
  getRubricTemplates: () => api.get('/api/faculty/rubric-templates'),
  getSubmissions: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/submissions`),
  getSubmissionDetail: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}`),
  triggerEvaluation: (submissionId: number) =>
    api.post(`/api/faculty/submissions/${submissionId}/evaluate`),
  getEvaluation: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}/evaluation`),
  approveEvaluation: (evaluationId: number, data: any) =>
    api.put(`/api/faculty/evaluations/${evaluationId}/approve`, data),
  rejectEvaluation: (evaluationId: number) =>
    api.put(`/api/faculty/evaluations/${evaluationId}/reject`),
  getEnrolledStudents: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/students`),
};

// ─── Student ───────────────────────────────────────────────────────────────────
export const studentApi = {
  getDashboard: () => api.get('/api/student/dashboard'),
  getSubjects: () => api.get('/api/student/subjects'),
  getAssessments: (subjectId: number) => api.get(`/api/student/subjects/${subjectId}/assessments`),
  submitAssignment: (assessmentId: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api.post(`/api/student/assessments/${assessmentId}/submit`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getMySubmissions: () => api.get('/api/student/submissions'),
  getFeedback: (submissionId: number) => api.get(`/api/student/submissions/${submissionId}/feedback`),
  downloadFeedbackPdf: (submissionId: number) =>
    api.get(`/api/student/submissions/${submissionId}/feedback.pdf`, { responseType: 'blob' }),
};
