import React, { useEffect, useState } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import AdminAssessments from './AdminAssessments';
import { adminApi } from '../../api/client';
import {
  LayoutDashboard, Users, BookOpen, FileText,
  UserPlus, Settings, ClipboardList, Shield, BarChart3,
  Award, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  ChevronDown, ChevronUp, Eye, Scale, Plus, ClipboardCheck
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/admin', icon: LayoutDashboard },
  { label: 'Assessments', to: '/admin/assessments', icon: ClipboardCheck },
  { label: 'Rubric Library', to: '/admin/rubrics', icon: Award },
  { label: 'Evaluation Monitor', to: '/admin/monitoring', icon: BarChart3 },
  { label: 'Faculty Management', to: '/admin/faculty', icon: Users },
  { label: 'Student Management', to: '/admin/students', icon: Users },
  { label: 'Subjects', to: '/admin/subjects', icon: BookOpen },
  { label: 'All Submissions', to: '/admin/submissions', icon: FileText },
  { label: 'Audit Logs', to: '/admin/audit', icon: ClipboardList },
];

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="card-hover relative overflow-hidden">
      <span className={`absolute left-0 top-0 h-full w-1 ${color.replace('text-', 'bg-')}`} />
      <p className="stat-label">{label}</p>
      <p className="stat-value text-slate-900">{value ?? 0}</p>
    </div>
  );
}

// ─── Dashboard Overview ───────────────────────────────────────────────────────
function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.getStats().then(r => setStats(r.data)).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-500">Loading dashboard...</div>;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Institution Overview</h2>
        <p className="text-slate-500 text-sm mt-1">Real-time platform statistics</p>
      </div>
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Students" value={stats.total_students} color="text-blue-600" />
          <StatCard label="Total Faculty" value={stats.total_faculty} color="text-purple-600" />
          <StatCard label="Subjects" value={stats.total_subjects} color="text-indigo-600" />
          <StatCard label="Submissions" value={stats.total_submissions} color="text-teal-600" />
          <StatCard label="AI Evaluations" value={stats.total_evaluations} color="text-orange-600" />
          <StatCard label="Pending Review" value={stats.pending_evaluations} color="text-yellow-600" />
          <StatCard label="Approved" value={stats.approved_evaluations} color="text-green-600" />
        </div>
      )}
      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-3">Quick Actions</h3>
        <div className="flex flex-wrap gap-3">
          <Link to="/admin/faculty" className="btn-primary text-sm">+ Add Faculty</Link>
          <Link to="/admin/students" className="btn-primary text-sm">+ Add Student</Link>
          <Link to="/admin/subjects" className="btn-primary text-sm">+ Create Subject</Link>
          <Link to="/admin/assessments" className="btn-primary text-sm">+ Create Assessment</Link>
          <Link to="/admin/audit" className="btn-secondary text-sm">View Audit Logs</Link>
        </div>
      </div>
    </div>
  );
}

// ─── Faculty Management ───────────────────────────────────────────────────────
function FacultyManagement() {
  const [faculty, setFaculty] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'faculty', department: '', employee_id: '', specialization: '' });
  const [msg, setMsg] = useState('');
  const [assignModal, setAssignModal] = useState<{ userId: number; name: string } | null>(null);
  const [selectedSubject, setSelectedSubject] = useState('');

  const load = () => {
    adminApi.listFaculty().then(r => setFaculty(r.data));
    adminApi.listSubjects().then(r => setSubjects(r.data));
  };
  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createFaculty(form);
      setMsg('Faculty created successfully');
      setShowForm(false);
      setForm({ email: '', full_name: '', password: '', role: 'faculty', department: '', employee_id: '', specialization: '' });
      load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  const handleAssign = async () => {
    if (!assignModal || !selectedSubject) return;
    try {
      await adminApi.assignFaculty(parseInt(selectedSubject), assignModal.userId);
      setMsg(`Assigned to subject successfully`);
      setAssignModal(null);
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  const toggleStatus = async (id: number, current: boolean) => {
    await adminApi.updateFaculty(id, { is_active: !current });
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Faculty Management</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-sm">
          + Add Faculty
        </button>
      </div>

      {msg && <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{msg}</div>}

      {showForm && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Create Faculty Account</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div><label className="text-xs font-medium text-slate-600">Full Name *</label><input className="input-field mt-1" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Email *</label><input type="email" className="input-field mt-1" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Password *</label><input type="password" className="input-field mt-1" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} /></div>
            <div><label className="text-xs font-medium text-slate-600">Employee ID</label><input className="input-field mt-1" value={form.employee_id} onChange={e => setForm({...form, employee_id: e.target.value})} /></div>
            <div><label className="text-xs font-medium text-slate-600">Department</label><input className="input-field mt-1" value={form.department} onChange={e => setForm({...form, department: e.target.value})} /></div>
            <div><label className="text-xs font-medium text-slate-600">Specialization</label><input className="input-field mt-1" value={form.specialization} onChange={e => setForm({...form, specialization: e.target.value})} /></div>
            <div className="col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm">Create Faculty</button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {assignModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="card w-80">
            <h3 className="font-semibold mb-3">Assign Subject to {assignModal.name}</h3>
            <select className="input-field mb-3" value={selectedSubject} onChange={e => setSelectedSubject(e.target.value)}>
              <option value="">Select subject...</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
            </select>
            <div className="flex gap-2">
              <button onClick={handleAssign} className="btn-primary text-sm">Assign</button>
              <button onClick={() => setAssignModal(null)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Name</th><th className="text-left pb-2 text-slate-500 font-medium">Email</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th><th className="pb-2"></th></tr></thead>
          <tbody>
            {faculty.map(f => (
              <tr key={f.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-3 font-medium text-slate-800">{f.full_name}</td>
                <td className="py-3 text-slate-500">{f.email}</td>
                <td className="py-3">
                  <span className={f.is_active ? 'badge-approved' : 'badge-rejected'}>
                    {f.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="py-3">
                  <div className="flex gap-2">
                    <button onClick={() => setAssignModal({ userId: f.id, name: f.full_name })} className="text-xs text-primary-600 hover:underline">Assign Subject</button>
                    <button onClick={() => toggleStatus(f.id, f.is_active)} className="text-xs text-slate-500 hover:underline">
                      {f.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {faculty.length === 0 && <tr><td colSpan={4} className="py-6 text-center text-slate-400">No faculty members yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Student Management ───────────────────────────────────────────────────────
function StudentManagement() {
  const [students, setStudents] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: '', full_name: '', password: '', role: 'student', student_id: '', program: '', year_of_study: 1 });
  const [msg, setMsg] = useState('');
  const [enrollModal, setEnrollModal] = useState<{ userId: number; name: string } | null>(null);
  const [selectedSubject, setSelectedSubject] = useState('');

  const load = () => {
    adminApi.listStudents().then(r => setStudents(r.data));
    adminApi.listSubjects().then(r => setSubjects(r.data));
  };
  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createStudent(form);
      setMsg('Student created successfully');
      setShowForm(false);
      setForm({ email: '', full_name: '', password: '', role: 'student', student_id: '', program: '', year_of_study: 1 });
      load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  const handleEnroll = async () => {
    if (!enrollModal || !selectedSubject) return;
    try {
      await adminApi.enrollStudent(parseInt(selectedSubject), enrollModal.userId);
      setMsg('Student enrolled successfully');
      setEnrollModal(null);
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Student Management</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-sm">+ Add Student</button>
      </div>

      {msg && <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{msg}</div>}

      {showForm && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Create Student Account</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div><label className="text-xs font-medium text-slate-600">Full Name *</label><input className="input-field mt-1" value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Email *</label><input type="email" className="input-field mt-1" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Password *</label><input type="password" className="input-field mt-1" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} /></div>
            <div><label className="text-xs font-medium text-slate-600">Student ID *</label><input className="input-field mt-1" value={form.student_id} onChange={e => setForm({...form, student_id: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Program</label><input className="input-field mt-1" value={form.program} onChange={e => setForm({...form, program: e.target.value})} /></div>
            <div><label className="text-xs font-medium text-slate-600">Year of Study</label><input type="number" className="input-field mt-1" value={form.year_of_study} onChange={e => setForm({...form, year_of_study: parseInt(e.target.value)})} min={1} max={6} /></div>
            <div className="col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm">Create Student</button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {enrollModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="card w-80">
            <h3 className="font-semibold mb-3">Enroll {enrollModal.name}</h3>
            <select className="input-field mb-3" value={selectedSubject} onChange={e => setSelectedSubject(e.target.value)}>
              <option value="">Select subject...</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
            </select>
            <div className="flex gap-2">
              <button onClick={handleEnroll} className="btn-primary text-sm">Enroll</button>
              <button onClick={() => setEnrollModal(null)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Name</th><th className="text-left pb-2 text-slate-500 font-medium">Email</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th><th className="pb-2"></th></tr></thead>
          <tbody>
            {students.map(s => (
              <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-3 font-medium text-slate-800">{s.full_name}</td>
                <td className="py-3 text-slate-500">{s.email}</td>
                <td className="py-3"><span className={s.is_active ? 'badge-approved' : 'badge-rejected'}>{s.is_active ? 'Active' : 'Inactive'}</span></td>
                <td className="py-3">
                  <button onClick={() => setEnrollModal({ userId: s.id, name: s.full_name })} className="text-xs text-primary-600 hover:underline">Enroll Subject</button>
                </td>
              </tr>
            ))}
            {students.length === 0 && <tr><td colSpan={4} className="py-6 text-center text-slate-400">No students yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Subject Management ───────────────────────────────────────────────────────
function SubjectManagement() {
  const [subjects, setSubjects] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', code: '', description: '' });
  const [msg, setMsg] = useState('');

  const load = () => adminApi.listSubjects().then(r => setSubjects(r.data));
  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await adminApi.createSubject(form);
      setMsg('Subject created successfully');
      setShowForm(false);
      setForm({ name: '', code: '', description: '' });
      load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Subject Management</h2>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary text-sm">+ Create Subject</button>
      </div>
      {msg && <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>{msg}</div>}
      {showForm && (
        <div className="card mb-6">
          <h3 className="font-semibold mb-4">Create Subject</h3>
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-4">
            <div><label className="text-xs font-medium text-slate-600">Subject Name *</label><input className="input-field mt-1" value={form.name} onChange={e => setForm({...form, name: e.target.value})} required /></div>
            <div><label className="text-xs font-medium text-slate-600">Subject Code *</label><input className="input-field mt-1" value={form.code} onChange={e => setForm({...form, code: e.target.value})} required /></div>
            <div className="col-span-2"><label className="text-xs font-medium text-slate-600">Description</label><textarea className="input-field mt-1" rows={2} value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></div>
            <div className="col-span-2 flex gap-2">
              <button type="submit" className="btn-primary text-sm">Create Subject</button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}
      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Name</th><th className="text-left pb-2 text-slate-500 font-medium">Code</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th></tr></thead>
          <tbody>
            {subjects.map(s => (
              <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-3 font-medium text-slate-800">{s.name}</td>
                <td className="py-3 text-slate-500 font-mono">{s.code}</td>
                <td className="py-3"><span className={s.is_active ? 'badge-approved' : 'badge-rejected'}>{s.is_active ? 'Active' : 'Inactive'}</span></td>
              </tr>
            ))}
            {subjects.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-slate-400">No subjects yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Audit Logs ───────────────────────────────────────────────────────────────
function AuditLogs() {
  const [logs, setLogs] = useState<any[]>([]);
  useEffect(() => { adminApi.getAuditLogs().then(r => setLogs(r.data)); }, []);
  return (
    <div>
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">Audit Logs</h2>
      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Action</th><th className="text-left pb-2 text-slate-500 font-medium">Resource</th><th className="text-left pb-2 text-slate-500 font-medium">Time</th></tr></thead>
          <tbody>
            {logs.map(l => (
              <tr key={l.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-2 font-medium text-slate-700">{l.action}</td>
                <td className="py-2 text-slate-500 text-xs">{l.resource_type} {l.resource_id ? `#${l.resource_id}` : ''}</td>
                <td className="py-2 text-slate-400 text-xs">{new Date(l.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {logs.length === 0 && <tr><td colSpan={3} className="py-6 text-center text-slate-400">No audit logs</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── All Submissions ──────────────────────────────────────────────────────────
function AllSubmissions() {
  const [submissions, setSubmissions] = useState<any[]>([]);
  useEffect(() => { adminApi.getAllSubmissions().then(r => setSubmissions(r.data)); }, []);
  return (
    <div>
      <h2 className="text-xl font-semibold text-slate-900 tracking-tight mb-6">All Submissions</h2>
      <div className="card">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-edu-border"><th className="text-left pb-2 text-slate-500 font-medium">Student</th><th className="text-left pb-2 text-slate-500 font-medium">Assessment</th><th className="text-left pb-2 text-slate-500 font-medium">Subject</th><th className="text-left pb-2 text-slate-500 font-medium">Status</th><th className="text-left pb-2 text-slate-500 font-medium">Date</th></tr></thead>
          <tbody>
            {submissions.map(s => (
              <tr key={s.id} className="border-b border-edu-border/50 last:border-0">
                <td className="py-2"><p className="font-medium text-slate-800">{s.student_name}</p><p className="text-xs text-slate-400">{s.student_id}</p></td>
                <td className="py-2 text-slate-600">{s.assessment_title}</td>
                <td className="py-2 text-slate-500 text-xs">{s.subject}</td>
                <td className="py-2"><span className={`badge-${s.status}`}>{s.status}</span></td>
                <td className="py-2 text-slate-400 text-xs">{new Date(s.submitted_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {submissions.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-slate-400">No submissions yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Assessment & Rubric Management (Admin) ──────────────────────────────────
function AssessmentRubricManagement() {
  const [types, setTypes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  // New assessment type form
  const [typeName, setTypeName] = useState('');
  const [typeDesc, setTypeDesc] = useState('');
  const [typeMaxMarks, setTypeMaxMarks] = useState(20);
  const [typeThreshold, setTypeThreshold] = useState(0.20);
  const [criteria, setCriteria] = useState<any[]>([
    {
      name: 'Relevance',
      max_marks: 4,
      description: 'Relevance to the core assignment brief',
      levels: [
        { level: 4, name: 'Excellent', description: 'Consistently and deeply relevant throughout.' },
        { level: 3, name: 'Good', description: 'Relevant with minor lapses.' },
        { level: 2, name: 'Average', description: 'Moderately relevant.' },
        { level: 1, name: 'Needs Improvement', description: 'Irrelevant or mostly unrelated.' }
      ]
    }
  ]);

  const load = () => {
    adminApi.listAssessmentTypes()
      .then(r => setTypes(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const toggleStatus = async (typeId: number, current: boolean) => {
    try {
      await adminApi.updateAssessmentType(typeId, { is_active: !current });
      setMsg(`Assessment type status updated to ${!current ? 'Active' : 'Inactive'}.`);
      load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Update failed'));
    }
  };

  const handleAddCriterion = () => {
    setCriteria([
      ...criteria,
      {
        name: `Criterion ${criteria.length + 1}`,
        max_marks: 4,
        description: '',
        levels: [
          { level: 4, name: 'Excellent', description: 'Exceeds standard expectations.' },
          { level: 3, name: 'Good', description: 'Meets expectations well.' },
          { level: 2, name: 'Average', description: 'Meets minimum standard with minor errors.' },
          { level: 1, name: 'Needs Improvement', description: 'Below acceptable standard.' }
        ]
      }
    ]);
  };

  const handleCreateType = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!typeName.trim()) return;
    try {
      await adminApi.createAssessmentType({
        name: typeName.trim(),
        description: typeDesc,
        max_marks: typeMaxMarks,
        default_discrepancy_threshold: typeThreshold,
        criteria,
      });
      setMsg(`Assessment type "${typeName}" created successfully!`);
      setShowAddForm(false);
      setTypeName('');
      setTypeDesc('');
      load();
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed to create assessment type'));
    }
  };

  if (loading) return <div className="text-slate-500">Loading rubrics...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900 tracking-tight">Assessment & Rubric Management</h2>
          <p className="text-xs text-slate-500 mt-1">Manage active assessment types, 4-level performance rubrics, and discrepancy thresholds.</p>
        </div>
        <button onClick={() => setShowAddForm(!showAddForm)} className="btn-primary text-sm flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Add Assessment Type
        </button>
      </div>

      {msg && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {msg}
        </div>
      )}

      {showAddForm && (
        <div className="card mb-6 border-primary-200">
          <h3 className="font-semibold text-slate-800 mb-3">Create New Assessment Type & Rubric</h3>
          <form onSubmit={handleCreateType} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-600">Assessment Type Name *</label>
                <input className="input-field mt-1" value={typeName} onChange={e => setTypeName(e.target.value)} required placeholder="e.g. Case Study" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600">Total Rubric Marks</label>
                <input type="number" className="input-field mt-1" value={typeMaxMarks} onChange={e => setTypeMaxMarks(parseFloat(e.target.value) || 20)} min={1} />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Description</label>
              <input className="input-field mt-1" value={typeDesc} onChange={e => setTypeDesc(e.target.value)} placeholder="Assessment description or instructions" />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Discrepancy Threshold Ratio (default 0.20 = 20%)</label>
              <input type="number" step="0.05" min="0.05" max="0.5" className="input-field mt-1 w-48" value={typeThreshold} onChange={e => setTypeThreshold(parseFloat(e.target.value) || 0.20)} />
            </div>

            <div className="border-t border-edu-border pt-3">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-slate-700 text-sm">Rubric Criteria (Each with 4 Performance Levels)</h4>
                <button type="button" onClick={handleAddCriterion} className="btn-secondary text-xs">+ Add Criterion</button>
              </div>
              <div className="space-y-3">
                {criteria.map((c, ci) => (
                  <div key={ci} className="bg-slate-50 p-3 rounded-lg border border-edu-border">
                    <div className="flex items-center gap-2 mb-2">
                      <input className="input-field text-sm font-semibold flex-1" value={c.name} onChange={e => { const nc = [...criteria]; nc[ci].name = e.target.value; setCriteria(nc); }} placeholder="Criterion name" required />
                      <input type="number" className="input-field text-sm w-20" value={c.max_marks} onChange={e => { const nc = [...criteria]; nc[ci].max_marks = parseFloat(e.target.value) || 4; setCriteria(nc); }} />
                      <button type="button" onClick={() => setCriteria(criteria.filter((_, idx) => idx !== ci))} className="text-red-500 hover:text-red-700 text-xs px-2">Delete</button>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {c.levels.map((lvl: any, li: number) => (
                        <div key={li} className="bg-white p-2 rounded border border-slate-200">
                          <p className="text-xs font-bold text-slate-600">{lvl.level} — {lvl.name}</p>
                          <textarea className="input-field text-xs mt-1" rows={2} value={lvl.description} onChange={e => {
                            const nc = [...criteria];
                            nc[ci].levels[li].description = e.target.value;
                            setCriteria(nc);
                          }} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button type="submit" className="btn-primary text-sm">Save Assessment Type</button>
              <button type="button" onClick={() => setShowAddForm(false)} className="btn-secondary text-sm">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Assessment Types Table */}
      <div className="space-y-4">
        {types.map(t => {
          const isExpanded = expandedId === t.id;
          const activeRubric = t.active_rubric;
          const criteriaList = activeRubric?.criteria_data || [];

          return (
            <div key={t.id} className="card border border-edu-border hover:border-slate-300 transition-all">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-slate-800 text-base">{t.name}</h3>
                    <span className={t.is_active ? 'badge-approved' : 'badge-pending'}>
                      {t.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono">
                      v{activeRubric?.version || 1}
                    </span>
                  </div>
                  {t.description && <p className="text-xs text-slate-500 mt-1">{t.description}</p>}
                  <p className="text-xs text-slate-400 mt-1">
                    Max Marks: <strong>{t.max_marks}</strong> · Discrepancy Threshold: <strong>{Math.round(t.default_discrepancy_threshold * 100)}% ({t.max_marks * t.default_discrepancy_threshold} marks)</strong> · Rubric Versions: {t.rubric_versions?.length || 1}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => toggleStatus(t.id, t.is_active)}
                    className={`text-xs px-2.5 py-1 rounded-md font-medium border ${t.is_active ? 'border-amber-300 text-amber-700 hover:bg-amber-50' : 'border-green-300 text-green-700 hover:bg-green-50'}`}
                  >
                    {t.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : t.id)}
                    className="btn-secondary text-xs flex items-center gap-1"
                  >
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    {isExpanded ? 'Hide Rubric' : 'View Rubric'}
                  </button>
                </div>
              </div>

              {/* Expanded Rubric Criteria & Levels */}
              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-edu-border space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase text-slate-500 tracking-wider">
                      Rubric Criteria & Performance Levels (Version {activeRubric?.version || 1})
                    </h4>
                  </div>
                  <div className="space-y-3">
                    {criteriaList.map((crit: any, idx: number) => (
                      <div key={idx} className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-sm font-bold text-slate-800">
                            {idx + 1}. {crit.name}
                          </p>
                          <span className="text-xs font-semibold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">
                            Max {crit.max_marks || 4} marks
                          </span>
                        </div>
                        {crit.description && <p className="text-xs text-slate-500 mb-2">{crit.description}</p>}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                          {(crit.levels || []).map((lvl: any, li: number) => (
                            <div key={li} className="bg-white p-2.5 rounded border border-slate-200 text-xs">
                              <p className="font-bold text-slate-700 mb-1">
                                Level {lvl.level} — {lvl.name}
                              </p>
                              <p className="text-slate-600 leading-relaxed">{lvl.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── AI Evaluation Monitoring & Detailed Comparison (Admin) ───────────────────
function EvaluationMonitoring() {
  const [items, setItems] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSubId, setSelectedSubId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [filterSubject, setFilterSubject] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [msg, setMsg] = useState('');

  const load = () => {
    adminApi.getEvaluationMonitoring({
      subject_id: filterSubject || undefined,
      status: filterStatus || undefined,
    }).then(r => setItems(r.data)).catch(console.error).finally(() => setLoading(false));
    adminApi.listSubjects().then(r => setSubjects(r.data)).catch(console.error);
  };

  useEffect(() => { load(); }, [filterSubject, filterStatus]);

  const openComparison = async (subId: number) => {
    setSelectedSubId(subId);
    setLoadingDetail(true);
    try {
      const r = await adminApi.getEvaluationComparison(subId);
      setDetail(r.data);
    } catch (err: any) {
      setMsg('Error loading comparison: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRetry = async (subId: number) => {
    setMsg('Triggering AI evaluation retry...');
    try {
      const r = await adminApi.retryAiEvaluation(subId);
      setMsg(r.data.message);
      load();
      if (selectedSubId === subId) {
        openComparison(subId);
      }
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Retry failed'));
    }
  };

  const handlePublish = async (subId: number, publish: boolean) => {
    try {
      await adminApi.publishEvaluation(subId, publish);
      setMsg(publish ? 'Evaluation published to student!' : 'Evaluation publication revoked.');
      load();
      if (selectedSubId === subId) {
        openComparison(subId);
      }
    } catch (err: any) {
      setMsg('Error: ' + (err.response?.data?.detail || 'Failed'));
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900 tracking-tight">AI Evaluation Monitoring & Comparison</h2>
          <p className="text-xs text-slate-500 mt-1">
            Faculty vs AI marks for every submission. Final mark = average of both; differences above the threshold are flagged for review.
          </p>
        </div>
        <button onClick={load} className="btn-secondary text-xs flex items-center gap-1">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {msg && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${msg.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
          {msg}
        </div>
      )}

      {/* Filter Bar */}
      <div className="card mb-4 flex flex-wrap items-center gap-3 py-3">
        <div>
          <label className="text-xs text-slate-500 block">Subject</label>
          <select className="input-field text-xs mt-1 w-48" value={filterSubject} onChange={e => setFilterSubject(e.target.value)}>
            <option value="">All Subjects</option>
            {subjects.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 block">Evaluation Status</label>
          <select className="input-field text-xs mt-1 w-44" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="completed">Completed & Finalized</option>
            <option value="ai_failed">AI Evaluation Failed</option>
            <option value="faculty_pending">Pending Faculty</option>
          </select>
        </div>
      </div>

      {/* Monitoring Table */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-edu-border">
              <th className="text-left pb-2 text-slate-500 font-medium">Student</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Subject / Assessment</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Faculty Score (F)</th>
              <th className="text-left pb-2 text-slate-500 font-medium">AI Score (A)</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Diff / Threshold</th>
              <th className="text-left pb-2 text-slate-500 font-medium">Final Marks</th>
              <th className="text-left pb-2 text-slate-500 font-medium">AI Status</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(it => (
              <tr key={it.submission_id} className="border-b border-edu-border/50 last:border-0 hover:bg-slate-50/50">
                <td className="py-2.5">
                  <p className="font-semibold text-slate-800 text-xs">{it.student_name}</p>
                  <p className="text-xs text-slate-400 font-mono">{it.student_id_str}</p>
                </td>
                <td className="py-2.5">
                  <p className="text-xs font-medium text-slate-700">{it.assessment_title}</p>
                  <p className="text-xs text-slate-400">{it.subject_name} · <span className="capitalize">{it.assessment_type}</span></p>
                </td>
                <td className="py-2.5">
                  {it.faculty_marks !== null ? (
                    <span className="font-bold text-slate-800 text-xs">{it.faculty_marks} / {it.max_marks}</span>
                  ) : (
                    <span className="text-xs text-amber-600 font-medium">Pending</span>
                  )}
                </td>
                <td className="py-2.5">
                  {it.ai_marks !== null ? (
                    <span className="font-bold text-indigo-700 text-xs">{it.ai_marks} / {it.max_marks}</span>
                  ) : (
                    <span className="text-xs text-slate-400">{it.ai_status}</span>
                  )}
                </td>
                <td className="py-2.5 text-xs text-slate-600">
                  {it.discrepancy_value !== null ? (
                    <span>
                      D = <strong>{it.discrepancy_value}</strong> / T = {it.discrepancy_threshold}
                      {it.discrepancy_value > it.discrepancy_threshold && (
                        <span className="text-amber-600 font-bold ml-1">(D &gt; T: Averaged)</span>
                      )}
                    </span>
                  ) : '—'}
                </td>
                <td className="py-2.5">
                  {it.final_marks !== null ? (
                    <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                      {it.final_marks} / {it.max_marks}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">Not calculated</span>
                  )}
                </td>
                <td className="py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    it.ai_status === 'Completed' ? 'bg-green-100 text-green-700' :
                    it.ai_status === 'Failed' ? 'bg-red-100 text-red-700 font-bold' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    {it.ai_status}
                  </span>
                  {it.error_details && (
                    <p className="text-[10px] text-red-600 truncate max-w-xs mt-0.5" title={it.error_details}>{it.error_details}</p>
                  )}
                </td>
                <td className="py-2.5 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => openComparison(it.submission_id)}
                      className="btn-secondary text-xs flex items-center gap-1"
                    >
                      <Scale className="w-3.5 h-3.5" /> Compare
                    </button>
                    {it.ai_status === 'Failed' && (
                      <button
                        onClick={() => handleRetry(it.submission_id)}
                        className="btn-primary text-xs flex items-center gap-1"
                      >
                        <RefreshCw className="w-3.5 h-3.5" /> Retry
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={8} className="py-8 text-center text-slate-400">No evaluations found</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Comparison Modal */}
      {selectedSubId && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-edu-border bg-slate-50">
              <div>
                <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                  <Scale className="w-5 h-5 text-primary-600" />
                  Academic Evaluation Comparison & Discrepancy Analysis
                </h3>
                {detail && (
                  <p className="text-xs text-slate-500 mt-0.5">
                    {detail.student_name} ({detail.student_id_str}) · {detail.assessment_title} ({detail.subject_name})
                  </p>
                )}
              </div>
              <button onClick={() => setSelectedSubId(null)} className="text-slate-400 hover:text-slate-600 font-bold p-1 text-lg">✕</button>
            </div>

            <div className="p-6 overflow-y-auto space-y-5 flex-1">
              {loadingDetail ? (
                <div className="text-center py-12 text-slate-500">Loading evaluation breakdown...</div>
              ) : detail ? (
                <>
                  {/* Calculation Breakdown Banner */}
                  <div className="rounded-xl border border-primary-200 bg-gradient-to-r from-primary-50 via-indigo-50 to-emerald-50 p-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                      Authoritative Python Final Score Calculation (Section 8 Policy)
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
                      <div className="bg-white/80 p-2.5 rounded-lg border border-slate-200">
                        <p className="text-xs text-slate-500">Faculty Score (F)</p>
                        <p className="text-xl font-semibold text-slate-900 tracking-tight">{detail.faculty_marks ?? 'N/A'}</p>
                      </div>
                      <div className="bg-white/80 p-2.5 rounded-lg border border-slate-200">
                        <p className="text-xs text-slate-500">AI Score (A)</p>
                        <p className="text-xl font-bold text-indigo-700">{detail.ai_marks ?? 'N/A'}</p>
                      </div>
                      <div className="bg-white/80 p-2.5 rounded-lg border border-slate-200">
                        <p className="text-xs text-slate-500">Difference (D)</p>
                        <p className="text-xl font-bold text-slate-700">{detail.discrepancy_value ?? 'N/A'}</p>
                      </div>
                      <div className="bg-white/80 p-2.5 rounded-lg border border-slate-200">
                        <p className="text-xs text-slate-500">Threshold (T)</p>
                        <p className="text-xl font-bold text-slate-700">{detail.discrepancy_threshold ?? 'N/A'}</p>
                      </div>
                      <div className="bg-emerald-100/80 p-2.5 rounded-lg border border-emerald-300">
                        <p className="text-xs text-emerald-800 font-bold">Final Marks</p>
                        <p className="text-2xl font-black text-emerald-700">{detail.final_marks ?? 'N/A'} / {detail.max_marks}</p>
                      </div>
                    </div>
                    <div className="mt-3 text-xs text-slate-600 bg-white/70 p-2 rounded">
                      <strong>Policy result: </strong>
                      <span className="text-indigo-800 font-medium">
                        Averaged: ({detail.faculty_marks} + {detail.ai_marks}) / 2 = {detail.final_marks}
                      </span>
                      {detail.discrepancy_value > detail.discrepancy_threshold && (
                        <span className="block mt-1 text-amber-700 font-medium">
                          Flagged for review: difference {detail.discrepancy_value} exceeds the threshold of {detail.discrepancy_threshold} marks.
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Side-by-Side Comparison */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Faculty Evaluation Column */}
                    <div className="card border-slate-200">
                      <div className="flex items-center justify-between pb-3 border-b border-edu-border">
                        <h4 className="font-bold text-slate-800">Faculty Evaluation (Manual)</h4>
                        <span className="text-sm font-bold text-slate-700">
                          {detail.faculty_marks !== null ? `${detail.faculty_marks} / ${detail.max_marks}` : 'Pending'}
                        </span>
                      </div>
                      <div className="mt-3 space-y-3 text-xs">
                        <div>
                          <p className="font-semibold text-slate-500 uppercase">Overall Feedback</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.faculty_feedback || 'No feedback entered'}</p>
                        </div>
                        <div>
                          <p className="font-semibold text-green-700 uppercase">Strengths</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.faculty_strengths || 'None'}</p>
                        </div>
                        <div>
                          <p className="font-semibold text-red-700 uppercase">Weaknesses / Gaps</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.faculty_weaknesses || 'None'}</p>
                        </div>
                        <div>
                          <p className="font-semibold text-blue-700 uppercase">Improvement Suggestions</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.faculty_suggestions || 'None'}</p>
                        </div>
                        {detail.faculty_irrelevant && (
                          <div className="bg-amber-50 p-2 rounded border border-amber-200">
                            <p className="font-semibold text-amber-800 uppercase">Faculty Irrelevant-Content Note</p>
                            <p className="text-amber-900 mt-0.5">{detail.faculty_irrelevant}</p>
                          </div>
                        )}
                        {detail.faculty_deductions && (
                          <div className="bg-red-50 p-2 rounded border border-red-200">
                            <p className="font-semibold text-red-800 uppercase">Deduction Reasons</p>
                            <p className="text-red-900 mt-0.5">{detail.faculty_deductions}</p>
                          </div>
                        )}
                        {detail.faculty_notes && (
                          <div className="bg-slate-100 p-2 rounded">
                            <p className="font-semibold text-slate-600 uppercase">Internal Faculty Notes</p>
                            <p className="text-slate-700 mt-0.5">{detail.faculty_notes}</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* AI Evaluation Column */}
                    <div className="card border-indigo-200 bg-indigo-50/20">
                      <div className="flex items-center justify-between pb-3 border-b border-indigo-100">
                        <div className="flex items-center gap-2">
                          <h4 className="font-bold text-indigo-900">AI Evaluation (Automated)</h4>
                          <span className={`text-[10px] px-2 py-0.5 rounded-full ${detail.ai_status === 'Completed' ? 'bg-green-100 text-green-700 font-bold' : 'bg-red-100 text-red-700'}`}>
                            {detail.ai_status}
                          </span>
                        </div>
                        <span className="text-sm font-bold text-indigo-800">
                          {detail.ai_marks !== null ? `${detail.ai_marks} / ${detail.max_marks}` : 'N/A'}
                        </span>
                      </div>

                      {detail.ai_error_details && (
                        <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                          <p className="font-bold flex items-center gap-1"><AlertTriangle className="w-4 h-4 text-red-500" /> AI Processing Error:</p>
                          <p className="mt-1">{detail.ai_error_details}</p>
                          <button onClick={() => handleRetry(detail.submission_id)} className="btn-primary text-xs mt-2 flex items-center gap-1">
                            <RefreshCw className="w-3.5 h-3.5" /> Retry AI Evaluation
                          </button>
                        </div>
                      )}

                      {/* 5-Criterion AI Score Breakdown */}
                      {detail.ai_criterion_scores?.length > 0 && (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-bold uppercase text-slate-600">AI 5-Criterion Analysis</p>
                          {detail.ai_criterion_scores.map((cs: any, i: number) => (
                            <div key={i} className="bg-white p-2 rounded border border-slate-200 text-xs">
                              <div className="flex justify-between font-semibold text-slate-800">
                                <span>{cs.criterion_name}</span>
                                <span className="text-indigo-700">{cs.score} / {cs.max_marks}</span>
                              </div>
                              <p className="text-slate-500 text-[11px] mt-0.5">{cs.justification}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 space-y-3 text-xs">
                        <div>
                          <p className="font-semibold text-slate-500 uppercase">AI Overall Feedback</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.ai_overall_feedback || 'None'}</p>
                        </div>
                        <div>
                          <p className="font-semibold text-green-700 uppercase">AI Strengths</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.ai_strengths || 'None'}</p>
                        </div>
                        <div>
                          <p className="font-semibold text-red-700 uppercase">AI Weaknesses</p>
                          <p className="text-slate-700 mt-1 whitespace-pre-wrap">{detail.ai_weaknesses || 'None'}</p>
                        </div>

                        {/* Irrelevant Observations */}
                        {detail.ai_irrelevant_observations?.length > 0 && (
                          <div className="bg-amber-50 p-2.5 rounded border border-amber-200">
                            <p className="font-semibold text-amber-900 uppercase">AI Irrelevant-Content Observations</p>
                            {detail.ai_irrelevant_observations.map((obs: any, idx: number) => (
                              <div key={idx} className="mt-1 text-slate-700 text-[11px]">
                                <p className="italic">"{obs.excerpt}"</p>
                                <p className="text-slate-500">{obs.why_unrelated} · Affects: {obs.relevant_criterion}</p>
                              </div>
                            ))}
                          </div>
                        )}

                        {detail.ai_evidence?.length > 0 && (
                          <div>
                            <p className="font-semibold text-slate-500 uppercase">Supporting Evidence Quotes</p>
                            <div className="space-y-1 mt-1">
                              {detail.ai_evidence.slice(0, 3).map((ev: any, i: number) => (
                                <p key={i} className="text-[11px] text-slate-600 bg-white p-1.5 rounded border border-slate-200 italic">
                                  "{ev.text}"
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Student Submission Text Preview */}
                  <div className="card">
                    <h4 className="font-bold text-slate-800 text-xs uppercase mb-2">Student Submission Text Preview ({detail.submission_type})</h4>
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 max-h-48 overflow-y-auto text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed">
                      {detail.submission_text || 'No text extracted'}
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            <div className="p-4 border-t border-edu-border bg-slate-50 flex items-center justify-between">
              <div>
                {detail && (
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${detail.is_published ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'}`}>
                    {detail.is_published ? 'Published to Student' : 'Draft / Unpublished'}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {detail && (
                  <>
                    {detail.final_marks !== null ? (
                      <button
                        onClick={() => handlePublish(detail.submission_id, !detail.is_published)}
                        className={detail.is_published ? 'btn-secondary text-xs' : 'btn-success text-xs'}
                      >
                        {detail.is_published ? 'Revoke Publication' : 'Publish to Student'}
                      </button>
                    ) : (
                      <span className="text-xs text-slate-500">
                        Publication unavailable until final marks are calculated
                      </span>
                    )}
                    {detail.final_marks !== null && (
                      <button
                        onClick={async () => {
                          try {
                            const res = await adminApi.downloadFeedbackPdf(detail.submission_id);
                            const url = URL.createObjectURL(res.data);
                            window.open(url, '_blank', 'noopener,noreferrer');
                            window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
                          } catch (err: any) {
                            setMsg('Error: feedback document not available for this submission');
                          }
                        }}
                        className="btn-secondary text-xs flex items-center gap-1"
                      >
                        <Eye className="w-3.5 h-3.5" /> Student feedback PDF
                      </button>
                    )}
                    <button
                      onClick={() => handleRetry(detail.submission_id)}
                      className="btn-primary text-xs flex items-center gap-1"
                    >
                      <RefreshCw className="w-3.5 h-3.5" /> Re-run AI Evaluation
                    </button>
                  </>
                )}
                <button onClick={() => setSelectedSubId(null)} className="btn-secondary text-xs">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Admin Portal ─────────────────────────────────────────────────────────────
export default function AdminPortal() {
  return (
    <DashboardLayout navItems={navItems} portalLabel="Admin Portal" portalColor="bg-slate-800">
      <Routes>
        <Route path="/" element={<AdminDashboard />} />
        <Route path="/assessments" element={<AdminAssessments />} />
        <Route path="/rubrics" element={<AssessmentRubricManagement />} />
        <Route path="/monitoring" element={<EvaluationMonitoring />} />
        <Route path="/faculty" element={<FacultyManagement />} />
        <Route path="/students" element={<StudentManagement />} />
        <Route path="/subjects" element={<SubjectManagement />} />
        <Route path="/submissions" element={<AllSubmissions />} />
        <Route path="/audit" element={<AuditLogs />} />
      </Routes>
    </DashboardLayout>
  );
}
