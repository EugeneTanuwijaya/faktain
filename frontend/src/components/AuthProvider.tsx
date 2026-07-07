"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  User,
} from "firebase/auth";
import { firebaseAuth, googleProvider, isAuthConfigured } from "@/lib/firebase";
import { setTokenProvider } from "@/lib/api";

interface AuthContextValue {
  /** The signed-in Firebase user, or null when anonymous. */
  user: User | null;
  /** True while the initial auth state is resolving. */
  loading: boolean;
  /** Whether Firebase Auth is configured in this environment. */
  authConfigured: boolean;
  /** Any error from the last sign-in attempt. */
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const authConfigured = isAuthConfigured();

  useEffect(() => {
    if (!firebaseAuth) {
      setLoading(false);
      return;
    }
    const unsubscribe = onAuthStateChanged(firebaseAuth, (nextUser) => {
      setUser(nextUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  // Bridge the Firebase token into the axios layer so API calls are
  // authenticated without each caller having to fetch a token.
  useEffect(() => {
    setTokenProvider(async () => {
      if (!firebaseAuth?.currentUser) return null;
      try {
        return await firebaseAuth.currentUser.getIdToken();
      } catch {
        return null;
      }
    });
    return () => setTokenProvider(null);
  }, []);

  const signInWithGoogle = useCallback(async () => {
    if (!firebaseAuth) {
      setError("Login belum dikonfigurasi di lingkungan ini.");
      return;
    }
    setError(null);
    try {
      await signInWithPopup(firebaseAuth, googleProvider);
    } catch (err: unknown) {
      const code =
        err && typeof err === "object" && "code" in err
          ? String((err as { code: string }).code)
          : "";
      if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") {
        return; // user dismissed the popup; not an error worth showing
      }
      setError("Gagal masuk dengan Google. Silakan coba lagi.");
    }
  }, []);

  const signOut = useCallback(async () => {
    if (!firebaseAuth) return;
    await firebaseSignOut(firebaseAuth);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      authConfigured,
      error,
      signInWithGoogle,
      signOut,
    }),
    [user, loading, authConfigured, error, signInWithGoogle, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error("useAuth harus dipakai di dalam <AuthProvider>");
  }
  return ctx;
}
