'use client'; // This layout needs to be a Client Component to use hooks

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import useAuthStore from '@/store/authStore';

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const router = useRouter();

  // Handle Zustand hydration and initial check
  const [isClient, setIsClient] = React.useState(false);
  useEffect(() => {
    setIsClient(true);
  }, []);

  useEffect(() => {
    // Only run the check on the client-side after hydration
    if (isClient && !isLoggedIn) {
      router.replace('/login'); // Redirect to login if not authenticated
    }
  }, [isClient, isLoggedIn, router]);

  // Render children only if logged in (or during initial client render before check)
  // This prevents flashing the protected content briefly before redirecting
  if (!isClient || !isLoggedIn) {
    // Optionally return a loading spinner or null while checking/redirecting
    return null;
  }

  // If logged in, render the actual page content
  return <>{children}</>;
}
