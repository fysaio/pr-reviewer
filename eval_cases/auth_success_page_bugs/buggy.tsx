'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import { Loader2 } from 'lucide-react';
import { Suspense } from 'react';

// Extract component that uses useSearchParams
function AuthSuccessContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleOAuthCallback } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const returnUrl = searchParams.get('returnUrl');

    if (code) {
      handleOAuthCallback(code, state)
        .then(() => {
          router.push(returnUrl || '/');
        })
        .catch((error) => {
          console.error('OAuth callback failed:', error);
          router.push('/login?error=true');
        });
    } else {
      router.push('/login?error=Invalid%20callback%20parameters');
    }
  }, [searchParams, handleOAuthCallback, router]);

  return (
    <div className="flex h-screen w-full items-center justify-center">
      <div className="text-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto mb-4" />
        <p className="text-muted-foreground">Completing authentication...</p>
      </div>
    </div>
  );
}

// Main page component wrapped in Suspense
export default function AuthSuccessPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen w-full items-center justify-center">
        <div className="text-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    }>
      <AuthSuccessContent />
    </Suspense>
  );
}