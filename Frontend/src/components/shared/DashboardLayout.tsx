import React, { ReactNode, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth, ROLE_LABEL } from '../../contexts/AuthContext';
import { authApi } from '../../api/client';
import {
  GraduationCap, LogOut, Menu, X, ChevronDown, KeyRound, Loader2, ShieldCheck,
} from 'lucide-react';

interface NavItem {
  label: string;
  to: string;
  icon: React.ElementType;
  /** Extra route prefixes that belong to this item (e.g. detail pages). */
  match?: string[];
}

interface DashboardLayoutProps {
  children: ReactNode;
  navItems: NavItem[];
  portalLabel: string;
  /** Kept for backwards compatibility; the accent is now derived from the user's role. */
  portalColor?: string;
}

const ROLE_ACCENT: Record<string, { chip: string; avatar: string; dot: string }> = {
  admin:   { chip: 'bg-slate-100 text-slate-700 ring-slate-200',  avatar: 'bg-slate-700',   dot: 'bg-slate-500' },
  faculty: { chip: 'bg-primary-50 text-primary-700 ring-primary-100', avatar: 'bg-primary-600', dot: 'bg-primary-500' },
  student: { chip: 'bg-indigo-50 text-indigo-700 ring-indigo-100', avatar: 'bg-indigo-600',  dot: 'bg-indigo-500' },
};

function initials(name?: string) {
  if (!name) return '?';
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join('');
}

function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (next.length < 6) return setError('New password must be at least 6 characters.');
    if (next !== confirm) return setError('New passwords do not match.');
    setSaving(true);
    try {
      await authApi.changePassword(current, next);
      toast.success('Password updated');
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not update password.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-panel max-w-md" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center">
              <KeyRound className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-900">Change password</h3>
              <p className="text-xs text-slate-500">Use at least 6 characters.</p>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn" aria-label="Close"><X className="w-4 h-4" /></button>
        </div>
        {error && <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="form-label">Current password</label>
            <input type="password" className="input-field" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
          </div>
          <div>
            <label className="form-label">New password</label>
            <input type="password" className="input-field" value={next} onChange={(e) => setNext(e.target.value)} required minLength={6} autoComplete="new-password" />
          </div>
          <div>
            <label className="form-label">Confirm new password</label>
            <input type="password" className="input-field" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />} Update password
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children, navItems, portalLabel }: DashboardLayoutProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const accent = ROLE_ACCENT[user?.role || 'student'];
  const roots = navItems.length ? [navItems[0].to] : [];

  const isActive = (item: NavItem) =>
    location.pathname === item.to ||
    (!roots.includes(item.to) && location.pathname.startsWith(item.to + '/')) ||
    (item.match || []).some((m) => location.pathname === m || location.pathname.startsWith(m + '/'));

  const current = [...navItems].sort((a, b) => b.to.length - a.to.length).find(isActive) || null;

  useEffect(() => { setMobileOpen(false); setMenuOpen(false); }, [location.pathname]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const handleLogout = () => {
    logout();
    toast.success('Signed out');
    navigate('/login', { replace: true });
  };

  const sidebar = (
    <div className="flex flex-col h-full bg-slate-950 text-slate-300">
      <div className="h-16 px-5 flex items-center gap-3 border-b border-white/5 shrink-0">
        <div className="w-9 h-9 rounded-lg bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-900/40">
          <GraduationCap className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-white tracking-tight">EduEval AI</p>
          <p className="text-[11px] text-slate-500 truncate">{portalLabel}</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Navigation</p>
        <ul className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = current?.to === item.to;
            return (
              <li key={item.to}>
                <Link
                  to={item.to}
                  className={`group flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                    active
                      ? 'bg-white/10 text-white font-medium'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-primary-100' : 'text-slate-500 group-hover:text-slate-300'}`} />
                  <span className="truncate">{item.label}</span>
                  {active && <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-500" />}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-3 border-t border-white/5 shrink-0">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className={`w-9 h-9 rounded-full ${accent.avatar} flex items-center justify-center text-xs font-semibold text-white`}>
            {initials(user?.full_name)}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
            <p className="text-[11px] text-slate-500 truncate">{user?.email || ROLE_LABEL[user!.role]}</p>
          </div>
          <button onClick={handleLogout} className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-white/5" title="Sign out" aria-label="Sign out">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-edu-bg overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden lg:block w-64 shrink-0">{sidebar}</aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85%] shadow-2xl">{sidebar}</aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white/90 backdrop-blur border-b border-edu-border px-4 sm:px-6 flex items-center gap-3 shrink-0 z-20">
          <button className="lg:hidden icon-btn -ml-1" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu className="w-5 h-5" />
          </button>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wider hidden sm:block">{portalLabel}</p>
            <h1 className="text-base sm:text-lg font-semibold text-slate-900 truncate leading-tight">{current?.label || portalLabel}</h1>
          </div>

          <span className={`hidden md:inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ring-1 ${accent.chip}`}>
            <ShieldCheck className="w-3.5 h-3.5" /> {user ? ROLE_LABEL[user.role] : ''}
          </span>

          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((o) => !o)}
              className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-full hover:bg-slate-100 transition-colors"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <span className={`w-8 h-8 rounded-full ${accent.avatar} text-white text-xs font-semibold flex items-center justify-center`}>
                {initials(user?.full_name)}
              </span>
              <ChevronDown className="w-4 h-4 text-slate-400 hidden sm:block" />
            </button>
            {menuOpen && (
              <div role="menu" className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-xl ring-1 ring-slate-200 py-1.5 z-50">
                <div className="px-4 py-3 border-b border-slate-100">
                  <p className="text-sm font-semibold text-slate-900 truncate">{user?.full_name}</p>
                  {user?.email && <p className="text-xs text-slate-500 truncate">{user.email}</p>}
                  <span className={`inline-flex items-center gap-1.5 mt-2 text-[11px] font-medium px-2 py-0.5 rounded-full ring-1 ${accent.chip}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${accent.dot}`} /> {user ? ROLE_LABEL[user.role] : ''}
                  </span>
                </div>
                <button onClick={() => { setMenuOpen(false); setPwOpen(true); }} className="menu-item" role="menuitem">
                  <KeyRound className="w-4 h-4 text-slate-400" /> Change password
                </button>
                <button onClick={handleLogout} className="menu-item text-red-600 hover:bg-red-50" role="menuitem">
                  <LogOut className="w-4 h-4" /> Sign out
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">{children}</div>
        </main>
      </div>

      {pwOpen && <ChangePasswordModal onClose={() => setPwOpen(false)} />}
    </div>
  );
}
