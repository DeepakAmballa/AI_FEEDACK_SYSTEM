import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/auth/LoginPage';
import AdminPortal from './pages/admin/AdminPortal';
import FacultyPortal from './pages/faculty/FacultyPortal';
import StudentPortal from './pages/student/StudentPortal';

function ProtectedRoute({ children, role }: { children: React.ReactNode; role?: string }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-slate-500">Loading...</div>
    </div>
  );
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role && !(role === 'faculty' && user.role === 'admin')) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function RootRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === 'admin') return <Navigate to="/admin" replace />;
  if (user.role === 'faculty') return <Navigate to="/faculty" replace />;
  return <Navigate to="/student" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/admin/*" element={
        <ProtectedRoute role="admin">
          <AdminPortal />
        </ProtectedRoute>
      } />
      <Route path="/faculty/*" element={
        <ProtectedRoute role="faculty">
          <FacultyPortal />
        </ProtectedRoute>
      } />
      <Route path="/student/*" element={
        <ProtectedRoute role="student">
          <StudentPortal />
        </ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
        <Toaster position="top-right" />
      </AuthProvider>
    </BrowserRouter>
  );
}

