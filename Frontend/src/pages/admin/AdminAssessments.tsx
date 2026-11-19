import React, { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  Plus, Pencil, Trash2, X, Loader2, ClipboardCheck, BookOpen, Layers, ChevronDown, ChevronUp, Scale, Ban,
} from 'lucide-react';
import { adminApi } from '../../api/client';

interface Level { name: string; description: string; min_marks: number | ''; max_marks: number | '' }
interface Criterion { name: string; max_marks: number | ''; description?: string; levels: Level[] }
interface Template {
  code: string; name: string; section: string; category: string; evaluation_mode: string;
  total_marks: number; criteria: any[];
}
interface Form {
  id?: number;
  title: string;
  description: string;
  instructions: string;
  subject_ids: number[];
  template_code: string | null;
  evaluation_mode: string;
  rubric: Criterion[];
  course_unit: string;
  reference_answer: string;
  due_date: string;
  discrepancy_threshold: number;
}

const MODE_LABEL: Record<string, string> = {
  document: 'Written / uploaded work',
  answer_key: 'Marked against an answer key',
  observation: 'Live activity (evidence from the uploaded artefact)',
};
const CATEGORY_LABEL: Record<string, string> = {
  pre_learning: 'Pre-Learning', theory: 'Theory', laboratory: 'Laboratory', practice: 'Practice',
  course_project: 'Course Project', internship: 'Internship', capstone: 'Capstone Project',
};
const DEFAULT_LEVELS = (max: number): Level[] => [
  { name: 'Excellent', description: '', min_marks: +(max * 0.85).toFixed(2), max_marks: max },
  { name: 'Good', description: '', min_marks: +(max * 0.6).toFixed(2), max_marks: +(max * 0.8).toFixed(2) },
  { name: 'Average', description: '', min_marks: +(max * 0.35).toFixed(2), max_marks: +(max * 0.55).toFixed(2) },
  { name: 'Needs Improvement', description: '', min_marks: 0, max_marks: +(max * 0.3).toFixed(2) },
];
const blankCriterion = (): Criterion => ({ name: '', max_marks: 4, levels: DEFAULT_LEVELS(4) });
const emptyForm = (): Form => ({
  title: '', description: '', instructions: '', subject_ids: [], template_code: null, evaluation_mode: 'document',
  rubric: [], course_unit: '', reference_answer: '', due_date: '', discrepancy_threshold: 0.2,
});
const fromTemplateCriteria = (criteria: any[]): Criterion[] => criteria.map(c => ({
  name: c.name, max_marks: c.max_marks, description: c.description,
  levels: (c.levels || []).map((l: any) => ({ name: l.name, description: l.description, min_marks: l.min_marks, max_marks: l.max_marks })),
}));
const total = (r: Criterion[]) => +r.reduce((s, c) => s + (Number(c.max_marks) || 0), 0).toFixed(2);
const toLocalInput = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

// ─── Rubric editor ───────────────────────────────────────────────────────────
function CriterionEditor({ c, index, onChange, onRemove, canRemove }: {
  c: Criterion; index: number; onChange: (c: Criterion) => void; onRemove: () => void; canRemove: boolean;
}) {
  const [open, setOpen] = useState(index === 0);
  const setLevel = (i: number, patch: Partial<Level>) =>
    onChange({ ...c, levels: c.levels.map((l, j) => (j === i ? { ...l, ...patch } : l)) });
  const num = (v: string) => (v === '' ? '' : Number(v));

  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center gap-3 p-3">
        <span className="w-7 h-7 rounded-lg bg-slate-100 text-slate-600 text-xs font-semibold flex items-center justify-center shrink-0">
          {String.fromCharCode(65 + index)}
        </span>
        <input className="input-field flex-1" placeholder="Criterion name" value={c.name}
          onChange={e => onChange({ ...c, name: e.target.value })} aria-label={`Criterion ${index + 1} name`} />
        <div className="flex items-center gap-1.5 shrink-0">
          <input type="number" min={0} step="any" className="input-field w-20 text-center" value={c.max_marks}
            aria-label="Maximum marks"
            onChange={e => {
              const max = num(e.target.value);
              // keep the top band reaching the maximum
              const levels = c.levels.map((l, j) => (j === 0 && max !== '' ? { ...l, max_marks: max } : l));
              onChange({ ...c, max_marks: max, levels });
            }} />
          <span className="text-xs text-slate-400">marks</span>
        </div>
        <button type="button" className="icon-btn" onClick={() => setOpen(o => !o)} aria-label={open ? 'Collapse' : 'Expand'}>
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {canRemove && (
          <button type="button" className="icon-btn hover:text-red-600" onClick={onRemove} aria-label="Remove criterion">
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
      {open && (
        <div className="border-t border-slate-100 p-3 grid sm:grid-cols-2 gap-3">
          {c.levels.map((l, i) => (
            <div key={i} className="rounded-lg bg-slate-50 border border-slate-200 p-2.5 space-y-2">
              <div className="flex items-center gap-2">
                <input className="input-field py-1.5 text-xs font-semibold flex-1" value={l.name}
                  onChange={e => setLevel(i, { name: e.target.value })} aria-label="Level name" />
                <input type="number" step="any" min={0} className="input-field py-1.5 text-xs w-16 text-center" value={l.min_marks}
                  onChange={e => setLevel(i, { min_marks: num(e.target.value) })} aria-label="Band minimum" />
                <span className="text-xs text-slate-400">–</span>
                <input type="number" step="any" min={0} className="input-field py-1.5 text-xs w-16 text-center" value={l.max_marks}
                  onChange={e => setLevel(i, { max_marks: num(e.target.value) })} aria-label="Band maximum" />
              </div>
              <textarea className="input-field text-xs" rows={2} value={l.description} placeholder="What performance at this level looks like"
                onChange={e => setLevel(i, { description: e.target.value })} aria-label="Level descriptor" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Editor modal ────────────────────────────────────────────────────────────
function AssessmentEditor({ initial, subjects, templates, onClose, onSaved }: {
  initial: Form; subjects: any[]; templates: Template[]; onClose: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState<Form>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [scaleTo, setScaleTo] = useState<number | ''>('');
  const tpl = templates.find(t => t.code === form.template_code) || null;
  const grouped = useMemo(() => {
    const g: Record<string, Template[]> = {};
    templates.forEach(t => (g[CATEGORY_LABEL[t.category] || 'Other'] ||= []).push(t));
    return g;
  }, [templates]);

  const set = (patch: Partial<Form>) => setForm(f => ({ ...f, ...patch }));
  const chooseTemplate = (code: string) => {
    if (code === '__blank') {
      set({ template_code: null, evaluation_mode: 'document', rubric: [blankCriterion()] });
      return;
    }
    const t = templates.find(x => x.code === code);
    if (!t) return;
    if (form.rubric.length && !window.confirm?.('Replace the current rubric with this template?')) return;
    set({ template_code: t.code, evaluation_mode: t.evaluation_mode, rubric: fromTemplateCriteria(t.criteria) });
  };

  const scale = () => {
    const current = total(form.rubric);
    if (!scaleTo || !current) return;
    const k = Number(scaleTo) / current;
    const r2 = (v: number | '') => (v === '' ? '' : Math.round(Number(v) * k * 100) / 100);
    set({
      rubric: form.rubric.map(c => ({
        ...c, max_marks: r2(c.max_marks),
        levels: c.levels.map(l => ({ ...l, min_marks: r2(l.min_marks), max_marks: r2(l.max_marks) })),
      })),
    });
    setScaleTo('');
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!form.subject_ids.length) return setError('Map the assessment to at least one subject.');
    if (!form.rubric.length) return setError('Choose an RTLP rubric template or build a rubric.');
    setSaving(true);
    const payload = {
      ...form,
      due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
      rubric: form.rubric.map(c => ({ ...c, max_marks: Number(c.max_marks), levels: c.levels.map(l => ({ ...l })) })),
    };
    try {
      const res = form.id ? await adminApi.updateAssessment(form.id, payload) : await adminApi.createAssessment(payload);
      toast.success(form.id ? 'Assessment updated' : 'Assessment created');
      if (res.data?.warning) toast(res.data.warning, { icon: 'ℹ️', duration: 6000 });
      onSaved();
    } catch (err: any) {
      const d = err.response?.data?.detail;
      setError(Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : d || 'Could not save the assessment');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop items-start overflow-y-auto">
      <form onSubmit={save} className="modal-panel max-w-5xl my-6 max-h-none p-0" onMouseDown={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 sticky top-0 bg-white rounded-t-2xl z-10">
          <div>
            <h2 className="font-semibold text-slate-900">{form.id ? 'Edit assessment' : 'New assessment'}</h2>
            <p className="text-xs text-slate-500">Faculty and students of every mapped subject see this assessment.</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-6 space-y-6">
          {error && <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}

          {/* Details */}
          <section className="grid md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="form-label">Title *</label>
              <input className="input-field" required value={form.title} onChange={e => set({ title: e.target.value })}
                placeholder="e.g. Reflective Essay — Synchronization" />
            </div>
            <div className="md:col-span-2">
              <label className="form-label">Question / brief</label>
              <textarea className="input-field" rows={3} value={form.description} onChange={e => set({ description: e.target.value })}
                placeholder="The question students answer. It heads the student's feedback document." />
            </div>
            <div className="md:col-span-2">
              <label className="form-label">Instructions for students</label>
              <textarea className="input-field" rows={2} value={form.instructions} onChange={e => set({ instructions: e.target.value })} />
            </div>
            <div>
              <label className="form-label">Due date</label>
              <input type="datetime-local" className="input-field" value={form.due_date} onChange={e => set({ due_date: e.target.value })} />
            </div>
            <div>
              <label className="form-label">Course unit / module</label>
              <input className="input-field" value={form.course_unit} onChange={e => set({ course_unit: e.target.value })}
                placeholder="e.g. Unit 3: Process Synchronization" />
            </div>
          </section>

          {/* Subjects */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <label className="form-label mb-0 flex items-center gap-1.5"><BookOpen className="w-4 h-4 text-slate-400" /> Map to subjects *</label>
              <span className="text-xs text-slate-400">{form.subject_ids.length} selected</span>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {subjects.map(s => {
                const on = form.subject_ids.includes(s.id);
                return (
                  <label key={s.id} className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 cursor-pointer text-sm transition-colors ${on ? 'border-primary-500 bg-primary-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                    <input type="checkbox" checked={on} className="rounded border-slate-300 text-primary-600"
                      onChange={() => set({ subject_ids: on ? form.subject_ids.filter(x => x !== s.id) : [...form.subject_ids, s.id] })} />
                    <span className="min-w-0"><span className="font-medium text-slate-800">{s.code}</span> <span className="text-slate-500 truncate">{s.name}</span></span>
                  </label>
                );
              })}
              {subjects.length === 0 && <p className="text-sm text-slate-400">Create subjects first.</p>}
            </div>
          </section>

          {/* Rubric */}
          <section className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="min-w-[260px] flex-1">
                <label className="form-label flex items-center gap-1.5"><Layers className="w-4 h-4 text-slate-400" /> Rubric (RTLP Chapter 14)</label>
                <select className="input-field" value={form.template_code ?? (form.rubric.length ? '__custom' : '')}
                  onChange={e => chooseTemplate(e.target.value)}>
                  <option value="" disabled>Choose an RTLP rubric to start from…</option>
                  {form.rubric.length > 0 && !form.template_code && <option value="__custom" disabled>Custom rubric</option>}
                  {Object.entries(grouped).map(([g, list]) => (
                    <optgroup key={g} label={`${g} Assessment`}>
                      {list.map(t => <option key={t.code} value={t.code}>{t.code} · {t.name} ({t.total_marks} marks)</option>)}
                    </optgroup>
                  ))}
                  <option value="__blank">Start from a blank rubric</option>
                </select>
              </div>
              <div>
                <label className="form-label">Evaluated as</label>
                <select className="input-field" value={form.evaluation_mode} onChange={e => set({ evaluation_mode: e.target.value })}>
                  {Object.entries(MODE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
            </div>

            {form.rubric.length > 0 && (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 border border-slate-200 px-4 py-2.5">
                  <p className="text-sm text-slate-700">
                    <strong>{form.rubric.length}</strong> criteria · total <strong>{total(form.rubric)}</strong> marks
                    {tpl && <span className="text-slate-500"> · from RTLP {tpl.code} {tpl.name} ({tpl.total_marks} marks)</span>}
                  </p>
                  <div className="flex items-center gap-2">
                    <input type="number" min={1} className="input-field w-24 py-1.5" placeholder="Total" value={scaleTo}
                      onChange={e => setScaleTo(e.target.value === '' ? '' : Number(e.target.value))} aria-label="Scale rubric to total marks" />
                    <button type="button" className="btn-secondary text-xs" onClick={scale} disabled={!scaleTo}><Scale className="w-3.5 h-3.5" /> Scale marks</button>
                  </div>
                </div>
                <div className="space-y-2.5">
                  {form.rubric.map((c, i) => (
                    <CriterionEditor key={i} c={c} index={i} canRemove={form.rubric.length > 1}
                      onChange={nc => set({ rubric: form.rubric.map((x, j) => (j === i ? nc : x)) })}
                      onRemove={() => set({ rubric: form.rubric.filter((_, j) => j !== i) })} />
                  ))}
                </div>
                <button type="button" className="btn-ghost text-xs" onClick={() => set({ rubric: [...form.rubric, blankCriterion()] })}>
                  <Plus className="w-3.5 h-3.5" /> Add criterion
                </button>
              </>
            )}
          </section>

          <section>
            <label className="form-label">
              {form.evaluation_mode === 'answer_key' ? 'Answer key *' : 'Model answer / key points (optional)'}
              <span className="text-slate-400 font-normal"> — used by the AI, never shown to students</span>
            </label>
            <textarea className="input-field" rows={3} value={form.reference_answer} required={form.evaluation_mode === 'answer_key'}
              onChange={e => set({ reference_answer: e.target.value })} />
          </section>
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-slate-200 bg-slate-50 rounded-b-2xl">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 animate-spin" />} {form.id ? 'Save changes' : 'Create assessment'}
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────
export default function AdminAssessments() {
  const [items, setItems] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Form | null>(null);
  const [filter, setFilter] = useState<number | 'all'>('all');
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [a, s, t] = await Promise.all([adminApi.listAssessments(), adminApi.listSubjects(), adminApi.getRubricTemplates()]);
      setItems(a.data); setSubjects(s.data); setTemplates(t.data);
    } catch {
      toast.error('Could not load assessments');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const openEdit = async (id: number) => {
    try {
      const { data } = await adminApi.getAssessment(id);
      setEditing({
        id: data.id, title: data.title, description: data.description || '', instructions: data.instructions || '',
        subject_ids: data.subject_ids, template_code: data.template_code, evaluation_mode: data.evaluation_mode || 'document',
        rubric: fromTemplateCriteria(data.rubric || []), course_unit: data.course_unit || '',
        reference_answer: data.reference_answer || '', due_date: toLocalInput(data.due_date),
        discrepancy_threshold: data.discrepancy_threshold ?? 0.2,
      });
    } catch {
      toast.error('Could not open the assessment');
    }
  };

  const deactivate = async (id: number) => {
    try {
      await adminApi.deactivateAssessment(id);
      toast.success('Assessment deactivated');
      setConfirmId(null);
      load();
    } catch {
      toast.error('Could not deactivate');
    }
  };

  const visible = items.filter(a => filter === 'all' || a.subject_ids.includes(filter));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Assessments</h1>
          <p className="page-subtitle">Create assessments with RTLP rubrics and map them to subjects. Faculty and students see them automatically.</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="input-field w-56" value={filter} onChange={e => setFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            aria-label="Filter by subject">
            <option value="all">All subjects</option>
            {subjects.map(s => <option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}
          </select>
          <button className="btn-primary" onClick={() => setEditing(emptyForm())}><Plus className="w-4 h-4" /> New assessment</button>
        </div>
      </div>

      {loading ? (
        <div className="card text-center text-slate-500 py-12"><Loader2 className="w-5 h-5 animate-spin inline" /> Loading…</div>
      ) : visible.length === 0 ? (
        <div className="card text-center py-14">
          <ClipboardCheck className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <p className="font-medium text-slate-700">No assessments yet</p>
          <p className="text-sm text-slate-500 mt-1">Create one from an RTLP rubric and map it to your subjects.</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="px-5 py-3 font-semibold">Assessment</th>
                  <th className="px-5 py-3 font-semibold">Subjects</th>
                  <th className="px-5 py-3 font-semibold">Rubric</th>
                  <th className="px-5 py-3 font-semibold text-right">Marks</th>
                  <th className="px-5 py-3 font-semibold text-right">Submissions</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {visible.map(a => (
                  <tr key={a.id} className="border-t border-slate-100 hover:bg-slate-50/60">
                    <td className="px-5 py-3.5">
                      <p className="font-medium text-slate-900">{a.title}</p>
                      <p className="text-xs text-slate-500">
                        {a.due_date ? `Due ${new Date(a.due_date).toLocaleDateString()}` : 'No due date'}
                        {a.evaluation_mode !== 'document' && ` · ${MODE_LABEL[a.evaluation_mode]}`}
                      </p>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex flex-wrap gap-1">
                        {a.subjects.map((s: any) => <span key={s.id} className="badge-neutral">{s.code}</span>)}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {a.rubric_source || '—'}
                      {!a.admin_managed && <span className="block text-amber-600">Legacy (faculty-created)</span>}
                    </td>
                    <td className="px-5 py-3.5 text-right font-medium text-slate-800">{a.max_marks}</td>
                    <td className="px-5 py-3.5 text-right text-slate-600">
                      {a.submission_count}
                      {a.published_count > 0 && <span className="block text-xs text-emerald-600">{a.published_count} published</span>}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={a.is_active ? 'badge-approved' : 'badge-neutral'}>{a.is_active ? 'Active' : 'Inactive'}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex justify-end gap-1">
                        <button className="icon-btn" onClick={() => openEdit(a.id)} aria-label={`Edit ${a.title}`}><Pencil className="w-4 h-4" /></button>
                        {a.is_active && (
                          confirmId === a.id ? (
                            <span className="flex items-center gap-1">
                              <button className="btn-danger text-xs py-1 px-2" onClick={() => deactivate(a.id)}>Deactivate</button>
                              <button className="btn-ghost text-xs py-1 px-2" onClick={() => setConfirmId(null)}>Keep</button>
                            </span>
                          ) : (
                            <button className="icon-btn hover:text-red-600" onClick={() => setConfirmId(a.id)} aria-label={`Deactivate ${a.title}`}>
                              <Ban className="w-4 h-4" />
                            </button>
                          )
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {editing && (
        <AssessmentEditor initial={editing} subjects={subjects} templates={templates}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
    </div>
  );
}
