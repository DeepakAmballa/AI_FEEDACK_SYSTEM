import React, { useEffect, useState } from 'react';
import { Routes, Route, useParams, useNavigate } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import { studentApi } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import {
  LayoutDashboard, BookOpen, Upload, FileText,
  CheckCircle, Clock, ChevronRight, AlertCircle, Star
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/student', icon: LayoutDashboard },
  { label: 'My Subjects', to: '/student/subjects', icon: BookOpen },
  { label: 'My Submissions', to: '/student/submissions', icon: FileText },
];

// ─── Student Dashboard ────────────────────────────────────────────────────────
function StudentDashboard() {
  const [data, setData] = useState<any>(null);
  const { user } = useAuth();

  useEffect(() => {
    studentApi.getDashboard().then(r => setData(r.data)).catch(console.error);
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800">Welcome, {data?.full_name || user?.full_name}!</h2>
        <p className="text-slate-500 text-sm mt-1">
          {data?.program && `${data.program} · `}
          {data?.year_of_study && `Year ${data.year_of_study} · `}
          Student ID: {data?.student_id}
        </p>
      </div>

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="card">
            <p className="text-xs text-slate-500">Enrolled Subjects</p>
            <p className="text-3xl font-bold text-primary-600 mt-1">{data.enrolled_subjects}</p>
          </div>
          <div className="card">
            <p className="text-xs text-slate-500">Total Submissions</p>
            <p className="text-3xl font-bold text-indigo-600 mt-1">{data.total_submissions}</p>
          </div>
          <div className="card">
            <p className="text-xs text-slate-500">Approved</p>
            <p className="text-3xl font-bold text-green-600 mt-1">{data.approved_submissions}</p>
          </div>
          <div className="card">
            <p className="text-xs text-slate-500">Pending Review</p>
            <p className="text-3xl font-bold text-yellow-600 mt-1">{data.pending_submissions}</p>
          </div>
        </div>
      )}

      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-3">Quick Links</h3>
        <div className="flex flex-wrap gap-3">
          <a href="/student/subjects" className="btn-primary text-sm">📚 View Subjects & Assessments</a>
          <a href="/student/submissions" className="btn-secondary text-sm">📄 My Submissions</a>
        </div>
      </div>
    </div>
  );
}

// ─── My Subjects ──────────────────────────────────────────────────────────────
function SubjectList() {
  const [subjects, setSubjects] = useState<any[]>([]);
  useEffect(() => { studentApi.getSubjects().then(r => setSubjects(r.data)); }, []);
  return (
    <div>
      <h2 className="text-xl font-bold text-slate-800 mb-6">My Subjects</h2>
      <div className="grid gap-3">
        {subjects.map(s => (
          <a key={s.id} href={`/student/subjects/${s.id}`}
            className="card hover:border-primary-300 hover:shadow-md transition-all group cursor-pointer">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800 group-hover:text-primary-700">{s.name}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{s.code}</p>
                {s.description && <p className="text-sm text-slate-500 mt-1 text-xs">{s.description}</p>}
              </div>
              <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-primary-600" />
            </div>
          </a>
        ))}
        {subjects.length === 0 && (
          <div className="card text-center py-10 text-slate-400">
            <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p>No subjects enrolled. Contact your administrator.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Subject Assessments & Upload ─────────────────────────────────────────────
function SubjectAssessments() {
  const { subjectId } = useParams<{ subjectId: string }>();
  const id = parseInt(subjectId!);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [msg, setMsg] = useState('');

  useEffect(() => { studentApi.getAssessments(id).then(r => setAssessments(r.data)); }, [id]);

  const handleUpload = async (assessmentId: number, e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    setUploadingId(assessmentId);
    setMsg('');
    try {
      const r = await studentApi.submitAssignment(assessmentId, e.target.files[0]);
      const uploadResult = r.data;
      if (!uploadResult || typeof uploadResult !== 'object') {
        throw new Error('The server returned an empty upload response. Please try again.');
      }
      if (uploadResult.extraction_status === 'success') {
        setMsg('✅ Submission successful! Document text extracted successfully.');
      } else {
        setMsg(`⚠️ File uploaded, but text extraction noted: ${uploadResult.extraction_status || 'unknown status'}`);
      }
      studentApi.getAssessments(id).then(r => setAssessments(r.data));
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.response?.data?.message || err.message || 'Upload failed';
      setMsg('❌ ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)));
    } finally { setUploadingId(null); }
  };

  return (
    <div>
      <a href="/student/subjects" className="text-slate-400 text-sm hover:text-slate-600 inline-flex items-center gap-1 mb-4">
        ← Back to Subjects
      </a>
      <h2 className="text-xl font-bold text-slate-800 mb-6">Subject Assessments</h2>

      {msg && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('❌') ? 'bg-red-50 text-red-700' : msg.startsWith('⚠️') ? 'bg-amber-50 text-amber-700' : 'bg-green-50 text-green-700'}`}>
          {msg}
        </div>
      )}

      <div className="space-y-4">
        {assessments.map(a => (
          <div key={a.id} className="card">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800">{a.title}</h3>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-slate-500 capitalize">{a.assessment_type}</span>
                  <span className="text-xs text-slate-500">Max: <strong>{a.max_marks} marks</strong></span>
                  {a.due_date && <span className="text-xs text-slate-500">Due: {new Date(a.due_date).toLocaleDateString()}</span>}
                </div>
                {a.description && <p className="text-sm text-slate-600 mt-2">{a.description}</p>}
              </div>
              <div className="ml-4">
                {a.submitted ? (
                  <div className="text-right">
                    <span className={`badge-${a.submission_status || 'pending'}`}>{a.submission_status || 'submitted'}</span>
                    <p className="text-xs text-slate-400 mt-1">Submitted</p>
                    {a.submission_status !== 'approved' && (
                      <label className="text-xs text-primary-600 hover:underline cursor-pointer block mt-1">
                        {uploadingId === a.id ? 'Re-uploading...' : 'Re-submit / Replace file'}
                        <input
                          type="file"
                          className="hidden"
                          accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif"
                          disabled={uploadingId === a.id}
                          onChange={e => handleUpload(a.id, e)}
                        />
                      </label>
                    )}
                  </div>
                ) : (
                  <label className={`btn-primary text-sm flex items-center gap-2 cursor-pointer ${uploadingId === a.id ? 'opacity-50' : ''}`}>
                    <Upload className="w-4 h-4" />
                    {uploadingId === a.id ? 'Uploading...' : 'Submit'}
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif"
                      disabled={uploadingId === a.id}
                      onChange={e => handleUpload(a.id, e)}
                    />
                  </label>
                )}
              </div>
            </div>
          </div>
        ))}
        {assessments.length === 0 && (
          <div className="card text-center py-8 text-slate-400">No assessments available for this subject</div>
        )}
      </div>
    </div>
  );
}

// ─── My Submissions ───────────────────────────────────────────────────────────
function MySubmissions() {
  const [submissions, setSubmissions] = useState<any[]>([]);
  const navigate = useNavigate();

  useEffect(() => { studentApi.getMySubmissions().then(r => setSubmissions(r.data)); }, []);

  return (
    <div>
      <h2 className="text-xl font-bold text-slate-800 mb-6">My Submissions</h2>
      <div className="card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-edu-border">
              <th className="text-left pb-2 text-slate-500 font-medium">Assessment</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Subject</th>
              <th className="text-left pb-2 text-slate-500 font-medium">File</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Status</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Feedback</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {submissions.map(s => (
              <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-3 font-medium text-slate-800">{s.assessment_title}</td>
                <td className="py-3 text-slate-500 text-xs">{s.subject_name}</td>
                <td className="py-3 text-slate-400 text-xs">{s.original_filename}</td>
                <td className="py-3"><span className={`badge-${s.status}`}>{s.status}</span></td>
                <td className="py-3">
                  {s.has_feedback ? (
                    <span className="badge-approved">Available</span>
                  ) : (
                    <span className="text-xs text-slate-400">Pending</span>
                  )}
                </td>
                <td className="py-3">
                  {s.has_feedback && (
                    <button onClick={() => navigate(`/student/submissions/${s.id}/feedback`)}
                      className="text-xs text-primary-600 hover:underline">
                      View Feedback →
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {submissions.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">No submissions yet. Go to My Subjects to submit.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── View Feedback ────────────────────────────────────────────────────────────
function FeedbackView() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const [feedback, setFeedback] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const downloadPdf = async () => {
    try {
      const response = await studentApi.downloadFeedbackPdf(parseInt(submissionId!));
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `evaluation-report-${submissionId}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Unable to download evaluation report', error);
    }
  };

  useEffect(() => {
    studentApi.getFeedback(parseInt(submissionId!))
      .then(r => setFeedback(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [submissionId]);

  if (loading) return <div className="text-slate-500">Loading feedback...</div>;

  if (!feedback || feedback.message) {
    return (
      <div>
        <button onClick={() => navigate(-1)} className="text-slate-400 text-sm mb-4 hover:text-slate-600">← Back</button>
        <div className="card text-center py-10">
          <Clock className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-600 font-medium">{feedback?.message || 'No feedback available yet'}</p>
          <p className="text-slate-400 text-sm mt-1">Your faculty is reviewing your submission.</p>
        </div>
      </div>
    );
  }

  const percentage = feedback.max_marks ? Math.round((feedback.final_score / feedback.max_marks) * 100) : 0;

  return (
    <div>
      <button onClick={() => navigate(-1)} className="text-slate-400 text-sm mb-4 hover:text-slate-600">← Back</button>

      {/* Score Header */}
      <div className="card bg-gradient-to-r from-green-50 to-emerald-50 border-green-200 mb-4">
        <h2 className="text-lg font-bold text-slate-800 mb-1">📊 Evaluation Report</h2>
        <p className="text-sm text-slate-600">{feedback.student_name}</p>
        <p className="text-sm text-slate-600">{feedback.assessment_title} · {feedback.subject_name}</p>
        {feedback.assessment_description && <p className="text-sm text-slate-600 mt-1">Question / brief: {feedback.assessment_description}</p>}
        <p className="text-xs text-slate-400 mt-0.5">Submitted: {new Date(feedback.submitted_at).toLocaleDateString()}</p>
        <div className="flex gap-2 mt-3">
          <button onClick={downloadPdf} className="btn-secondary text-xs">Download PDF</button>
          <button onClick={() => window.print()} className="btn-secondary text-xs">Print</button>
        </div>
        <div className="flex items-center gap-6 mt-4">
          <div>
            <p className="text-xs text-slate-500">Your Score</p>
            <p className="text-4xl font-bold text-green-700">{feedback.final_score}</p>
          </div>
          <div className="text-slate-300 text-3xl">/</div>
          <div>
            <p className="text-xs text-slate-500">Maximum</p>
            <p className="text-4xl font-bold text-slate-500">{feedback.max_marks}</p>
          </div>
          <div className="ml-4">
            <div className="w-20 h-20 rounded-full border-4 border-green-500 flex items-center justify-center">
              <span className="text-lg font-bold text-green-700">{percentage}%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Criterion Breakdown */}
      {feedback.criterion_scores?.length > 0 && (
        <div className="card mb-4">
          <h3 className="font-semibold text-slate-800 mb-3">📋 Marks Breakdown</h3>
          <div className="space-y-2">
            {feedback.criterion_scores.map((cs: any, i: number) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex-1">
                  <p className="text-sm text-slate-700">{cs.criterion_name}</p>
                </div>

                {(feedback.comparative_analysis_feedback || feedback.style_feedback?.length || feedback.language_errors?.length || feedback.line_feedback?.length) && (
                  <div className="card mb-4">
                    <h3 className="font-semibold text-slate-800 mb-3">Detailed Feedback</h3>
                    {feedback.comparative_analysis_feedback && <p className="text-sm text-slate-700 whitespace-pre-wrap mb-3">{feedback.comparative_analysis_feedback}</p>}
                    {feedback.style_feedback?.length > 0 && <><h4 className="text-xs font-semibold uppercase text-slate-500">Style</h4><ul className="list-disc pl-5 text-sm text-slate-700 mb-3">{feedback.style_feedback.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul></>}
                    {feedback.language_errors?.length > 0 && <><h4 className="text-xs font-semibold uppercase text-slate-500">Language and proofreading</h4><ul className="list-disc pl-5 text-sm text-slate-700 mb-3">{feedback.language_errors.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul></>}
                    {feedback.line_feedback?.length > 0 && <><h4 className="text-xs font-semibold uppercase text-slate-500">Line-level notes</h4><div className="space-y-2 mt-2">{feedback.line_feedback.map((item: any, i: number) => <div key={i} className="border-l-4 border-primary-300 pl-3"><p className="text-xs text-slate-500">Line {item.line_number} · {item.category}</p><p className="text-sm text-slate-700">{item.comment}</p>{item.suggested_revision && <p className="text-xs text-primary-700">Suggested revision: {item.suggested_revision}</p>}</div>)}</div></>}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <div className="w-28 bg-slate-200 rounded-full h-2">
                    <div className="bg-primary-500 h-2 rounded-full" style={{ width: `${Math.min(100, (cs.score / cs.max_marks) * 100)}%` }} />
                  </div>
                  <span className="text-sm font-bold text-primary-700 w-16 text-right">{cs.score} / {cs.max_marks}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final Feedback */}
      <div className="card mb-4">
        <h3 className="font-semibold text-slate-800 mb-2">📝 Faculty Feedback</h3>
        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{feedback.final_feedback}</p>
      </div>

      {/* Strengths & Improvements */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {feedback.strengths && (
          <div className="card border-green-200 bg-green-50">
            <h4 className="font-semibold text-green-800 mb-2">✅ Your Strengths</h4>
            <p className="text-sm text-green-700 whitespace-pre-wrap">{feedback.strengths}</p>
          </div>
        )}
        {feedback.improvement_suggestions && (
          <div className="card border-blue-200 bg-blue-50">
            <h4 className="font-semibold text-blue-800 mb-2">💡 How to Improve</h4>
            <p className="text-sm text-blue-700 whitespace-pre-wrap">{feedback.improvement_suggestions}</p>
          </div>
        )}
      </div>

      {feedback.missing_concepts && (
        <div className="card border-amber-200 bg-amber-50">
          <h4 className="font-semibold text-amber-800 mb-2">🔍 Concepts to Study</h4>
          <p className="text-sm text-amber-700 whitespace-pre-wrap">{feedback.missing_concepts}</p>
        </div>
      )}

      <div className="mt-4 text-center">
        <p className="text-xs text-slate-400">
          Approved on {new Date(feedback.approved_at).toLocaleDateString()} ·
          AI-assisted evaluation reviewed and approved by faculty
        </p>
      </div>
    </div>
  );
}

// ─── Student Portal ───────────────────────────────────────────────────────────
export default function StudentPortal() {
  return (
    <DashboardLayout navItems={navItems} portalLabel="Student Portal" portalColor="bg-indigo-600">
      <Routes>
        <Route path="/" element={<StudentDashboard />} />
        <Route path="/subjects" element={<SubjectList />} />
        <Route path="/subjects/:subjectId" element={<SubjectAssessments />} />
        <Route path="/submissions" element={<MySubmissions />} />
        <Route path="/submissions/:submissionId/feedback" element={<FeedbackView />} />
      </Routes>
    </DashboardLayout>
  );
}
