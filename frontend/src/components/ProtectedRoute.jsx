import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function ProtectedRoute({ children }) {
  const { user, isAdmin } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  // Admin accidentally on user dashboard → send to admin portal
  if (isAdmin) return <Navigate to="/admin" replace />;
  return children;
}
