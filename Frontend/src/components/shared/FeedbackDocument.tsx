import React, { useCallback, useState } from 'react';
import { Download, Loader2, Printer } from 'lucide-react';

/** Payload produced by the backend (app/services/report/feedback_document.py). */
export interface FeedbackDoc {
  brand?: string;
  student_name: string;
  student_id?: string | null;
  date?: string | null;
  subject_name?: string | null;
  assessment_title: string;
  assessment_type?: string | null;
  rtlp_code?: string | null;
  question: string;
  max_display: string;
  score_display: string;
  final_score: number;
  criteria: {
    label: string; name: string; color: string; score_display: string; max_display: string;
    level?: string | null; level_description?: string | null;
  }[];
  paragraphs: { id: number; text: string; color: string | null; type?: string | null }[][];
  overall_feedback: string;
  faculty_comments?: string | null;
  strengths: FeedbackItem[];
  weaknesses: FeedbackItem[];
  suggestions: { category: string; items: FeedbackItem[] }[];
  subject_relevant?: boolean;
  relevance_explanation?: string | null;
}
interface FeedbackItem { id: number; color: string; comment: string }

const TINTS: Record<string, string> = {
  '#0184c7': '#e0f2fe', '#9333ea': '#f0e6ff', '#ec4899': '#fdf2f8', '#16a34a': '#f0fdf4',
  '#ea580c': '#fff7ed', '#0d9488': '#ccfbf1', '#ca8a04': '#fef9c3', '#4f46e5': '#e0e7ff',
};
const tint = (c: string | null | undefined) => (c && TINTS[c]) || '#f1f5f9';

function formatDate(iso?: string | null) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso.slice(0, 10) : d.toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' });
}

function Badge({ n, color, size = 'sm' }: { n: number; color: string; size?: 'sm' | 'md' }) {
  const dim = size === 'md' ? 'w-[22px] h-[22px] text-[9.5px]' : n >= 10 ? 'w-[17px] h-[17px] text-[8px]' : 'w-[15px] h-[15px] text-[8.5px]';
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-semibold shrink-0 select-none ${dim}`}
      style={{ backgroundColor: color, color: tint(color) }}
    >
      {n}
    </span>
  );
}

function Sheet({ children }: { children: React.ReactNode }) {
  return (
    <section className="fb-sheet relative bg-white rounded-xl border border-slate-200 shadow-[0_1px_3px_rgba(15,23,42,0.06),0_8px_24px_-12px_rgba(15,23,42,0.18)] px-6 sm:px-12 py-10 sm:py-12">
      {children}
    </section>
  );
}

function ItemsBox({ title, items, active, onPick }: {
  title: string; items: FeedbackItem[]; active: number | null; onPick: (id: number) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="border border-slate-300 px-4 sm:px-5 py-5 mb-5">
      <h4 className="font-heading font-extrabold text-[15px] text-slate-900 mb-4">{title}</h4>
      <ul className="space-y-3">
        {items.map(it => (
          <li key={`${title}-${it.id}`}>
            <button
              id={`fb-comment-${it.id}`}
              onClick={() => onPick(it.id)}
              className={`w-full text-left flex gap-3 rounded-md -mx-1.5 px-1.5 py-1 transition-colors ${active === it.id ? 'bg-slate-100 ring-1 ring-slate-300' : 'hover:bg-slate-50'}`}
            >
              <span className="pt-px"><Badge n={it.id} color={it.color} size="md" /></span>
              <span className="text-[13.5px] leading-[1.45] text-[#334055]">{it.comment}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function FeedbackDocument({ doc, onDownload, downloading }: {
  doc: FeedbackDoc; onDownload?: () => void; downloading?: boolean;
}) {
  const [active, setActive] = useState<number | null>(null);

  const focus = useCallback((id: number, target: 'segment' | 'comment') => {
    setActive(id);
    document.getElementById(target === 'segment' ? `fb-seg-${id}` : `fb-comment-${id}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, []);

  const meta = [doc.subject_name, doc.assessment_title,
    doc.rtlp_code ? `RTLP ${doc.rtlp_code} ${doc.assessment_type || ''}`.trim() : doc.assessment_type]
    .filter(Boolean).join(' · ');

  return (
    <div className="fb-doc max-w-[860px] mx-auto space-y-6">
      {(onDownload) && (
        <div className="flex flex-wrap items-center justify-end gap-2 print:hidden">
          <button onClick={() => window.print()} className="btn-secondary text-xs"><Printer className="w-3.5 h-3.5" /> Print</button>
          <button onClick={onDownload} disabled={downloading} className="btn-primary text-xs">
            {downloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
            {downloading ? 'Preparing PDF…' : 'Download PDF'}
          </button>
        </div>
      )}

      {/* Page 1 — score and criteria */}
      <Sheet>
        <h1 className="font-heading font-extrabold text-[22px] text-slate-900 tracking-tight">
          Score {doc.score_display} <span className="text-[16px] text-slate-400">/ {doc.max_display}</span>
        </h1>
        <p className="mt-2 text-[14.5px] font-medium text-[#4b5563] flex flex-wrap items-center gap-x-2.5">
          <span>{doc.student_name}</span>
          <span className="w-1 h-1 rounded-full bg-[#4b5563]" />
          <span>{formatDate(doc.date)}</span>
        </p>
        {meta && <p className="mt-1 text-xs text-slate-400">{meta}</p>}
        {doc.subject_relevant === false && doc.relevance_explanation && (
          <p className="mt-4 text-sm rounded-lg bg-red-50 border border-red-200 text-red-700 p-3">{doc.relevance_explanation}</p>
        )}
        <ul className="mt-5">
          {doc.criteria.map((c, i) => (
            <li key={c.label} className={`flex gap-3 py-2.5 ${i ? 'border-t border-slate-300/80' : ''}`}>
              <span className="mt-[6px] w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
              <div className="flex-1 min-w-0">
                <p className="text-[13.5px] font-medium text-[#334055]">
                  {c.label}. {c.name}{c.level ? <span className="text-slate-500"> — {c.level}</span> : null}
                </p>
                {c.level_description && <p className="text-[12.5px] text-slate-500 mt-0.5">{c.level_description}</p>}
              </div>
              <p className="text-[13.5px] font-semibold text-slate-900 whitespace-nowrap">
                {c.score_display}<span className="text-xs font-medium text-slate-400">/{c.max_display}</span>
              </p>
            </li>
          ))}
        </ul>
      </Sheet>

      {/* Page 2 — the student's text, numbered and highlighted by criterion */}
      {doc.paragraphs?.length > 0 && (
        <Sheet>
          <h2 className="text-[17px] font-medium text-slate-900 leading-snug">
            {doc.question} [{doc.max_display}]
          </h2>
          <div className="border-t border-slate-300 mt-4 mb-6" />
          <p className="text-[11.5px] text-slate-400 mb-4 print:hidden">Select a numbered passage to see its comment.</p>
          <div className="space-y-5 text-[14.5px] leading-[1.6] font-medium text-[#475569]">
            {doc.paragraphs.map((para, pi) => (
              <p key={pi}>
                {para.map(seg => (
                  <React.Fragment key={seg.id}>
                    {seg.color ? (
                      <span
                        id={`fb-seg-${seg.id}`}
                        role="button"
                        tabIndex={0}
                        onClick={() => focus(seg.id, 'comment')}
                        onKeyDown={e => { if (e.key === 'Enter') focus(seg.id, 'comment'); }}
                        className="relative cursor-pointer transition-[filter] hover:brightness-95 [box-decoration-break:clone] [-webkit-box-decoration-break:clone]"
                        style={{
                          backgroundColor: tint(seg.color),
                          borderBottom: `1.5px solid ${seg.color}`,
                          boxShadow: active === seg.id ? `0 0 0 2px ${seg.color}55` : undefined,
                          paddingBottom: 1,
                        }}
                      >
                        <span className="absolute -left-[7px] -top-[9px] leading-none"><Badge n={seg.id} color={seg.color} /></span>
                        {seg.text}
                      </span>
                    ) : (
                      <span id={`fb-seg-${seg.id}`}>{seg.text}</span>
                    )}{' '}
                  </React.Fragment>
                ))}
              </p>
            ))}
          </div>
        </Sheet>
      )}

      {/* Page 3 — overall feedback and the numbered comments */}
      <Sheet>
        <h3 className="font-heading font-extrabold text-[21px] text-slate-900">Overall feedback</h3>
        <p className="mt-3 text-[14px] leading-[1.55] font-medium text-[#334055] whitespace-pre-line">{doc.overall_feedback}</p>
        {doc.faculty_comments && (
          <div className="mt-5">
            <h4 className="font-heading font-extrabold text-[15px] text-slate-900">Faculty comments</h4>
            <p className="mt-2 text-[14px] leading-[1.55] font-medium text-[#334055] whitespace-pre-line">{doc.faculty_comments}</p>
          </div>
        )}
        <div className="border-t border-slate-300 my-7" />

        {(doc.strengths.length > 0 || doc.weaknesses.length > 0) && (
          <>
            <h3 className="font-heading font-extrabold text-[21px] text-slate-900 mb-4">Feedback</h3>
            <ItemsBox title="Strengths" items={doc.strengths} active={active} onPick={id => focus(id, 'segment')} />
            <ItemsBox title="Weaknesses" items={doc.weaknesses} active={active} onPick={id => focus(id, 'segment')} />
          </>
        )}
        {doc.suggestions.length > 0 && (
          <>
            <h3 className="font-heading font-extrabold text-[21px] text-slate-900 mb-4 mt-2">Suggestions</h3>
            {doc.suggestions.map(g => (
              <ItemsBox key={g.category} title={g.category} items={g.items} active={active} onPick={id => focus(id, 'segment')} />
            ))}
          </>
        )}
        <p className="text-right text-[13px] font-medium text-[#4b5563] mt-8">{doc.brand || 'EduEval AI'}</p>
      </Sheet>
    </div>
  );
}
