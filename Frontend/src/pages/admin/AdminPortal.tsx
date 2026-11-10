import React, { useEffect, useState } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import DashboardLayout from '../../components/shared/DashboardLayout';
import { adminApi } from '../../api/client';
import {
  LayoutDashboard, Users, BookOpen, FileText,
  UserPlus, Settings, ClipboardList, Shield, BarChart3
} from 'lucide-react';

const navItems = [
  { label: 'Dashboard', to: '/admin', icon: LayoutDashboard },
  { label: 'Faculty Management', to: '/admin/faculty', icon: Users },
  { label: 'Student Management', to: '/admin/students', icon: Users },
  { label: 'Subjects', to: '/admin/subjects', icon: BookOpen },
  { label: 'All Submissions', to: '/admin/submissions', icon: FileText },
  { label: 'Audit Logs', to: '/admin/audit', icon: ClipboardList },
];

// ─── Stat Card ────────────────────────────────────────────────────────────────
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="card">
      <p className="text-sm text-slate-500 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
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
        <h2 className="text-xl font-bold text-slate-800">Institution Overview</h2>
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
        <h2 className="text-xl font-bold text-slate-800">Faculty Management</h2>
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
        <h2 className="text-xl font-bold text-slate-800">Student Management</h2>
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
        <h2 className="text-xl font-bold text-slate-800">Subject Management</h2>
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
      <h2 className="text-xl font-bold text-slate-800 mb-6">Audit Logs</h2>
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
      <h2 className="text-xl font-bold text-slate-800 mb-6">All Submissions</h2>
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

// ─── Admin Portal ─────────────────────────────────────────────────────────────
export default function AdminPortal() {
  return (
    <DashboardLayout navItems={navItems} portalLabel="Admin Portal" portalColor="bg-slate-800">
      <Routes>
        <Route path="/" element={<AdminDashboard />} />
        <Route path="/faculty" element={<FacultyManagement />} />
        <Route path="/students" element={<StudentManagement />} />
        <Route path="/subjects" element={<SubjectManagement />} />
        <Route path="/submissions" element={<AllSubmissions />} />
        <Route path="/audit" element={<AuditLogs />} />
      </Routes>
    </DashboardLayout>
  );
}

