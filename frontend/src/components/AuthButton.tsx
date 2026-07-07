"use client";

import { useAuth } from "@/components/AuthProvider";

/**
 * Compact auth control for the utility bar. Shows a "Masuk" button for
 * anonymous visitors and the user's name + "Keluar" when signed in. Renders
 * nothing when Firebase Auth isn't configured.
 */
export default function AuthButton() {
  const { user, loading, authConfigured, signInWithGoogle, signOut } = useAuth();

  if (!authConfigured) return null;

  if (loading) {
    return (
      <span className="meta-text" style={{ fontSize: "10px", opacity: 0.6 }}>
        &nbsp;
      </span>
    );
  }

  if (user) {
    const label = user.displayName || user.email || "Akun";
    return (
      <span className="flex items-center gap-2">
        <span className="meta-text" style={{ fontSize: "10px" }}>
          {label}
        </span>
        <button
          type="button"
          onClick={() => signOut()}
          className="meta-text cursor-pointer hover:underline"
          style={{ fontSize: "10px", background: "none", border: "none" }}
        >
          Keluar
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => signInWithGoogle()}
      className="meta-text cursor-pointer hover:underline"
      style={{ fontSize: "10px", background: "none", border: "none" }}
    >
      Masuk
    </button>
  );
}
