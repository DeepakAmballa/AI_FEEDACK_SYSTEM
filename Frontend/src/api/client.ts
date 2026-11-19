import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Every request has a timeout so an unresponsive backend surfaces as an error instead of an
// endless spinner. Uploads (document extraction/OCR) get a longer allowance below.
const api = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});
const UPLOAD_TIMEOUT = 180_000;

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — session expired/invalid: clear and send to the single login page.
// Login requests are excluded so a wrong password shows an inline error instead of reloading.
api.interceptors.response.use(
  (res) => res,
  (error) => {
    const url: string = error.config?.url || '';
    if (error.response?.status === 401 && !url.includes('/api/auth/login')) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('role');
      localStorage.removeItem('full_name');
      localStorage.removeItem('user_id');
      if (window.location.pathname !== '/login') {
        sessionStorage.setItem('auth_notice', 'Your session has expired. Please sign in again.');
        window.location.href = '/login';
      }
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
      timeout: 15_000,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },
  me: () => api.get('/api/auth/me', { timeout: 8_000 }),
  changePassword: (current_password: string, new_password: string) =>
    api.post('/api/auth/change-password', { current_password, new_password }),
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
  // Admin-owned assessments (RTLP rubrics, mapped to subjects)
  getRubricTemplates: () => api.get('/api/admin/rubric-templates'),
  listAssessments: () => api.get('/api/admin/assessments'),
  getAssessment: (id: number) => api.get(`/api/admin/assessments/${id}`),
  createAssessment: (data: any) => api.post('/api/admin/assessments', data),
  updateAssessment: (id: number, data: any) => api.put(`/api/admin/assessments/${id}`, data),
  deactivateAssessment: (id: number) => api.delete(`/api/admin/assessments/${id}`),
  // Assessment Types & Rubrics
  listAssessmentTypes: () => api.get('/api/admin/assessment-types'),
  createAssessmentType: (data: any) => api.post('/api/admin/assessment-types', data),
  updateAssessmentType: (id: number, data: any) => api.put(`/api/admin/assessment-types/${id}`, data),
  createRubricVersion: (typeId: number, data: any) => api.post(`/api/admin/assessment-types/${typeId}/rubric-versions`, data),
  // Evaluation Monitoring & Comparison
  getEvaluationMonitoring: (params?: any) => api.get('/api/admin/evaluation-monitoring', { params }),
  getEvaluationComparison: (submissionId: number) => api.get(`/api/admin/evaluation-monitoring/${submissionId}`),
  retryAiEvaluation: (submissionId: number) => api.post(`/api/admin/evaluation-monitoring/${submissionId}/retry`),
  downloadFeedbackPdf: (submissionId: number) =>
    api.get(`/api/admin/evaluation-monitoring/${submissionId}/feedback.pdf`, { responseType: 'blob' }),
  publishEvaluation: (submissionId: number, publish: boolean) => api.put(`/api/admin/evaluation-monitoring/${submissionId}/publish`, null, { params: { publish } }),
};

// ─── Faculty ───────────────────────────────────────────────────────────────────
export const facultyApi = {
  getSubjects: () => api.get('/api/faculty/subjects'),
  uploadCourseDoc: (subjectId: number, file: File, docType: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('doc_type', docType);
    return api.post(`/api/faculty/subjects/${subjectId}/course-documents`, form, {
      timeout: UPLOAD_TIMEOUT,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  listCourseDocs: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/course-documents`),
  buildIndex: (subjectId: number) => api.post(`/api/faculty/subjects/${subjectId}/build-index`),
  // Course Profile (Typed)
  getCourseProfile: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/course-profile`),
  saveTypedCourseProfile: (subjectId: number, data: any) => api.post(`/api/faculty/subjects/${subjectId}/course-profile/typed`, data),
  addTopic: (subjectId: number, data: any) => api.post(`/api/faculty/subjects/${subjectId}/topics`, data),
  listTopics: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/topics`),
  // Assessments (admin-owned; read-only for faculty)
  listAssessments: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/assessments`),
  getSubmissions: (subjectId: number) => api.get(`/api/faculty/subjects/${subjectId}/submissions`),
  getSubmissionDetail: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}`),
  getSubmissionFile: (submissionId: number, download = false) =>
    api.get(`/api/faculty/submissions/${submissionId}/file`, {
      params: { download },
      responseType: 'blob',
    }),
  // Faculty-First Evaluation
  getEvaluationContext: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}/evaluation-context`),
  submitManualEvaluation: (submissionId: number, data: any) =>
    api.post(`/api/faculty/submissions/${submissionId}/manual-evaluate`, data),
  getFacultyEvaluation: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}/faculty-evaluation`),
  getEvaluationStatus: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}/evaluation-status`),
  getFeedbackDocument: (submissionId: number) => api.get(`/api/faculty/submissions/${submissionId}/feedback-document`),
  downloadFeedbackPdf: (submissionId: number) =>
    api.get(`/api/faculty/submissions/${submissionId}/feedback.pdf`, { responseType: 'blob' }),
  // Legacy compatibility
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
  getAllAssessments: () => api.get('/api/student/assessments'),
  submitAssignment: (assessmentId: number, file: File, subjectId?: number) => {
    const form = new FormData();
    form.append('file', file);
    if (subjectId) form.append('subject_id', String(subjectId));
    return api.post(`/api/student/assessments/${assessmentId}/submit`, form, {
      timeout: UPLOAD_TIMEOUT,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  submitTypedAssignment: (assessmentId: number, data: { typed_content: string; is_draft: boolean }, subjectId?: number) =>
    api.post(`/api/student/assessments/${assessmentId}/submit-typed`, data, { params: subjectId ? { subject_id: subjectId } : undefined }),
  getMyTypedDraft: (assessmentId: number) => api.get(`/api/student/assessments/${assessmentId}/my-typed-draft`),
  getMySubmissions: () => api.get('/api/student/submissions'),
  getFeedback: (submissionId: number) => api.get(`/api/student/submissions/${submissionId}/feedback`),
  downloadFeedbackPdf: (submissionId: number) =>
    api.get(`/api/student/submissions/${submissionId}/feedback.pdf`, { responseType: 'blob' }),
};
