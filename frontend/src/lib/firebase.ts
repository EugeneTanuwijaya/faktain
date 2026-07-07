"use client";

import { FirebaseApp, getApp, getApps, initializeApp } from "firebase/app";
import { Auth, getAuth, GoogleAuthProvider } from "firebase/auth";

/**
 * Firebase client configuration.
 *
 * All values are public (NEXT_PUBLIC_*) by design — Firebase web config is not
 * secret; access is controlled by Firebase security rules and Auth settings.
 *
 * Auth is *optional*: if the API key is not configured, `firebaseAuth` is null
 * and the app runs in anonymous mode. UI should check `isAuthConfigured()`.
 */
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function isAuthConfigured(): boolean {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain);
}

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (isAuthConfigured()) {
  app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  auth = getAuth(app);
}

export const firebaseApp = app;
export const firebaseAuth = auth;

export const googleProvider = new GoogleAuthProvider();
