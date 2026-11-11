import React, { useEffect, useState } from 'react';
import { Routes, Route, Link, useNavigate, useParams } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import { facultyApi } from '../../api/client';
import {
  LayoutDashboard, BookOpen, FileText, Users,
  Upload, Brain, CheckCircle, XCircle, Edit3,
  ChevronRight, AlertTriangle, Star
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/faculty', icon: LayoutDashboard },
  { label: 'My Subjects', to: '/faculty/subjects', icon: BookOpen },
  { label: 'Evaluations', to: '/faculty/evaluations', icon: Brain },
];

// ─── Faculty Dashboard ────────────────────────────────────────────────────────
function FacultyDashboard() {
  const [subjects, setSubjects] = useState<any[]>([]);
  useEffect(() => { facultyApi.getSubjects().then(r => setSubjects(r.data)); }, []);
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-800">Faculty Dashboard</h2>
        <p className="text-slate-500 text-sm mt-1">Manage your subjects, learning documents, and student evaluations</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card"><p className="text-sm text-slate-500">Assigned Subjects</p><p className="text-3xl font-bold text-primary-600 mt-1">{subjects.length}</p></div>
      </div>
      <div className="card">
        <h3 className="font-semibold mb-3 text-slate-800">Your Subjects</h3>
        {subjects.length === 0 ? (
          <p className="text-slate-400 text-sm">No subjects assigned yet. Contact admin.</p>
        ) : (
          <div className="space-y-2">
            {subjects.map(s => (
              <Link key={s.id} to={`/faculty/subjects/${s.id}`} className="flex items-center justify-between p-3 rounded-lg border border-edu-border hover:border-primary-300 hover:bg-primary-50 transition-all group">
                <div>
                  <p className="font-medium text-slate-800">{s.name}</p>
                  <p className="text-xs text-slate-500 font-mono">{s.code}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-primary-600" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Subject Detail ───────────────────────────────────────────────────────────
function SubjectDetail() {
  const { subjectId } = useParams<{ subjectId: string }>();
  const id = parseInt(subjectId!);
  const [tab, setTab] = useState<'docs' | 'assessments' | 'submissions'>('docs');
  const [docs, setDocs] = useState<any[]>([]);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  // Assessment form
  const [showAssessForm, setShowAssessForm] = useState(false);
  const [assessForm, setAssessForm] = useState({ title: '', description: '', assessment_type: 'assignment', max_marks: 20, subject_id: id });

  useEffect(() => {
    facultyApi.listCourseDocs(id).then(r => setDocs(r.data));
    facultyApi.listAssessments(id).then(r => setAssessments(r.data));
    facultyApi.getSubmissions(id).then(r => setSubmissions(r.data));
  }, [id]);

  const handleDocUpload = async (e: React.ChangeEvent<HTMLInputElement>, docType: string) => {
    if (!e.target.files?.[0]) return;
    setUploading(true);
    try {
      await facultyApi.uploadCourseDoc(id, e.target.files[0], docType);
      setMsg('Document uploaded successfully!');
      facultyApi.listCourseDocs(id).then(r => setDocs(r.data));
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Upload failed'));
    } finally { setUploading(false); }
  };

  const buildIndex = async () => {
    setMsg('Building RAG index...');
    try {
      const r = await facultyApi.buildIndex(id);
      setMsg(r.data.message);
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Index build failed'));
    }
  };

  const createAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await facultyApi.createAssessment({ ...assessForm, subject_id: id });
      setMsg('Assessment created!');
      setShowAssessForm(false);
      facultyApi.listAssessments(id).then(r => setAssessments(r.data));
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  const tabs = ['docs', 'assessments', 'submissions'] as const;
  const tabLabels = { docs: 'Course Documents & Syllabus', assessments: 'Assessments', submissions: 'Submissions' };

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <Link to="/faculty/subjects" className="text-slate-400 text-sm hover:text-slate-600">Subjects</Link>
        <ChevronRight className="w-3 h-3 text-slate-400" />
        <span className="text-slate-800 font-medium text-sm">Subject #{id}</span>
      </div>

      {msg && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {msg}
        </div>
      )}

      <div className="flex gap-1 mb-6 border-b border-edu-border">
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t ? 'border-primary-600 text-primary-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            {tabLabels[t]}
            {t === 'submissions' && submissions.length > 0 && (
              <span className="ml-2 bg-primary-100 text-primary-700 text-xs rounded-full px-1.5">{submissions.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Documents Tab */}
      {tab === 'docs' && (
        <div className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-1">Upload Course Documents & Syllabus</h3>
            <p className="text-xs text-slate-500 mb-4">Upload subject syllabi, lecture notes, reference material, and rubrics. These documents automatically train the local RAG engine for student evaluations.</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {['syllabus', 'notes', 'reference', 'rubric'].map(type => (
                <label key={type} className="border-2 border-dashed border-edu-border rounded-xl p-4 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50 transition-all">
                  <Upload className="w-6 h-6 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm font-medium text-slate-700 capitalize">{type}</p>
                  <p className="text-xs text-slate-400">PDF, DOCX, PPTX, images</p>
                  <input type="file" className="hidden" accept=".pdf,.docx,.doc,.pptx,.ppt,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif" onChange={e => handleDocUpload(e, type)} disabled={uploading} />
                </label>
              ))}
            </div>
            {uploading && <p className="text-sm text-blue-600 mt-2">Uploading and extracting text...</p>}
          </div>

          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="font-semibold text-slate-800">Uploaded Course Documents</h3>
                <p className="text-xs text-slate-400">Documents available for evaluation reference</p>
              </div>
              <button onClick={buildIndex} className="btn-primary text-xs flex items-center gap-1.5">
                <Brain className="w-3.5 h-3.5" />
                Build RAG Index
              </button>
            </div>
            {docs.length === 0 ? (
              <p className="text-slate-400 text-sm py-4">No course documents uploaded yet. Upload a syllabus or lecture notes above.</p>
            ) : (
              <div className="space-y-2">
                {docs.map(d => (
                  <div key={d.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-slate-700">{d.original_filename}</p>
                      <p className="text-xs text-slate-400">{d.doc_type} · {d.page_count} pages · {d.file_type.toUpperCase()}</p>
                    </div>
                    <span className={d.is_indexed ? 'badge-approved' : 'badge-pending'}>
                      {d.is_indexed ? 'Indexed' : 'Pending'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      {/* Assessments Tab */}
      {tab === 'assessments' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-800">Assessments</h3>
            <button onClick={() => setShowAssessForm(!showAssessForm)} className="btn-primary text-sm">+ Create Assessment</button>
          </div>

          {showAssessForm && (
            <form onSubmit={createAssessment} className="card grid grid-cols-2 gap-4">
              <div><label className="text-xs font-medium text-slate-600">Title *</label><input className="input-field mt-1" value={assessForm.title} onChange={e => setAssessForm({...assessForm, title: e.target.value})} required /></div>
              <div>
                <label className="text-xs font-medium text-slate-600">Type</label>
                <select className="input-field mt-1" value={assessForm.assessment_type} onChange={e => setAssessForm({...assessForm, assessment_type: e.target.value})}>
                  <option value="assignment">Assignment</option>
                  <option value="journal">Journal</option>
                  <option value="presentation">Presentation</option>
                  <option value="report">Report</option>
                </select>
              </div>
              <div><label className="text-xs font-medium text-slate-600">Maximum Marks</label><input type="number" className="input-field mt-1" value={assessForm.max_marks} onChange={e => setAssessForm({...assessForm, max_marks: parseFloat(e.target.value)})} min={1} /></div>
              <div className="col-span-2"><label className="text-xs font-medium text-slate-600">Description</label><textarea className="input-field mt-1" rows={2} value={assessForm.description} onChange={e => setAssessForm({...assessForm, description: e.target.value})} /></div>
              <div className="col-span-2 flex gap-2">
                <button type="submit" className="btn-primary text-sm">Create</button>
                <button type="button" onClick={() => setShowAssessForm(false)} className="btn-secondary text-sm">Cancel</button>
              </div>
            </form>
          )}

          {assessments.map(a => (
            <div key={a.id} className="card">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-semibold text-slate-800">{a.title}</h4>
                  <p className="text-xs text-slate-500 mt-1">{a.assessment_type} · Max: {a.max_marks} marks</p>
                  {a.description && <p className="text-sm text-slate-600 mt-1">{a.description}</p>}
                </div>
                <Link to={`/faculty/assessments/${a.id}/rubric`} className="btn-secondary text-xs">
                  Manage Rubric
                </Link>
              </div>
            </div>
          ))}
          {assessments.length === 0 && <div className="card text-center text-slate-400 py-8">No assessments created yet</div>}
        </div>
      )}

      {/* Submissions Tab */}
      {tab === 'submissions' && (
        <div className="card">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Student</th><th className="text-left pb-2 text-slate-500 font-medium">Assessment</th><th className="text-left pb-2 text-slate-500 font-medium">File</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th><th className="pb-2"></th></tr></thead>
            <tbody>
              {submissions.map((s: any) => (
                <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                  <td className="py-3">
                    <p className="font-medium text-slate-800">{s.student_name}</p>
                    <p className="text-xs text-slate-400">{s.student_id}</p>
                  </td>
                  <td className="py-3 text-slate-600 text-xs">{s.assessment_title}</td>
                  <td className="py-3 text-slate-500 text-xs">{s.original_filename}</td>
                  <td className="py-3">
                    <span className={`badge-${s.status}`}>{s.status}</span>
                  </td>
                  <td className="py-3">
                    <Link to={`/faculty/submissions/${s.id}`} className="text-xs text-primary-600 hover:underline">
                      {s.has_evaluation ? 'View Evaluation' : 'Evaluate'}
                    </Link>
                  </td>
                </tr>
              ))}
              {submissions.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-slate-400">No submissions yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Rubric Manager ───────────────────────────────────────────────────────────
function RubricManager() {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const id = parseInt(assessmentId!);
  const [rubric, setRubric] = useState<any>(null);
  const [criteria, setCriteria] = useState([{ name: '', description: '', max_marks: 0 }]);
  const [totalMarks, setTotalMarks] = useState(20);
  const [msg, setMsg] = useState('');
  const [templates, setTemplates] = useState<any[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    facultyApi.getRubricTemplates().then(r => setTemplates(r.data)).catch(() => {});
    facultyApi.getRubric(id).then(r => {
      setRubric(r.data);
      setCriteria(r.data.criteria.map((c: any) => ({ name: c.name, description: c.description || '', max_marks: c.max_marks })));
      setTotalMarks(r.data.total_marks);
    }).catch(() => {});
  }, [id]);

  const addCriterion = () => setCriteria([...criteria, { name: '', description: '', max_marks: 0 }]);
  const removeCriterion = (i: number) => setCriteria(criteria.filter((_, idx) => idx !== i));

  const sumCriteria = criteria.reduce((s, c) => s + (parseFloat(String(c.max_marks)) || 0), 0);

  const applyTemplate = (templateId: string) => {
    const template = templates.find(item => item.id === templateId);
    if (!template) return;
    let allocated = 0;
    const next = template.criteria.map((criterion: any, index: number) => {
      const marks = index === template.criteria.length - 1
        ? Number((totalMarks - allocated).toFixed(2))
        : Number((totalMarks * criterion.proportion).toFixed(2));
      allocated += marks;
      return { name: criterion.name, description: criterion.description, max_marks: marks };
    });
    setCriteria(next);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (Math.abs(sumCriteria - totalMarks) > 0.5) {
      setMsg(`Error: Criteria sum (${sumCriteria}) must equal total marks (${totalMarks})`);
      return;
    }
    try {
      await facultyApi.createRubric(id, { total_marks: totalMarks, criteria });
      setMsg('Rubric saved successfully!');
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-6">
        <button onClick={() => navigate(-1)} className="text-slate-400 text-sm hover:text-slate-600">← Back</button>
        <span className="text-slate-800 font-medium text-sm">Assessment #{id} — Marking Rubric</span>
      </div>
      {msg && <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{msg}</div>}
      <form onSubmit={handleSubmit} className="card space-y-4">
        <div className="flex items-center gap-4">
          <div>
            <label className="text-xs font-medium text-slate-600">Total Maximum Marks</label>
            <input type="number" className="input-field mt-1 w-32" value={totalMarks} onChange={e => setTotalMarks(parseFloat(e.target.value))} min={1} />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600">Start from template</label>
            <select className="input-field mt-1" defaultValue="" onChange={e => applyTemplate(e.target.value)}>
              <option value="">Choose a preset...</option>
              {templates.map(template => <option key={template.id} value={template.id}>{template.name}</option>)}
            </select>
          </div>
          <div className="text-sm text-slate-500 mt-5">
            Criteria sum: <span className={Math.abs(sumCriteria - totalMarks) > 0.5 ? 'text-red-600 font-bold' : 'text-green-600 font-bold'}>{sumCriteria}</span> / {totalMarks}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-slate-700">Criteria</h4>
            <button type="button" onClick={addCriterion} className="btn-secondary text-xs">+ Add Criterion</button>
          </div>
          {criteria.map((c, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-start bg-slate-50 rounded-lg p-3">
              <div className="col-span-5">
                <label className="text-xs text-slate-500">Criterion Name *</label>
                <input className="input-field mt-1" value={c.name} onChange={e => { const nc = [...criteria]; nc[i].name = e.target.value; setCriteria(nc); }} required />
              </div>
              <div className="col-span-5">
                <label className="text-xs text-slate-500">Description</label>
                <input className="input-field mt-1" value={c.description} onChange={e => { const nc = [...criteria]; nc[i].description = e.target.value; setCriteria(nc); }} />
              </div>
              <div className="col-span-1">
                <label className="text-xs text-slate-500">Marks</label>
                <input type="number" className="input-field mt-1" value={c.max_marks} onChange={e => { const nc = [...criteria]; nc[i].max_marks = parseFloat(e.target.value) || 0; setCriteria(nc); }} min={0} />
              </div>
              <div className="col-span-1 mt-5">
                <button type="button" onClick={() => removeCriterion(i)} className="text-red-400 hover:text-red-600 p-1">✕</button>
              </div>
            </div>
          ))}
        </div>

        <button type="submit" className="btn-primary text-sm">Save Rubric</button>
      </form>
    </div>
  );
}

// ─── Evaluation Page ──────────────────────────────────────────────────────────
function SubmissionEvaluation() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const id = parseInt(submissionId!);
  const [submission, setSubmission] = useState<any>(null);
  const [evaluation, setEvaluation] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [msg, setMsg] = useState('');
  const [approveForm, setApproveForm] = useState({ faculty_total_score: 0, faculty_feedback: '', faculty_notes: '', publish_to_student: false });
  const [criterionOverrides, setCriterionOverrides] = useState<Record<number, number>>({});
  const navigate = useNavigate();

  const load = async () => {
    try {
      const sr = await facultyApi.getSubmissionDetail(id);
      setSubmission(sr.data);
      try {
        const er = await facultyApi.getEvaluation(id);
        setEvaluation(er.data);
        setApproveForm(f => ({
          ...f,
          faculty_total_score: er.data.faculty_total_score ?? er.data.ai_total_score ?? 0,
          faculty_feedback: er.data.faculty_feedback ?? er.data.ai_overall_feedback ?? '',
          faculty_notes: er.data.faculty_notes ?? '',
        }));
        setCriterionOverrides(Object.fromEntries(
          (er.data.criterion_scores || []).map((cs: any) => [cs.id, cs.faculty_score ?? cs.ai_score])
        ));
      } catch {}
    } catch { setMsg('Failed to load submission'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const triggerEval = async () => {
    setEvaluating(true);
    setMsg('Running AI evaluation...');
    try {
      await facultyApi.triggerEvaluation(id);
      await load();
      setMsg('AI evaluation completed successfully!');
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Evaluation failed'));
    } finally { setEvaluating(false); }
  };

  const handleApprove = async (publish: boolean) => {
    if (!evaluation) return;
    try {
      await facultyApi.approveEvaluation(evaluation.id, {
        ...approveForm,
        publish_to_student: publish,
        criterion_overrides: Object.entries(criterionOverrides).map(([criterion_score_id, faculty_score]) => ({
          criterion_score_id: Number(criterion_score_id),
          faculty_score,
        })),
      });
      setMsg(publish ? 'Evaluation approved and published to student!' : 'Evaluation approved!');
      await load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  const maximumMarks = Number(submission?.assessment_max_marks || 0);
  const setFacultyScore = (value: number) => {
    const score = Number.isFinite(value) ? Math.min(maximumMarks, Math.max(0, value)) : 0;
    setApproveForm(f => ({ ...f, faculty_total_score: score }));
  };

  const handleReject = async () => {
    if (!evaluation) return;
    try {
      await facultyApi.rejectEvaluation(evaluation.id);
      setMsg('Evaluation rejected');
      await load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  if (loading) return <div className="text-slate-500">Loading...</div>;

  return (
    <div>
      <button onClick={() => navigate(-1)} className="text-slate-400 text-sm hover:text-slate-600 mb-4 inline-flex items-center gap-1">
        ← Back
      </button>

      {msg && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
          {msg}
        </div>
      )}

      {/* Submission Info */}
      {submission && (
        <div className="card mb-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-800">{submission.student_name}</h2>
              <p className="text-sm text-slate-500">Student ID: {submission.student_id_num}</p>
              <p className="text-sm text-slate-600 mt-1">📄 {submission.original_filename} · {submission.assessment_title}</p>
              <p className="text-sm text-slate-600 mt-1">Subject: {submission.subject_name}</p>
              {submission.assessment_description && (
                <p className="text-sm text-slate-600 mt-1">Question / brief: {submission.assessment_description}</p>
              )}
              <p className="text-xs text-slate-400 mt-1">Submitted: {new Date(submission.submitted_at).toLocaleString()}</p>
            </div>
            <span className={`badge-${submission.status}`}>{submission.status}</span>
          </div>

          {submission.extracted_text && (
            <div className="mt-4">
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Extracted Submission Content</h4>
              <div className="bg-slate-50 rounded-lg p-3 max-h-48 overflow-y-auto">
                <p className="text-sm text-slate-700 whitespace-pre-wrap font-mono leading-relaxed">
                  {submission.extracted_text.slice(0, 2000)}{submission.extracted_text.length > 2000 ? '...' : ''}
                </p>
              </div>
            </div>
          )}

          {!evaluation && (
            <div className="mt-4">
              <button
                onClick={triggerEval}
                disabled={evaluating}
                className="btn-primary flex items-center gap-2"
              >
                <Brain className="w-4 h-4" />
                {evaluating ? 'Running AI Evaluation...' : '🤖 Trigger AI Evaluation'}
              </button>
              {submission.extraction_status !== 'success' && (
                <div className="flex items-start gap-2 mt-2 p-2 bg-amber-50 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                  <p className="text-xs text-amber-700">Extraction status: {submission.extraction_status}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Evaluation Results */}
      {evaluation && (
        <div className="space-y-4">
          {/* Score Overview */}
          <div className="card bg-gradient-to-r from-primary-50 to-indigo-50 border-primary-200">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-bold text-slate-800">AI Evaluation Results</h3>
              <span className={`badge-${evaluation.status}`}>{evaluation.status}</span>
            </div>
            <div className="flex items-center gap-6">
              <div>
                <p className="text-xs text-slate-500">AI Estimated Score</p>
                <p className="text-3xl font-bold text-primary-700">{evaluation.ai_total_score?.toFixed(1)}</p>
              </div>
              <div className="text-slate-300 text-2xl">/</div>
              <div>
                <p className="text-xs text-slate-500">Maximum Marks</p>
                <p className="text-3xl font-bold text-slate-600">{submission?.assessment_max_marks || '?'}</p>
              </div>
              {evaluation.ai_feedback && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold uppercase text-amber-800">Subject relevance check</p>
                  <p className="mt-1 text-sm text-amber-700 whitespace-pre-wrap">{evaluation.ai_feedback}</p>
                </div>
              )}
            </div>
          </div>

          {/* Criterion Scores */}
          {evaluation.criterion_scores?.length > 0 && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-3">Criterion-wise Scores</h4>
              <div className="space-y-2">
                {evaluation.criterion_scores.map((cs: any) => (
                  <div key={cs.id} className="flex items-center gap-3 p-2 bg-slate-50 rounded-lg">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-700">{cs.criterion_name}</p>
                      {cs.justification && <p className="text-xs text-slate-400 mt-0.5">{cs.justification}</p>}
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-bold text-primary-700">{(cs.faculty_score ?? cs.ai_score)?.toFixed(1)}</span>
                      <span className="text-xs text-slate-400"> / {cs.max_marks}</span>
                    </div>
                    <div className="w-20 bg-slate-200 rounded-full h-1.5">
                      <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, (cs.ai_score / cs.max_marks) * 100)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strengths & Weaknesses */}
          <div className="grid grid-cols-2 gap-4">
            <div className="card border-green-200 bg-green-50">
              <h4 className="font-semibold text-green-800 mb-2">✅ Strengths</h4>
              <p className="text-sm text-green-700 whitespace-pre-wrap">{evaluation.ai_strengths || 'No strengths noted'}</p>
            </div>
            <div className="card border-red-200 bg-red-50">
              <h4 className="font-semibold text-red-800 mb-2">⚠️ Weaknesses</h4>
              <p className="text-sm text-red-700 whitespace-pre-wrap">{evaluation.ai_weaknesses || 'None identified'}</p>
            </div>
          </div>

          {evaluation.ai_missing_concepts && (
            <div className="card border-amber-200 bg-amber-50">
              <h4 className="font-semibold text-amber-800 mb-2">🔍 Missing Concepts</h4>
              <p className="text-sm text-amber-700 whitespace-pre-wrap">{evaluation.ai_missing_concepts}</p>
            </div>
          )}

          {evaluation.ai_improvement_suggestions && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-2">💡 Improvement Suggestions</h4>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{evaluation.ai_improvement_suggestions}</p>
            </div>
          )}

          {evaluation.ai_overall_feedback && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-2">📝 Overall Feedback</h4>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{evaluation.ai_overall_feedback}</p>
            </div>
          )}

          {(evaluation.comparative_analysis_feedback || evaluation.style_feedback?.length || evaluation.language_errors?.length) && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-3">Detailed Analysis</h4>
              {evaluation.comparative_analysis_feedback && (
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase text-slate-500">Comparative analysis</p>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap mt-1">{evaluation.comparative_analysis_feedback}</p>
                </div>
              )}
              {evaluation.style_feedback?.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-semibold uppercase text-slate-500">Style</p>
                  <ul className="list-disc pl-5 text-sm text-slate-700">{evaluation.style_feedback.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul>
                </div>
              )}
              {evaluation.language_errors?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">Language and proofreading</p>
                  <ul className="list-disc pl-5 text-sm text-slate-700">{evaluation.language_errors.map((item: string, i: number) => <li key={i}>{item}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {evaluation.line_feedback?.length > 0 && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-3">Line-level feedback</h4>
              <div className="space-y-2">
                {evaluation.line_feedback.map((item: any, i: number) => (
                  <div key={i} className="border-l-4 border-primary-300 pl-3">
                    <p className="text-xs font-semibold text-slate-500">Line {item.line_number} · {item.category}</p>
                    <p className="text-sm text-slate-700">{item.comment}</p>
                    {item.suggested_revision && <p className="text-xs text-primary-700 mt-1">Suggested revision: {item.suggested_revision}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Supporting Evidence */}
          {evaluation.supporting_evidence?.length > 0 && (
            <div className="card">
              <h4 className="font-semibold text-slate-800 mb-3">📎 Supporting Evidence</h4>
              <div className="space-y-2">
                {evaluation.supporting_evidence.map((e: any) => (
                  <div key={e.id} className="bg-slate-50 rounded-lg p-3 border-l-4 border-primary-400">
                    <p className="text-sm text-slate-700 italic">"{e.evidence_text}"</p>
                    {e.relevance_note && <p className="text-xs text-slate-500 mt-1">{e.relevance_note}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Faculty Review Section - remains editable after approval and re-evaluation */}
          <div id="faculty-score-editor" className="card">
              <h4 className="font-semibold text-slate-800 mb-4">Faculty Review & Edit</h4>
              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-600">Faculty Final Score</label>
                    <span className="text-xs font-semibold text-primary-700">
                      {approveForm.faculty_total_score} / {maximumMarks}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-3">
                    <input
                      type="range"
                      className="w-full accent-primary-600"
                      value={approveForm.faculty_total_score}
                      onChange={e => setFacultyScore(parseFloat(e.target.value))}
                      min={0}
                      max={maximumMarks}
                      step={0.5}
                      aria-label={`Faculty final score out of ${maximumMarks}`}
                    />
                    <input
                      type="number"
                      className="input-field w-24"
                      value={approveForm.faculty_total_score}
                      onChange={e => setFacultyScore(parseFloat(e.target.value))}
                      min={0}
                      max={maximumMarks}
                      step={0.5}
                      aria-label="Faculty final score"
                    />
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Move the slider or enter a score from 0 to {maximumMarks}.
                  </p>
                </div>
                {evaluation.criterion_scores?.length > 0 && (
                  <div>
                    <label className="text-xs font-medium text-slate-600">Criterion marks (editable)</label>
                    <div className="mt-2 space-y-2">
                      {evaluation.criterion_scores.map((cs: any) => (
                        <div key={cs.id} className="flex items-center gap-2">
                          <span className="flex-1 text-sm text-slate-700">{cs.criterion_name}</span>
                          <input
                            type="number"
                            className="input-field w-24"
                            min={0}
                            max={cs.max_marks}
                            step={0.5}
                            value={criterionOverrides[cs.id] ?? cs.ai_score}
                            onChange={e => setCriterionOverrides({
                              ...criterionOverrides,
                              [cs.id]: parseFloat(e.target.value),
                            })}
                          />
                          <span className="text-xs text-slate-400">/ {cs.max_marks}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <label className="text-xs font-medium text-slate-600">Faculty Feedback (optional override)</label>
                  <textarea className="input-field mt-1" rows={3}
                    value={approveForm.faculty_feedback}
                    onChange={e => setApproveForm({ ...approveForm, faculty_feedback: e.target.value })} />
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600">Faculty Notes (internal)</label>
                  <input className="input-field mt-1"
                    value={approveForm.faculty_notes}
                    onChange={e => setApproveForm({ ...approveForm, faculty_notes: e.target.value })} />
                </div>
                <div className="flex gap-3 pt-2">
                  <button onClick={() => handleApprove(false)} className="btn-success flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" /> {evaluation.status === 'approved' ? 'Save Changes' : 'Approve'}
                  </button>
                  <button onClick={() => handleApprove(true)} className="btn-primary flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" /> Save & Publish to Student
                  </button>
                  {evaluation.status !== 'approved' && (
                    <button onClick={handleReject} className="btn-danger flex items-center gap-2">
                      <XCircle className="w-4 h-4" /> Reject
                    </button>
                  )}
                  <button onClick={triggerEval} disabled={evaluating} className="btn-secondary text-sm flex items-center gap-1.5">
                    <Brain className="w-3.5 h-3.5" /> Re-evaluate
                  </button>
                </div>
              </div>
          </div>

          {(evaluation.status === 'approved' || evaluation.status === 'rejected') && (
            <div className={`card border-2 ${evaluation.status === 'approved' ? 'border-green-300 bg-green-50' : 'border-red-300 bg-red-50'}`}>
              <div className="flex items-center gap-2">
                {evaluation.status === 'approved' ? <CheckCircle className="w-5 h-5 text-green-600" /> : <XCircle className="w-5 h-5 text-red-600" />}
                <span className="font-semibold capitalize text-slate-800">Evaluation {evaluation.status}</span>
              </div>
              {evaluation.faculty_total_score !== null && (
                <p className="text-sm text-slate-600 mt-2">Final Score: <strong>{evaluation.faculty_total_score}</strong></p>
              )}
              <button
                onClick={() => {
                  document.getElementById('faculty-score-editor')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }}
                className="btn-secondary text-xs mt-3"
              >
                Edit Score & Feedback
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Subject List ─────────────────────────────────────────────────────────────
function SubjectList() {
  const [subjects, setSubjects] = useState<any[]>([]);
  useEffect(() => { facultyApi.getSubjects().then(r => setSubjects(r.data)); }, []);
  return (
    <div>
      <h2 className="text-xl font-bold text-slate-800 mb-6">My Subjects</h2>
      <div className="grid gap-4">
        {subjects.map(s => (
          <Link key={s.id} to={`/faculty/subjects/${s.id}`}
            className="card hover:border-primary-300 hover:shadow-md transition-all group cursor-pointer">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-800 group-hover:text-primary-700">{s.name}</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{s.code}</p>
                {s.description && <p className="text-sm text-slate-500 mt-1">{s.description}</p>}
              </div>
              <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-primary-600" />
            </div>
          </Link>
        ))}
        {subjects.length === 0 && (
          <div className="card text-center py-10 text-slate-400">
            <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p>No subjects assigned. Contact admin.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Evaluations List ─────────────────────────────────────────────────────────
function EvaluationsList() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [allSubmissions, setAllSubmissions] = useState<any[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    facultyApi.getSubjects().then(async r => {
      setSubjects(r.data);
      const all: any[] = [];
      for (const s of r.data) {
        try {
          const sr = await facultyApi.getSubmissions(s.id);
          all.push(...sr.data);
        } catch {}
      }
      setAllSubmissions(all);
    });
  }, []);

  return (
    <div>
      <h2 className="text-xl font-bold text-slate-800 mb-6">Submissions & Evaluations</h2>
      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Student</th><th className="text-left pb-2 text-slate-500 font-medium">Assessment</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th><th className="text-left pb-2 text-slate-500 font-medium">Evaluated?</th><th className="pb-2"></th></tr></thead>
          <tbody>
            {allSubmissions.map(s => (
              <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-3 font-medium text-slate-800">{s.student_name}</td>
                <td className="py-3 text-slate-500 text-xs">{s.assessment_title}</td>
                <td className="py-3"><span className={`badge-${s.status}`}>{s.status}</span></td>
                <td className="py-3">
                  {s.has_evaluation ? <span className="badge-evaluated">Yes</span> : <span className="badge-pending">No</span>}
                </td>
                <td className="py-3">
                  <button onClick={() => navigate(`/faculty/submissions/${s.id}`)} className="text-xs text-primary-600 hover:underline">
                    Open →
                  </button>
                </td>
              </tr>
            ))}
            {allSubmissions.length === 0 && <tr><td colSpan={5} className="py-8 text-center text-slate-400">No submissions yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Faculty Portal ───────────────────────────────────────────────────────────
export default function FacultyPortal() {
  return (
    <DashboardLayout navItems={navItems} portalLabel="Faculty Portal" portalColor="bg-primary-700">
      <Routes>
        <Route path="/" element={<FacultyDashboard />} />
        <Route path="/subjects" element={<SubjectList />} />
        <Route path="/subjects/:subjectId" element={<SubjectDetail />} />
        <Route path="/assessments/:assessmentId/rubric" element={<RubricManager />} />
        <Route path="/submissions/:submissionId" element={<SubmissionEvaluation />} />
        <Route path="/evaluations" element={<EvaluationsList />} />
      </Routes>
    </DashboardLayout>
  );
}
