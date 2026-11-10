import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { GraduationCap, Eye, EyeOff, AlertCircle } from 'lucide-react';

type Portal = 'admin' | 'faculty' | 'student';

const portalConfig: Record<Portal, { label: string; color: string; email: string; password: string; hint: string }> = {
  admin: {
    label: 'Admin Portal',
    color: 'from-slate-800 to-slate-900',
    email: 'admin@edueval.ai',
    password: 'Admin@123',
    hint: 'Default: admin@edueval.ai / Admin@123',
  },
  faculty: {
    label: 'Faculty Portal',
    color: 'from-primary-700 to-primary-900',
    email: '',
    password: '',
    hint: 'Use credentials provided by your administrator',
  },
  student: {
    label: 'Student Portal',
    color: 'from-indigo-600 to-purple-700',
    email: '',
    password: '',
    hint: 'Use credentials provided by your institution',
  },
};

export default function LoginPage() {
  const [portal, setPortal] = useState<Portal>('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handlePortalChange = (p: Portal) => {
    setPortal(p);
    setError('');
    setEmail('');
    setPassword('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      const role = localStorage.getItem('role');
      if (role === 'admin') navigate('/admin');
      else if (role === 'faculty') navigate('/faculty');
      else navigate('/student');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const cfg = portalConfig[portal];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-100 to-blue-50 flex flex-col items-center justify-center p-4">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-3 mb-3">
          <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center">
            <GraduationCap className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-slate-800">EduEval AI</h1>
        </div>
        <p className="text-slate-500 text-sm">AI-Powered Academic Evaluation Platform</p>
      </div>

      {/* Portal Selector */}
      <div className="flex gap-2 mb-6 bg-white rounded-xl p-1.5 shadow-sm border border-edu-border">
        {(['admin', 'faculty', 'student'] as Portal[]).map((p) => (
          <button
            key={p}
            onClick={() => handlePortalChange(p)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              portal === p
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {p.charAt(0).toUpperCase() + p.slice(1)}
          </button>
        ))}
      </div>

      {/* Login Card */}
      <div className="w-full max-w-md">
        <div className="card shadow-lg">
          <div className={`-mx-6 -mt-6 mb-6 px-6 py-5 rounded-t-xl bg-gradient-to-r ${cfg.color}`}>
            <h2 className="text-xl font-bold text-white">{cfg.label}</h2>
            <p className="text-white/70 text-sm mt-1">{cfg.hint}</p>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mb-4">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your email"
                className="input-field"
                required
                autoComplete="email"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="input-field pr-10"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-2 py-2.5"
            >
              {loading ? 'Signing in...' : `Sign in to ${cfg.label}`}
            </button>
          </form>
        </div>

        {portal === 'admin' && (
          <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-center">
            <p className="text-amber-700 text-xs">
              🔑 First login: admin@edueval.ai / Admin@123 — Change password after first login
            </p>
          </div>
        )}
      </div>

      <p className="mt-8 text-slate-400 text-xs">
        © 2024 EduEval AI · Academic Evaluation Platform
      </p>
    </div>
  );
}

