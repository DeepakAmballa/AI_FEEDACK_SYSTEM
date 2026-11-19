import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth, ROLE_HOME, Role } from './contexts/AuthContext';
import LoginPage from './pages/auth/LoginPage';
import AdminPortal from './pages/admin/AdminPortal';
import FacultyPortal from './pages/faculty/FacultyPortal';
import StudentPortal from './pages/student/StudentPortal';
import { GraduationCap } from 'lucide-react';

function FullPageLoader() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-edu-bg gap-4">
      <div className="w-12 h-12 rounded-xl bg-primary-600 flex items-center justify-center shadow-lg shadow-primary-600/30 animate-pulse">
        <GraduationCap className="w-6 h-6 text-white" />
      </div>
      <p className="text-sm text-slate-500">Loading your workspace…</p>
    </div>
  );
}

/**
 * Strict role guard: only the given role may enter. Unauthenticated users go to
 * the login page (remembering where they wanted to go); users of another role are
 * sent to their own portal.
 */
function RoleRoute({ role, children }: { role: Role; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role !== role) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <>{children}</>;
}

/** The login page is only for signed-out users. */
function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <>{children}</>;
}

function RootRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <FullPageLoader />;
  return <Navigate to={user ? ROLE_HOME[user.role] : '/login'} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
      <Route path="/admin/*" element={<RoleRoute role="admin"><AdminPortal /></RoleRoute>} />
      <Route path="/faculty/*" element={<RoleRoute role="faculty"><FacultyPortal /></RoleRoute>} />
      <Route path="/student/*" element={<RoleRoute role="student"><StudentPortal /></RoleRoute>} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster
          position="top-right"
          toastOptions={{
            style: { borderRadius: '10px', fontSize: '14px', border: '1px solid #e2e8f0' },
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  );
}
