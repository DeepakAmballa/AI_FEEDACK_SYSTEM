import React, { useEffect, useState } from 'react';
import { Routes, Route, Link, useNavigate, useParams } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import FeedbackDocument from '../../components/shared/FeedbackDocument';
import toast from 'react-hot-toast';
import { facultyApi } from '../../api/client';
import {
  LayoutDashboard, BookOpen, FileText, Users,
  Upload, CheckCircle, XCircle, Edit3,
  ChevronRight, AlertTriangle, Star, Eye, Download,
  Info, Save, Send, HelpCircle, Brain
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/faculty', icon: LayoutDashboard },
  { label: 'My Subjects', to: '/faculty/subjects', icon: BookOpen, match: ['/faculty/assessments'] },
  { label: 'Evaluations', to: '/faculty/evaluations', icon: FileText, match: ['/faculty/submissions'] },
];

// ─── Faculty Dashboard ────────────────────────────────────────────────────────
function FacultyDashboard() {
  const [subjects, setSubjects] = useState<any[]>([]);
  useEffect(() => { facultyApi.getSubjects().then(r => setSubjects(r.data)); }, []);
  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Faculty Dashboard</h2>
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
/** Course-profile units may be stored as structured JSON or as legacy text ("Unit 1: ...\nUnit 2: ..."). */
function normalizeUnits(raw: any): { unit_number?: number | string; unit_name: string; topics: string[] }[] {
  if (!raw) return [];
  if (typeof raw === 'string') {
    try { return normalizeUnits(JSON.parse(raw)); } catch { /* plain text */ }
    return raw.split(/\n+/).map(l => l.trim()).filter(Boolean).map((line, i) => {
      const m = line.match(/^(?:unit|module)\s*(\d+)\s*[:.-]\s*(.*)$/i);
      return { unit_number: m ? Number(m[1]) : i + 1, unit_name: (m ? m[2] : line).replace(/\.$/, ''), topics: [] };
    });
  }
  if (!Array.isArray(raw)) return [];
  return raw.map((u: any, i: number) => typeof u === 'string'
    ? { unit_number: i + 1, unit_name: u, topics: [] }
    : {
      unit_number: u.unit_number ?? u.number ?? i + 1,
      unit_name: u.unit_name ?? u.name ?? u.title ?? '',
      topics: Array.isArray(u.topics) ? u.topics.map((t: any) => (typeof t === 'string' ? t : t.name || t.topic_name || '')) : [],
    });
}

function SubjectDetail() {
  const { subjectId } = useParams<{ subjectId: string }>();
  const id = parseInt(subjectId!);
  const [tab, setTab] = useState<'docs' | 'profile' | 'assessments' | 'submissions'>('docs');
  const [docs, setDocs] = useState<any[]>([]);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [submissionDateFrom, setSubmissionDateFrom] = useState('');
  const [submissionDateTo, setSubmissionDateTo] = useState('');
  const [msg, setMsg] = useState('');
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  // Typed course profile state
  const [courseProfile, setCourseProfile] = useState<any>({
    title: '',
    description: '',
    syllabus: '',
    learning_objectives: '',
    expected_outcomes: '',
    reference_content: '',
    learning_materials: '',
    additional_info: '',
    units_topics: [],
    is_typed_published: false,
  });
  const [savingProfile, setSavingProfile] = useState(false);

  const units: { unit_number?: number | string; unit_name: string; topics: string[] }[] = normalizeUnits(courseProfile.units_topics);

  const openSubmissionFile = async (submissionId: number, download: boolean) => {
    try {
      const response = await facultyApi.getSubmissionFile(submissionId, download);
      const url = URL.createObjectURL(response.data);
      if (download) {
        const link = document.createElement('a');
        link.href = url;
        link.download = 'student-submission';
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Unable to access submission file'));
    }
  };

  useEffect(() => {
    facultyApi.listCourseDocs(id).then(r => setDocs(r.data));
    facultyApi.listAssessments(id).then(r => setAssessments(r.data));
    facultyApi.getSubmissions(id).then(r => setSubmissions(r.data));
    facultyApi.getCourseProfile(id).then(r => {
      if (r.data) {
        setCourseProfile({ ...r.data, units_topics: normalizeUnits(r.data.units_topics) });
      }
    });
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

  const handleSaveTypedProfile = async (publish: boolean) => {
    setSavingProfile(true);
    setMsg(publish ? 'Publishing and indexing course profile in FAISS...' : 'Saving draft course profile...');
    try {
      const r = await facultyApi.saveTypedCourseProfile(id, {
        ...courseProfile,
        units_topics: normalizeUnits(courseProfile.units_topics)
          .filter(u => u.unit_name.trim())
          .map(u => ({ ...u, unit_name: u.unit_name.trim(), topics: u.topics.map(t => t.trim()).filter(Boolean) })),
        is_published: publish,
      });
      setCourseProfile({ ...r.data, units_topics: normalizeUnits(r.data.units_topics) });
      setMsg(publish ? '✅ Course profile published and successfully indexed in local RAG!' : 'Course profile draft saved successfully.');
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed to save course profile'));
    } finally {
      setSavingProfile(false);
    }
  };

  const tabs = ['docs', 'profile', 'assessments', 'submissions'] as const;
  const tabLabels = {
    docs: 'Course Documents',
    profile: 'Type Course Profile',
    assessments: 'Assessments',
    submissions: 'Submissions'
  };
  const visibleSubmissions = submissions
    .filter((submission: any) => {
      const submittedDate = new Date(submission.submitted_at).toISOString().slice(0, 10);
      return (!submissionDateFrom || submittedDate >= submissionDateFrom)
        && (!submissionDateTo || submittedDate <= submissionDateTo);
    })
    .sort((a: any, b: any) => (
      new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime()
    ));

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
            <h3 className="font-semibold text-slate-800 mb-1">Option 1: Upload Course Documents & Syllabus</h3>
            <p className="text-xs text-slate-500 mb-4">Upload subject syllabi, lecture notes, reference material, and rubrics. These documents train the local RAG engine for student evaluations.</p>
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

      {/* Type Course Profile Tab */}
      {tab === 'profile' && (
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-800">Option 2: Type Course Profile Editor</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Type the syllabus, learning objectives, outcomes, and materials directly. Publishing automatically embeds and indexes the content for RAG.
              </p>
            </div>
            <span className={courseProfile.is_typed_published ? 'badge-approved' : 'badge-pending'}>
              {courseProfile.is_typed_published ? 'Published & Indexed' : 'Draft'}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-600">Course / Subject Title</label>
              <input
                className="input-field mt-1"
                value={courseProfile.title || ''}
                onChange={e => setCourseProfile({ ...courseProfile, title: e.target.value })}
                placeholder="e.g. Distributed Operating Systems"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Course Description</label>
              <input
                className="input-field mt-1"
                value={courseProfile.description || ''}
                onChange={e => setCourseProfile({ ...courseProfile, description: e.target.value })}
                placeholder="Brief course overview"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">Course Syllabus & Units</label>
            <textarea
              className="input-field mt-1"
              rows={4}
              value={courseProfile.syllabus || ''}
              onChange={e => setCourseProfile({ ...courseProfile, syllabus: e.target.value })}
              placeholder="Unit 1: Concurrency and Synchronization&#10;Unit 2: Distributed File Systems&#10;Unit 3: Fault Tolerance..."
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-600">Course Learning Objectives</label>
              <textarea
                className="input-field mt-1"
                rows={3}
                value={courseProfile.learning_objectives || ''}
                onChange={e => setCourseProfile({ ...courseProfile, learning_objectives: e.target.value })}
                placeholder="Key concepts students must learn"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Expected Course Outcomes</label>
              <textarea
                className="input-field mt-1"
                rows={3}
                value={courseProfile.expected_outcomes || ''}
                onChange={e => setCourseProfile({ ...courseProfile, expected_outcomes: e.target.value })}
                placeholder="Specific abilities students should demonstrate"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-600">Reference Content & Academic Standard</label>
              <textarea
                className="input-field mt-1"
                rows={3}
                value={courseProfile.reference_content || ''}
                onChange={e => setCourseProfile({ ...courseProfile, reference_content: e.target.value })}
                placeholder="Important reference definitions, principles, and concepts"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Recommended Learning Materials</label>
              <textarea
                className="input-field mt-1"
                rows={3}
                value={courseProfile.learning_materials || ''}
                onChange={e => setCourseProfile({ ...courseProfile, learning_materials: e.target.value })}
                placeholder="Textbooks, research papers, lab manuals"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-600">Units / modules and topics</label>
              <button type="button" className="btn-ghost text-xs py-1"
                onClick={() => setCourseProfile({ ...courseProfile, units_topics: [...units, { unit_number: units.length + 1, unit_name: '', topics: [] }] })}>
                + Add unit
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mb-2">Assessments are linked to a unit; the AI evaluates against that unit's topics.</p>
            <div className="space-y-2">
              {units.length === 0 && <p className="text-xs text-slate-400 italic">No units yet.</p>}
              {units.map((u, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-start">
                  <input className="input-field col-span-2" value={u.unit_number ?? ''} aria-label="Unit number"
                    onChange={e => { const next = [...units]; next[i] = { ...u, unit_number: e.target.value }; setCourseProfile({ ...courseProfile, units_topics: next }); }} />
                  <input className="input-field col-span-4" value={u.unit_name} placeholder="Unit name"
                    onChange={e => { const next = [...units]; next[i] = { ...u, unit_name: e.target.value }; setCourseProfile({ ...courseProfile, units_topics: next }); }} />
                  <input className="input-field col-span-5" value={u.topics.join(', ')} placeholder="Topics, comma separated"
                    onChange={e => { const next = [...units]; next[i] = { ...u, topics: e.target.value.split(',').map(t => t.trimStart()) }; setCourseProfile({ ...courseProfile, units_topics: next }); }} />
                  <button type="button" className="icon-btn col-span-1" aria-label="Remove unit"
                    onClick={() => setCourseProfile({ ...courseProfile, units_topics: units.filter((_, j) => j !== i) })}>
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">Additional Academic Information</label>
            <input
              className="input-field mt-1"
              value={courseProfile.additional_info || ''}
              onChange={e => setCourseProfile({ ...courseProfile, additional_info: e.target.value })}
              placeholder="Evaluation policies, grading notes, or prerequisites"
            />
          </div>

          <div className="flex gap-3 pt-3 border-t border-edu-border">
            <button
              onClick={() => handleSaveTypedProfile(false)}
              disabled={savingProfile}
              className="btn-secondary text-sm"
            >
              Save as Draft
            </button>
            <button
              onClick={() => handleSaveTypedProfile(true)}
              disabled={savingProfile}
              className="btn-primary text-sm flex items-center gap-1.5"
            >
              <Brain className="w-4 h-4" />
              {savingProfile ? 'Publishing & Indexing...' : 'Publish Course Profile & Index RAG'}
            </button>
          </div>
        </div>
      )}

      {/* Assessments Tab — created and maintained by the admin */}
      {tab === 'assessments' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="font-semibold text-slate-900">Assessments</h3>
              <p className="text-xs text-slate-500">Assessments and their RTLP rubrics are created by the admin and mapped to this subject.</p>
            </div>
          </div>
          {assessments.map(a => (
            <div key={a.id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h4 className="font-semibold text-slate-900">{a.title}</h4>
                  <p className="text-xs text-slate-500 mt-1">
                    <span className="font-medium text-primary-700">{a.rubric_source || a.assessment_type}</span>
                    {' '}· {a.max_marks} marks
                    {a.due_date && ` · Due ${new Date(a.due_date).toLocaleDateString()}`}
                    {a.course_unit && ` · ${a.course_unit}`}
                    {a.has_answer_key && ' · Answer key on file'}
                  </p>
                  {a.description && <p className="text-sm text-slate-600 mt-2">{a.description}</p>}
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <span className="badge-neutral">{a.submission_count} submission{a.submission_count === 1 ? '' : 's'}</span>
                  {a.shared_with?.length > 0 && <span className="text-[11px] text-slate-400">Shared with {a.shared_with.length} other subject{a.shared_with.length === 1 ? '' : 's'}</span>}
                </div>
              </div>
              {a.criteria?.length > 0 && (
                <details className="mt-3">
                  <summary className="text-xs font-medium text-primary-700 cursor-pointer select-none">Rubric ({a.criteria.length} criteria)</summary>
                  <div className="mt-2 space-y-2">
                    {a.criteria.map((c: any) => (
                      <div key={c.name} className="rounded-lg border border-slate-200 p-3">
                        <p className="text-sm font-medium text-slate-800 flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c.color }} />
                          {c.label}. {c.name} <span className="text-xs text-slate-400 font-normal">· {c.max_marks} marks</span>
                        </p>
                        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-2 mt-2">
                          {(c.levels || []).map((l: any) => (
                            <div key={l.name} className="text-[11px] bg-slate-50 rounded-md p-2">
                              <p className="font-semibold text-slate-700">{l.name} <span className="font-normal text-slate-400">({l.min_marks}–{l.max_marks})</span></p>
                              <p className="text-slate-600 mt-0.5">{l.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
          {assessments.length === 0 && (
            <div className="card text-center text-slate-400 py-8">No assessments have been assigned to this subject yet. The admin creates and maps assessments.</div>
          )}
        </div>
      )}

      {/* Submissions Tab */}
      {tab === 'submissions' && (
        <div className="space-y-3">
          <div className="card flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs text-slate-500 block">Submitted from</label>
              <input
                type="date"
                className="input-field text-sm mt-1"
                value={submissionDateFrom}
                onChange={e => setSubmissionDateFrom(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 block">Submitted to</label>
              <input
                type="date"
                className="input-field text-sm mt-1"
                value={submissionDateTo}
                onChange={e => setSubmissionDateTo(e.target.value)}
              />
            </div>
            {(submissionDateFrom || submissionDateTo) && (
              <button
                type="button"
                className="btn-secondary text-sm"
                onClick={() => {
                  setSubmissionDateFrom('');
                  setSubmissionDateTo('');
                }}
              >
                Clear dates
              </button>
            )}
            <p className="text-xs text-slate-400 ml-auto">
              Showing newest submissions first ({visibleSubmissions.length})
            </p>
          </div>
          <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-edu-border">
                <th className="text-left pb-2 text-slate-500 font-medium">Student</th>
                <th className="text-left pb-2 text-slate-500 font-medium">Assessment</th>
                <th className="text-left pb-2 text-slate-500 font-medium">Format</th>
                <th className="text-left pb-2 text-slate-500 font-medium">Status</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleSubmissions.map((s: any) => (
                <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                  <td className="py-3">
                    <p className="font-medium text-slate-800">{s.student_name}</p>
                    <p className="text-xs text-slate-400">{s.student_id}</p>
                  </td>
                  <td className="py-3 text-slate-600 text-xs">{s.assessment_title}</td>
                  <td className="py-3 text-slate-500 text-xs capitalize">
                    {s.file_type ? s.file_type.toUpperCase() : 'Typed'}
                  </td>
                  <td className="py-3">
                    <span className={`badge-${s.status}`}>{s.status}</span>
                  </td>
                  <td className="py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {s.original_filename && (
                        <>
                          <button
                            onClick={() => openSubmissionFile(s.id, false)}
                            className="text-xs text-slate-600 hover:text-slate-900 inline-flex items-center gap-1"
                          >
                            <Eye className="w-3.5 h-3.5" /> View File
                          </button>
                          <button
                            onClick={() => openSubmissionFile(s.id, true)}
                            className="text-xs text-slate-600 hover:text-slate-900 inline-flex items-center gap-1"
                          >
                            <Download className="w-3.5 h-3.5" /> Download
                          </button>
                        </>
                      )}
                      <Link to={`/faculty/submissions/${s.id}`} className="btn-primary text-xs flex items-center gap-1">
                        <Edit3 className="w-3.5 h-3.5" /> Evaluate
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {visibleSubmissions.length === 0 && (
                <tr><td colSpan={5} className="py-8 text-center text-slate-400">No submissions yet</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </div>
  );
}

function fmt(n: number) {
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '');
}

function SubmissionEvaluation() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const id = parseInt(submissionId!);
  const navigate = useNavigate();
  const [context, setContext] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: 'error' | 'success' | 'info'; text: string } | null>(null);
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [overall, setOverall] = useState('');
  const [notes, setNotes] = useState('');
  const [state, setState] = useState<any>(null);
  const [docOpen, setDocOpen] = useState(false);
  const [doc, setDoc] = useState<any>(null);
  const [pdfBusy, setPdfBusy] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const { data } = await facultyApi.getEvaluationContext(id);
      setContext(data);
      setState(data.evaluation_state);
      const fe = data.faculty_evaluation;
      const m: Record<string, string> = {};
      for (const cm of fe?.criterion_marks || []) m[cm.criterion_name] = String(cm.score);
      setMarks(m);
      setOverall(fe?.overall_feedback || '');
      setNotes(fe?.internal_notes || '');
    } catch (err: any) {
      setMsg({ type: 'error', text: 'Failed to load submission: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [id]);

  // Poll the AI step while it runs
  useEffect(() => {
    if (!state || !['processing', 'pending'].includes(state.ai_status)) return;
    const t = window.setInterval(async () => {
      try {
        const { data } = await facultyApi.getEvaluationStatus(id);
        setState(data);
        if (data.published) toast.success('Feedback document published to the student');
      } catch { /* keep polling */ }
    }, 4000);
    return () => window.clearInterval(t);
  }, [state?.ai_status, id]);

  const criteria: any[] = context?.rubric_reference?.criteria || [];
  const maxMarks: number = context?.max_marks || 20;
  const total = criteria.reduce((sum, c) => sum + (parseFloat(marks[c.name]) || 0), 0);
  const allMarked = criteria.length > 0 && criteria.every(c => marks[c.name] !== undefined && marks[c.name] !== '');
  const isFinal = context?.faculty_evaluation && !context.faculty_evaluation.is_draft;

  const setMark = (name: string, value: string, max: number) => {
    if (value === '') { setMarks(m => ({ ...m, [name]: '' })); return; }
    const v = Math.max(0, Math.min(max, parseFloat(value)));
    if (!isNaN(v)) setMarks(m => ({ ...m, [name]: String(v) }));
  };

  const levelFor = (c: any) => {
    const v = parseFloat(marks[c.name]);
    if (isNaN(v)) return null;
    return [...(c.levels || [])].sort((a, b) => b.level - a.level).find(l => v + 1e-9 >= (l.min_marks ?? 0)) || null;
  };

  const save = async (isDraft: boolean) => {
    if (!isDraft) {
      if (!allMarked) { setMsg({ type: 'error', text: 'Enter a mark for every rubric criterion before submitting.' }); return; }
      if (!overall.trim()) { setMsg({ type: 'error', text: 'Overall feedback is required — the student sees it as “Faculty comments”.' }); return; }
    }
    try {
      setSaving(true);
      setMsg(null);
      const { data } = await facultyApi.submitManualEvaluation(id, {
        faculty_total_marks: Number(total.toFixed(2)),
        criterion_marks: criteria.filter(c => marks[c.name] !== undefined && marks[c.name] !== '')
          .map(c => ({ criterion_name: c.name, score: parseFloat(marks[c.name]) })),
        overall_feedback: overall,
        internal_notes: notes,
        is_draft: isDraft,
      });
      setMsg({ type: 'success', text: data.message });
      await load();
    } catch (err: any) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Failed to save evaluation' });
    } finally {
      setSaving(false);
    }
  };

  const openDocument = async () => {
    try {
      const { data } = await facultyApi.getFeedbackDocument(id);
      setDoc(data);
      setDocOpen(true);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Feedback document not available yet');
    }
  };

  const downloadPdf = async () => {
    try {
      setPdfBusy(true);
      const res = await facultyApi.downloadFeedbackPdf(id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = `feedback-${id}.pdf`; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch { toast.error('Unable to download the PDF'); } finally { setPdfBusy(false); }
  };

  const openSubmissionFile = async (download: boolean) => {
    try {
      const response = await facultyApi.getSubmissionFile(id, download);
      const url = URL.createObjectURL(response.data);
      if (download) {
        const link = document.createElement('a');
        link.href = url; link.download = context?.original_filename || 'student-submission';
        document.body.appendChild(link); link.click(); link.remove();
      } else {
        window.open(url, '_blank', 'noopener,noreferrer');
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err: any) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Unable to access submission file' });
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading submission…</div>;
  if (!context) return <div className="card text-red-600">{msg?.text || 'Submission not available.'}</div>;

  const aiStatus = state?.ai_status;
  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <button onClick={() => navigate(-1)} className="text-slate-500 hover:text-slate-800 text-sm mb-2">← Back</button>
          <h1 className="page-title">{context.student_name}</h1>
          <p className="page-subtitle">
            {context.subject_name} · {context.assessment_title} ·{' '}
            <span className="font-medium text-slate-700">{context.rtlp_code ? `RTLP ${context.rtlp_code} ` : ''}{context.assessment_type}</span>
            {context.course_unit ? ` · ${context.course_unit}` : ''}
          </p>
        </div>
        <span className={isFinal ? 'badge-approved' : context.faculty_evaluation ? 'badge-pending' : 'badge-neutral'}>
          {isFinal ? 'Faculty evaluation submitted' : context.faculty_evaluation ? 'Draft saved' : 'Awaiting your evaluation'}
        </span>
      </div>

      {msg && (
        <div className={`p-3.5 rounded-lg text-sm border ${msg.type === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200'}`}>
          {msg.text}
        </div>
      )}

      {/* AI step + publication status (never shows the AI marks) */}
      {isFinal && (
        <div className="card flex flex-wrap items-center justify-between gap-3 py-4">
          <div className="flex items-center gap-3">
            {aiStatus === 'completed' && state?.published ? <CheckCircle className="w-5 h-5 text-emerald-600" />
              : aiStatus === 'failed' ? <XCircle className="w-5 h-5 text-red-600" />
              : <Brain className="w-5 h-5 text-primary-600 animate-pulse" />}
            <div>
              <p className="text-sm font-semibold text-slate-900">
                {aiStatus === 'completed' && state?.published ? 'Feedback document published to the student'
                  : aiStatus === 'failed' ? 'AI evaluation failed'
                  : 'AI evaluation in progress…'}
              </p>
              <p className="text-xs text-slate-500">
                {aiStatus === 'failed' ? (state?.ai_error || 'The admin can retry it from Evaluation Monitor.')
                  : 'The AI evaluates independently against the same RTLP rubric and course profile. The student’s final mark is the average of both evaluations.'}
              </p>
            </div>
          </div>
          {state?.published && (
            <div className="flex gap-2">
              <button onClick={openDocument} className="btn-secondary text-xs"><Eye className="w-3.5 h-3.5" /> View student document</button>
              <button onClick={downloadPdf} disabled={pdfBusy} className="btn-secondary text-xs"><Download className="w-3.5 h-3.5" /> PDF</button>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Submission */}
        <div className="lg:col-span-5 space-y-4 lg:sticky lg:top-4">
          <div className="card space-y-3">
            <h2 className="font-semibold text-slate-900 text-sm flex items-center gap-2"><FileText className="w-4 h-4 text-primary-600" /> Assessment brief</h2>
            {context.assessment_description && <p className="text-sm text-slate-700">{context.assessment_description}</p>}
            {context.instructions && <p className="text-xs bg-slate-50 rounded-lg p-2.5 text-slate-600"><strong>Instructions:</strong> {context.instructions}</p>}
            <p className="text-xs text-slate-500">
              Submitted {new Date(context.submitted_at).toLocaleString()} · {context.submission_type === 'typed' ? 'Typed answer' : context.original_filename}
              {context.has_answer_key ? ' · Answer key on file' : ''}
            </p>
            {context.submission_type !== 'typed' && context.original_filename && (
              <div className="flex gap-2">
                <button onClick={() => openSubmissionFile(false)} className="btn-secondary text-xs flex-1"><Eye className="w-3.5 h-3.5" /> View file</button>
                <button onClick={() => openSubmissionFile(true)} className="btn-secondary text-xs flex-1"><Download className="w-3.5 h-3.5" /> Download</button>
              </div>
            )}
          </div>
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-slate-900 text-sm">Student submission</h3>
              <span className="text-xs text-slate-400">{(context.submission_text || '').split(/\s+/).filter(Boolean).length} words</span>
            </div>
            {context.submission_text ? (
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 max-h-[60vh] overflow-y-auto text-[13.5px] text-slate-800 whitespace-pre-wrap leading-relaxed">
                {context.submission_text}
              </div>
            ) : <p className="text-xs text-slate-400 italic py-4">No text could be extracted from this submission.</p>}
          </div>
        </div>

        {/* Faculty rubric marking */}
        <div className="lg:col-span-7 space-y-5">
          <div className="card">
            <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
              <div>
                <h2 className="font-semibold text-slate-900">Mark against the RTLP rubric</h2>
                <p className="text-xs text-slate-500 mt-0.5">Choose a level for each criterion, then fine-tune the mark inside its band.</p>
              </div>
              <div className="text-right">
                <p className="stat-label">Your total</p>
                <p className="text-2xl font-semibold text-slate-900">{fmt(Math.round(total * 100) / 100)}<span className="text-sm text-slate-400"> / {fmt(maxMarks)}</span></p>
              </div>
            </div>

            {criteria.length === 0 && <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">No rubric is linked to this assessment.</p>}

            <div className="space-y-4">
              {criteria.map((c: any) => {
                const lvl = levelFor(c);
                return (
                  <div key={c.name} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-2.5 min-w-0">
                        <span className="mt-1.5 w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900">{c.label}. {c.name}</p>
                          <p className="text-xs text-slate-500">Maximum {fmt(c.max_marks)} marks</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <input
                          type="number" inputMode="decimal" min={0} max={c.max_marks} step={0.5}
                          aria-label={`Mark for ${c.name}`}
                          className="input-field w-20 text-center font-semibold"
                          value={marks[c.name] ?? ''}
                          onChange={e => setMark(c.name, e.target.value, c.max_marks)}
                        />
                        <span className="text-xs text-slate-400">/ {fmt(c.max_marks)}</span>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
                      {[...(c.levels || [])].sort((a: any, b: any) => b.level - a.level).map((l: any) => {
                        const selected = lvl && lvl.level === l.level;
                        return (
                          <button
                            key={l.level}
                            type="button"
                            onClick={() => setMark(c.name, String(l.max_marks ?? l.level), c.max_marks)}
                            className={`text-left rounded-lg border p-2.5 transition-colors ${selected ? 'border-primary-500 bg-primary-50 ring-1 ring-primary-500' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}
                            title={l.description}
                          >
                            <p className="text-[11px] font-semibold text-slate-800">{l.name}</p>
                            <p className="text-[10.5px] text-slate-500">
                              {l.min_marks !== undefined && l.min_marks !== l.max_marks ? `${fmt(l.min_marks)}–${fmt(l.max_marks)}` : fmt(l.max_marks ?? l.level)} marks
                            </p>
                            <p className="text-[11px] text-slate-600 mt-1 leading-snug line-clamp-3">{l.description}</p>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card space-y-4">
            <div>
              <label className="form-label">Overall feedback <span className="text-red-500">*</span></label>
              <textarea className="input-field" rows={4} value={overall} onChange={e => setOverall(e.target.value)}
                placeholder="Your overall judgement of the work. The student sees this as “Faculty comments” on the feedback document." />
            </div>
            <div>
              <label className="form-label">Private notes <span className="text-slate-400 font-normal">(never shown to the student)</span></label>
              <input className="input-field" value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes for yourself or the admin" />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100">
              <button type="button" onClick={() => save(true)} disabled={saving} className="btn-secondary text-sm"><Save className="w-4 h-4" /> Save draft</button>
              <button type="button" onClick={() => save(false)} disabled={saving || !allMarked} className="btn-primary text-sm">
                <Send className="w-4 h-4" /> {saving ? 'Submitting…' : isFinal ? 'Update evaluation' : 'Submit evaluation'}
              </button>
            </div>
            <p className="text-xs text-slate-500 flex gap-1.5"><Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              Submitting starts the AI evaluation. The student receives the annotated feedback document with the average of your marks and the AI’s marks.</p>
          </div>
        </div>
      </div>

      {docOpen && doc && (
        <div className="modal-backdrop items-start overflow-y-auto" onMouseDown={() => setDocOpen(false)}>
          <div className="w-full max-w-[900px] my-6" onMouseDown={e => e.stopPropagation()}>
            <div className="flex justify-end mb-3">
              <button onClick={() => setDocOpen(false)} className="btn-secondary text-xs">Close preview</button>
            </div>
            <FeedbackDocument doc={doc} onDownload={downloadPdf} downloading={pdfBusy} />
          </div>
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
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">My Subjects</h2>
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
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">Submissions & Evaluations</h2>
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
        <Route path="/submissions/:submissionId" element={<SubmissionEvaluation />} />
        <Route path="/evaluations" element={<EvaluationsList />} />
      </Routes>
    </DashboardLayout>
  );
}
