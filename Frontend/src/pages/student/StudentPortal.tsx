import React, { useEffect, useState } from 'react';
import { Routes, Route, useParams, useNavigate, Link } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import FeedbackDocument from '../../components/shared/FeedbackDocument';
import toast from 'react-hot-toast';
import { studentApi } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import {
  LayoutDashboard, BookOpen, Upload, FileText,
  CheckCircle, Clock, ChevronRight, AlertCircle, Star,
  Download, Printer, Edit3, Save, Send, Eye, X, Check, ClipboardList
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/student', icon: LayoutDashboard },
  { label: 'Assessments', to: '/student/assessments', icon: ClipboardList },
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
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Welcome, {data?.full_name || user?.full_name}!</h2>
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
          <Link to="/student/assessments" className="btn-primary text-sm"><ClipboardList className="w-4 h-4" /> Go to Assessments</Link>
          <Link to="/student/subjects" className="btn-secondary text-sm">📚 My Subjects</Link>
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
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">My Subjects</h2>
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

// ─── Typed Submission Modal ──────────────────────────────────────────────────
function TypedSubmissionModal({
  assessment,
  subjectId,
  onClose,
  onSuccess,
}: {
  assessment: any;
  subjectId: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  useEffect(() => {
    studentApi.getMyTypedDraft(assessment.id)
      .then(res => {
        if (res.data?.typed_content) {
          setContent(res.data.typed_content);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [assessment.id]);

  const words = content.trim() ? content.trim().split(/\s+/).length : 0;
  const chars = content.length;

  const handleSubmit = async (isDraft: boolean) => {
    if (!content.trim()) {
      setMsg({ type: 'error', text: 'Please enter submission text before submitting.' });
      return;
    }
    try {
      setSaving(true);
      setMsg(null);
      await studentApi.submitTypedAssignment(assessment.id, {
        typed_content: content,
        is_draft: isDraft,
      }, subjectId);
      if (isDraft) {
        setMsg({ type: 'success', text: 'Draft saved successfully!' });
      } else {
        toast.success('Assignment submitted');
        onSuccess();
        onClose();
      }
    } catch (err: any) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to submit.' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-primary-600" />
              Typed Submission: {assessment.title}
            </h3>
            <p className="text-xs text-slate-500">
              {assessment.assessment_type} · Max {assessment.max_marks} marks
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl font-bold p-1">
            ✕
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto space-y-3">
          {assessment.description && (
            <div className="p-3 bg-blue-50/50 border border-blue-200 rounded-lg text-xs text-blue-900">
              <p className="font-semibold mb-0.5">Prompt / Instructions:</p>
              <p>{assessment.description}</p>
            </div>
          )}

          {msg && (
            <div className={`p-3 rounded-lg text-xs ${msg.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {msg.text}
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-xs text-slate-400">Loading draft content...</div>
          ) : (
            <div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                <span>Direct Essay / Submission Text</span>
                <span>{words} words · {chars} characters</span>
              </div>
              <textarea
                className="input-field w-full font-mono text-xs leading-relaxed"
                rows={14}
                placeholder="Type or paste your complete academic response here..."
                value={content}
                onChange={e => setContent(e.target.value)}
              />
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={() => handleSubmit(true)}
            disabled={saving || loading}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? 'Saving...' : 'Save Draft'}
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="text-xs text-slate-500 hover:text-slate-700 px-3 py-1.5"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => handleSubmit(false)}
              disabled={saving || loading}
              className="btn-primary text-xs flex items-center gap-1.5 px-4 py-2"
            >
              <Send className="w-3.5 h-3.5" />
              {saving ? 'Submitting...' : 'Submit Assignment'}
            </button>
          </div>
        </div>
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
  const [activeTypedModal, setActiveTypedModal] = useState<any | null>(null);

  const loadData = () => {
    studentApi.getAssessments(id).then(r => setAssessments(r.data)).catch(console.error);
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const handleUpload = async (assessmentId: number, e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    setUploadingId(assessmentId);
    setMsg('');
    try {
      const r = await studentApi.submitAssignment(assessmentId, e.target.files[0], id);
      const uploadResult = r.data;
      if (uploadResult?.extraction_status === 'success') {
        setMsg('✅ Submission successful! Document text extracted successfully.');
      } else {
        setMsg(`⚠️ File uploaded, but text extraction noted: ${uploadResult?.extraction_status || 'completed'}`);
      }
      loadData();
    } catch (err: any) {
      let detail = err.response?.data?.detail || err.response?.data?.message || err.message || 'Upload failed';
      if (Array.isArray(detail)) {
        detail = detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      }
      setMsg('❌ ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)));
    } finally {
      setUploadingId(null);
    }
  };

  return (
    <div>
      <a href="/student/subjects" className="text-slate-400 text-sm hover:text-slate-600 inline-flex items-center gap-1 mb-4">
        ← Back to Subjects
      </a>
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">Subject Assessments</h2>

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
                {a.instructions && <p className="text-xs text-slate-500 mt-2 bg-slate-50 rounded-lg p-2.5"><strong>Instructions:</strong> {a.instructions}</p>}
                {a.criteria?.length > 0 && (
                  <details className="mt-3 group">
                    <summary className="text-xs font-medium text-primary-700 cursor-pointer select-none">
                      How this is assessed ({a.criteria.length} criteria)
                    </summary>
                    <ul className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1">
                      {a.criteria.map((c: any) => (
                        <li key={c.name} className="flex items-center justify-between gap-3 text-xs text-slate-600">
                          <span className="flex items-center gap-2 min-w-0">
                            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
                            <span className="truncate">{c.label}. {c.name}</span>
                          </span>
                          <span className="text-slate-400 whitespace-nowrap">{c.max_marks} marks</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>

              <div className="ml-4 flex flex-col items-end gap-2">
                {a.submitted ? (
                  <div className="text-right">
                    <span className={`badge-${a.submission_status || 'pending'}`}>{a.submission_status || 'submitted'}</span>
                    <p className="text-xs text-slate-400 mt-1">Submitted</p>
                    {a.submission_status !== 'approved' && (
                      <div className="flex items-center gap-2 mt-2">
                        <label className="text-xs text-primary-600 hover:underline cursor-pointer">
                          {uploadingId === a.id ? 'Uploading...' : 'Re-upload File'}
                          <input
                            type="file"
                            className="hidden"
                            accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif"
                            disabled={uploadingId === a.id}
                            onChange={e => handleUpload(a.id, e)}
                          />
                        </label>
                        <span className="text-slate-300">|</span>
                        <button
                          onClick={() => setActiveTypedModal(a)}
                          className="text-xs text-primary-600 hover:underline"
                        >
                          Edit Typed Draft
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <label className={`btn-primary text-xs flex items-center gap-1.5 cursor-pointer ${uploadingId === a.id ? 'opacity-50' : ''}`}>
                      <Upload className="w-3.5 h-3.5" />
                      {uploadingId === a.id ? 'Uploading...' : 'Upload File'}
                      <input
                        type="file"
                        className="hidden"
                        accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif"
                        disabled={uploadingId === a.id}
                        onChange={e => handleUpload(a.id, e)}
                      />
                    </label>
                    <button
                      onClick={() => setActiveTypedModal(a)}
                      className="btn-secondary text-xs flex items-center gap-1.5"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      Type Online
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {assessments.length === 0 && (
          <div className="card text-center py-8 text-slate-400">No assessments available for this subject</div>
        )}
      </div>

      {activeTypedModal && (
        <TypedSubmissionModal
          assessment={activeTypedModal}
          subjectId={id}
          onClose={() => setActiveTypedModal(null)}
          onSuccess={loadData}
        />
      )}
    </div>
  );
}

// ─── Assessments tab: every assessment across enrolled subjects ───────────────
const STATE_META: Record<string, { label: string; badge: string }> = {
  not_started: { label: 'To do', badge: 'badge-neutral' },
  draft: { label: 'Draft saved', badge: 'badge-pending' },
  submitted: { label: 'Submitted', badge: 'badge-evaluated' },
  in_evaluation: { label: 'Being evaluated', badge: 'badge-pending' },
  feedback_ready: { label: 'Feedback ready', badge: 'badge-approved' },
};
const FILTERS = [
  { key: 'todo', label: 'To do', match: (a: any) => a.state === 'not_started' || a.state === 'draft' },
  { key: 'submitted', label: 'Submitted', match: (a: any) => a.state === 'submitted' || a.state === 'in_evaluation' },
  { key: 'feedback', label: 'Feedback ready', match: (a: any) => a.state === 'feedback_ready' },
  { key: 'all', label: 'All', match: () => true },
] as const;
const ACCEPT = '.pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif';

function dueLabel(a: any) {
  if (!a.due_date) return null;
  const d = new Date(a.due_date);
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000);
  const when = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  if (a.is_overdue) return { text: `Overdue · was due ${when}`, cls: 'text-red-600' };
  if (a.state === 'not_started' || a.state === 'draft') {
    if (days <= 0) return { text: `Due today · ${when}`, cls: 'text-amber-600' };
    if (days <= 3) return { text: `Due in ${days} day${days === 1 ? '' : 's'} · ${when}`, cls: 'text-amber-600' };
  }
  return { text: `Due ${when}`, cls: 'text-slate-500' };
}

function StudentAssessments() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]['key']>('todo');
  const [subject, setSubject] = useState<number | 'all'>('all');
  const [query, setQuery] = useState('');
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [typing, setTyping] = useState<any | null>(null);
  const navigate = useNavigate();

  const load = () => {
    studentApi.getAllAssessments()
      .then(r => setItems(r.data))
      .catch(() => toast.error('Could not load your assessments'))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const subjects = Array.from(new Map(items.map(a => [a.subject_id, { id: a.subject_id, name: a.subject_name, code: a.subject_code }])).values());
  const base = items.filter(a => (subject === 'all' || a.subject_id === subject)
    && (!query.trim() || `${a.title} ${a.description || ''} ${a.subject_name}`.toLowerCase().includes(query.trim().toLowerCase())));
  const active = FILTERS.find(f => f.key === filter)!;
  const visible = base.filter(active.match);

  const upload = async (a: any, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploadingId(a.id);
    try {
      const r = await studentApi.submitAssignment(a.id, file, a.subject_id);
      if (r.data?.extraction_status === 'success') toast.success(`Submitted “${a.title}”`);
      else toast(`Uploaded, but the text could not be fully read (${r.data?.extraction_status}). Consider typing your answer instead.`, { icon: '⚠️', duration: 7000 });
      load();
    } catch (err: any) {
      const d = err.response?.data?.detail;
      toast.error(Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : d || 'Upload failed');
    } finally {
      setUploadingId(null);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading assessments…</div>;

  return (
    <div className="space-y-5">
      <div className="page-header mb-0">
        <div>
          <h1 className="page-title">Assessments</h1>
          <p className="page-subtitle">Everything assigned to you across your subjects. Upload a file or type your answer online.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5" role="tablist">
          {FILTERS.map(f => {
            const count = base.filter(f.match).length;
            const on = f.key === filter;
            return (
              <button key={f.key} role="tab" aria-selected={on} onClick={() => setFilter(f.key)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${on ? 'bg-primary-600 border-primary-600 text-white' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                {f.label} <span className={on ? 'text-white/80' : 'text-slate-400'}>{count}</span>
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <input className="input-field w-48" placeholder="Search…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Search assessments" />
          {subjects.length > 1 && (
            <select className="input-field w-48" value={subject} onChange={e => setSubject(e.target.value === 'all' ? 'all' : Number(e.target.value))} aria-label="Filter by subject">
              <option value="all">All subjects</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}
            </select>
          )}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="card text-center py-14">
          <CheckCircle className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="font-medium text-slate-700">{filter === 'todo' ? 'You are all caught up' : 'Nothing here'}</p>
          <p className="text-sm text-slate-500 mt-1">{items.length === 0 ? 'No assessments have been assigned to your subjects yet.' : 'Try another filter.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map(a => {
            const meta = STATE_META[a.state] || STATE_META.not_started;
            const due = dueLabel(a);
            const busy = uploadingId === a.id;
            return (
              <div key={a.id} className={`card ${a.is_overdue ? 'border-red-200' : ''}`}>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="badge-neutral">{a.subject_code}</span>
                      <span className={meta.badge}>{meta.label}</span>
                    </div>
                    <h3 className="font-semibold text-slate-900">{a.title}</h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {a.assessment_type} · {a.max_marks} marks
                      {due && <> · <span className={due.cls}>{due.text}</span></>}
                      {a.submitted_at && a.state !== 'not_started' && ` · ${a.state === 'draft' ? 'Saved' : 'Submitted'} ${new Date(a.submitted_at).toLocaleDateString()}`}
                    </p>
                    {a.description && <p className="text-sm text-slate-700 mt-2">{a.description}</p>}
                    {a.instructions && <p className="text-xs text-slate-500 mt-2 bg-slate-50 rounded-lg p-2.5"><strong>Instructions:</strong> {a.instructions}</p>}
                    {a.criteria?.length > 0 && (
                      <details className="mt-3">
                        <summary className="text-xs font-medium text-primary-700 cursor-pointer select-none">How this is assessed ({a.criteria.length} criteria)</summary>
                        <ul className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1">
                          {a.criteria.map((c: any) => (
                            <li key={c.name} className="flex items-center justify-between gap-3 text-xs text-slate-600">
                              <span className="flex items-center gap-2 min-w-0">
                                <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
                                <span className="truncate">{c.label}. {c.name}</span>
                              </span>
                              <span className="text-slate-400 whitespace-nowrap">{c.max_marks} marks</span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </div>

                  <div className="flex flex-col items-end gap-2 shrink-0">
                    {a.state === 'feedback_ready' ? (
                      <>
                        {a.final_score != null && <p className="text-lg font-semibold text-slate-900">{a.final_score}<span className="text-sm text-slate-400"> / {a.max_marks}</span></p>}
                        <button className="btn-primary text-sm" onClick={() => navigate(`/student/submissions/${a.submission_id}/feedback`)}>
                          <Eye className="w-4 h-4" /> View feedback
                        </button>
                      </>
                    ) : a.can_submit ? (
                      <>
                        <div className="flex gap-2">
                          <label className={`btn-primary text-sm cursor-pointer ${busy ? 'opacity-60 pointer-events-none' : ''}`}>
                            <Upload className="w-4 h-4" />
                            {busy ? 'Uploading…' : a.state === 'submitted' ? 'Replace file' : 'Upload file'}
                            <input type="file" className="hidden" accept={ACCEPT} disabled={busy} onChange={e => upload(a, e)} />
                          </label>
                          <button className="btn-secondary text-sm" onClick={() => setTyping(a)}>
                            <Edit3 className="w-4 h-4" /> {a.state === 'draft' ? 'Continue draft' : a.submission_type === 'typed' ? 'Edit answer' : 'Type online'}
                          </button>
                        </div>
                        {a.state === 'submitted' && <p className="text-[11px] text-slate-400">You can update your work until your faculty evaluates it.</p>}
                      </>
                    ) : (
                      <p className="text-xs text-slate-500 max-w-[220px] text-right">
                        Your faculty is evaluating this work, so it can no longer be changed. Feedback appears here when it is ready.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {typing && (
        <TypedSubmissionModal assessment={typing} subjectId={typing.subject_id}
          onClose={() => setTyping(null)} onSuccess={load} />
      )}
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
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">My Submissions</h2>
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

// ─── View Feedback (Unified Student Evaluation Report) ─────────────────────────
function FeedbackView() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const [feedback, setFeedback] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const navigate = useNavigate();

  const downloadPdf = async () => {
    try {
      setDownloading(true);
      const response = await studentApi.downloadFeedbackPdf(parseInt(submissionId!));
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `feedback-${(feedback?.assessment_title || 'assessment').replace(/[^\w-]+/g, '-').toLowerCase()}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Unable to download the feedback PDF.');
    } finally {
      setDownloading(false);
    }
  };

  useEffect(() => {
    studentApi.getFeedback(parseInt(submissionId!))
      .then(r => setFeedback(r.data))
      .catch(() => setFeedback({ message: 'Unable to load feedback right now.' }))
      .finally(() => setLoading(false));
  }, [submissionId]);

  if (loading) return <div className="p-8 text-center text-slate-500">Loading your feedback…</div>;

  if (!feedback || feedback.message) {
    return (
      <div>
        <button onClick={() => navigate(-1)} className="text-slate-500 text-sm mb-4 hover:text-slate-800 inline-flex items-center gap-1">← Back</button>
        <div className="card text-center py-12">
          <Clock className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-700 font-semibold text-base">{feedback?.message || 'No feedback published yet'}</p>
          <p className="text-slate-400 text-xs mt-1">Your faculty evaluates your work first, then the AI evaluation runs. Your feedback document appears here as soon as both are complete.</p>
        </div>
      </div>
    );
  }

  // New annotated feedback document
  if (feedback.document) {
    return (
      <div className="space-y-5 pb-12">
        <div className="max-w-[860px] mx-auto flex flex-wrap items-end justify-between gap-3 print:hidden">
          <div>
            <button onClick={() => navigate(-1)} className="text-slate-500 text-sm hover:text-slate-800 inline-flex items-center gap-1 mb-2">← Back</button>
            <h1 className="page-title">{feedback.assessment_title}</h1>
            <p className="page-subtitle">{feedback.subject_name} · Final mark is the average of your faculty and AI evaluations</p>
          </div>
        </div>
        <FeedbackDocument doc={feedback.document} onDownload={downloadPdf} downloading={downloading} />
      </div>
    );
  }

  // Legacy results published before the feedback document existed
  const percentage = feedback.final_percentage ?? (feedback.max_marks ? Math.round((feedback.final_score / feedback.max_marks) * 100) : 0);
  const observations: any[] = feedback.irrelevant_observations || [];
  return (
    <div className="space-y-6 pb-12 max-w-4xl">
      <button onClick={() => navigate(-1)} className="text-slate-500 text-sm hover:text-slate-800 inline-flex items-center gap-1">← Back</button>
      <div className="card flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium text-slate-500">{feedback.subject_name} · {feedback.assessment_type}</p>
          <h1 className="page-title mt-1">{feedback.assessment_title}</h1>
          <p className="text-xs text-slate-400 mt-1">Submitted {new Date(feedback.submitted_at).toLocaleDateString()}</p>
        </div>
        <div className="text-right">
          <p className="stat-label">Final mark</p>
          <p className="stat-value text-slate-900">{feedback.final_score}<span className="text-base text-slate-400"> / {feedback.max_marks}</span></p>
          <p className="text-xs text-slate-500">{percentage}%</p>
          <button onClick={downloadPdf} disabled={downloading} className="btn-secondary text-xs mt-3">
            <Download className="w-3.5 h-3.5" /> {downloading ? 'Preparing…' : 'Download PDF'}
          </button>
        </div>
      </div>
      {feedback.overall_feedback && (
        <div className="card"><h3 className="font-semibold text-slate-900 mb-2">Overall feedback</h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{feedback.overall_feedback}</p></div>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        {feedback.strengths && <div className="card"><h3 className="font-semibold text-emerald-800 mb-2">Strengths</h3><p className="text-sm text-slate-700 whitespace-pre-wrap">{feedback.strengths}</p></div>}
        {feedback.weaknesses && <div className="card"><h3 className="font-semibold text-amber-800 mb-2">Areas for improvement</h3><p className="text-sm text-slate-700 whitespace-pre-wrap">{feedback.weaknesses}</p></div>}
      </div>
      {feedback.criterion_feedback?.length > 0 && (
        <div className="card space-y-2"><h3 className="font-semibold text-slate-900 mb-1">Rubric criteria</h3>
          {feedback.criterion_feedback.map((cf: any, i: number) => (
            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <p className="text-xs font-semibold text-slate-800">{cf.criterion_name}</p>
              <p className="text-xs text-slate-600 mt-1">{cf.description}</p>
            </div>
          ))}
        </div>
      )}
      {feedback.improvement_suggestions && (
        <div className="card"><h3 className="font-semibold text-slate-900 mb-2">Suggestions</h3><p className="text-sm text-slate-700 whitespace-pre-wrap">{feedback.improvement_suggestions}</p></div>
      )}
      {observations.length > 0 && (
        <div className="card"><h3 className="font-semibold text-rose-800 mb-2">Content relevance</h3>
          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
            {observations.map((o, i) => (
              <li key={i}>{typeof o === 'string' ? o : `${o.excerpt ? `“${o.excerpt}” — ` : ''}${o.why_unrelated || ''}`}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Student Portal ───────────────────────────────────────────────────────────
export default function StudentPortal() {
  return (
    <DashboardLayout navItems={navItems} portalLabel="Student Portal" portalColor="bg-indigo-600">
      <Routes>
        <Route path="/" element={<StudentDashboard />} />
        <Route path="/assessments" element={<StudentAssessments />} />
        <Route path="/subjects" element={<SubjectList />} />
        <Route path="/subjects/:subjectId" element={<SubjectAssessments />} />
        <Route path="/submissions" element={<MySubmissions />} />
        <Route path="/submissions/:submissionId/feedback" element={<FeedbackView />} />
      </Routes>
    </DashboardLayout>
  );
}
