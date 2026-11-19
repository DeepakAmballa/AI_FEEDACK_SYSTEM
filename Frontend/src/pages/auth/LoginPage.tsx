import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth, ROLE_HOME } from '../../contexts/AuthContext';
import {
  GraduationCap, Eye, EyeOff, AlertCircle, Mail, Lock, ArrowRight,
  ShieldCheck, Sparkles, BarChart3, Loader2, Info,
} from 'lucide-react';

const FEATURES = [
  { icon: Sparkles, title: 'AI-assisted evaluation', text: 'Rubric-aligned scoring and feedback grounded in course material.' },
  { icon: ShieldCheck, title: 'Faculty in control', text: 'Every AI result is reviewed, edited and approved before release.' },
  { icon: BarChart3, title: 'Actionable insights', text: 'Clear strengths, gaps and suggestions for every submission.' },
];

export default function LoginPage() {
  const [email, setEmail] = useState(() => localStorage.getItem('remembered_email') || '');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(() => !!localStorage.getItem('remembered_email'));
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const n = sessionStorage.getItem('auth_notice');
    if (n) {
      setNotice(n);
      sessionStorage.removeItem('auth_notice');
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const user = await login(email, password);
      if (remember) localStorage.setItem('remembered_email', email.trim());
      else localStorage.removeItem('remembered_email');

      // Role decides the destination. A deep link is honoured only inside the user's own portal.
      const home = ROLE_HOME[user.role];
      const from = (location.state as { from?: string } | null)?.from;
      const target = from && (from === home || from.startsWith(home + '/')) ? from : home;
      navigate(target, { replace: true });
    } catch (err: any) {
      if (!err.response) setError('Unable to reach the server. Please check your connection and try again.');
      else setError(err.response?.data?.detail || 'Sign in failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-white">
      {/* Brand panel */}
      <aside className="hidden lg:flex lg:w-[46%] xl:w-1/2 relative overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(37,99,235,0.45),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(99,102,241,0.35),transparent_55%)]" />
        <div className="absolute inset-0 opacity-[0.07] bg-[linear-gradient(to_right,#fff_1px,transparent_1px),linear-gradient(to_bottom,#fff_1px,transparent_1px)] bg-[size:44px_44px]" />
        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16 w-full">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/10 ring-1 ring-white/20 backdrop-blur flex items-center justify-center">
              <GraduationCap className="w-6 h-6" />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight">EduEval AI</p>
              <p className="text-xs text-slate-400">Academic Evaluation Platform</p>
            </div>
          </div>

          <div className="max-w-md">
            <h1 className="text-4xl xl:text-[2.75rem] font-semibold leading-tight tracking-tight">
              Fair, consistent and transparent assessment.
            </h1>
            <p className="mt-4 text-slate-300 leading-relaxed">
              One secure sign-in for administrators, faculty and students. You'll be taken
              straight to the workspace for your role.
            </p>
            <ul className="mt-10 space-y-5">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <li key={title} className="flex gap-4">
                  <div className="w-10 h-10 shrink-0 rounded-lg bg-white/10 ring-1 ring-white/15 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-primary-100" />
                  </div>
                  <div>
                    <p className="font-medium">{title}</p>
                    <p className="text-sm text-slate-400">{text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-slate-500">© {new Date().getFullYear()} EduEval AI. All rights reserved.</p>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex-1 flex items-center justify-center px-6 py-12 bg-edu-bg lg:bg-white">
        <div className="w-full max-w-[400px]">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-11 h-11 rounded-xl bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-600/25">
              <GraduationCap className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-lg font-semibold text-slate-900">EduEval AI</p>
              <p className="text-xs text-slate-500">Academic Evaluation Platform</p>
            </div>
          </div>

          <h2 className="text-2xl font-semibold text-slate-900 tracking-tight">Welcome back</h2>
          <p className="mt-1.5 text-sm text-slate-500">Sign in with your institutional account to continue.</p>

          {notice && (
            <div className="mt-6 flex items-start gap-2.5 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
              <Info className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{notice}</span>
            </div>
          )}
          {error && (
            <div role="alert" className="mt-6 flex items-start gap-2.5 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate={false}>
            <div>
              <label htmlFor="email" className="form-label">Email address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@institution.edu"
                  className="input-field pl-10 py-2.5"
                  required
                  autoFocus={!email}
                  autoComplete="username"
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="form-label">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  id="password"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="input-field pl-10 pr-10 py-2.5"
                  required
                  autoFocus={!!email}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-slate-600 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                Remember my email
              </label>
              <span className="text-slate-400 text-xs">Forgot password? Contact your admin</span>
            </div>

            <button type="submit" disabled={loading || !email || !password} className="btn-primary w-full py-2.5 text-[15px]">
              {loading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Signing in…</>
              ) : (
                <>Sign in <ArrowRight className="w-4 h-4" /></>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-edu-border">
            <p className="text-xs text-slate-500 text-center leading-relaxed">
              Administrators, faculty and students all sign in here. Access is granted
              automatically based on the role assigned to your account.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
