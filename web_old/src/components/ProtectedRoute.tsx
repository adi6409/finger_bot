import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import useAuthStore from '../store/authStore';

const ProtectedRoute: React.FC = () => {
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);

  // If logged in, render the child route (using Outlet)
  // Otherwise, redirect to the login page
  return isLoggedIn ? <Outlet /> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
