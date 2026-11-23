import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import { onIdTokenChanged, signInWithEmailAndPassword, signOut } from "firebase/auth";
import { auth } from "../lib/firebase";
import { api, setClientAuthToken, registerUnauthorizedCallback, ApiError } from "../api/client";

export interface User {
  uid: string;
  email: string;
  name: string;
  role: "CATALOGUE_ADMIN" | "APPROVER" | "PLATFORM_ADMIN";
  token: string;
  avatar: string;
  isMock?: boolean;
}

export const MOCK_USERS: Record<string, Omit<User, "uid" | "email">> = {
  catalogue: {
    name: "Lakshmi",
    role: "CATALOGUE_ADMIN",
    token: "mock-catalogue-token",
    avatar: "L",
    isMock: true
  },
  approver: {
    name: "Sandeep",
    role: "APPROVER",
    token: "mock-approver-token",
    avatar: "S",
    isMock: true
  },
  admin: {
    name: "Platform Admin",
    role: "PLATFORM_ADMIN",
    token: "mock-admin-token",
    avatar: "A",
    isMock: true
  }
};

interface AuthContextType {
  currentUser: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginAs: (key: "catalogue" | "approver" | "admin") => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Define logout first so it can be referenced in callbacks
  const logout = () => {
    localStorage.removeItem("mock_user_key");
    setClientAuthToken("");
    setCurrentUser(null);
    if (auth) {
      signOut(auth).catch(() => {});
    }
  };

  useEffect(() => {
    // Register the 401 logout callback in the API client
    registerUnauthorizedCallback(logout);

    if (!auth) {
      // Firebase not configured: fallback entirely to mock authentication
      const saved = localStorage.getItem("mock_user_key") || "catalogue";
      if (saved && MOCK_USERS[saved]) {
        const mock = MOCK_USERS[saved];
        setClientAuthToken(mock.token);
        setCurrentUser({
          uid: `${saved}-uid`,
          email: `${saved}@example.com`,
          ...mock
        });
      }
      setLoading(false);
      return;
    }

    // Subscribe to Firebase ID Token state changes (handles logins, logouts, and token refreshes)
    const unsubscribe = onIdTokenChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        try {
          const token = await firebaseUser.getIdToken();
          setClientAuthToken(token);
          
          // Retrieve the authorized profile (role & name) from the backend
          const me = await api.getMe();
          
          setCurrentUser({
            uid: firebaseUser.uid,
            email: firebaseUser.email || "",
            name: me.name || firebaseUser.email?.split("@")[0] || "User",
            role: me.role,
            token: token,
            avatar: (me.name || firebaseUser.email || "U")[0].toUpperCase()
          });
        } catch (err) {
          console.error("Backend profile validation failed on auth state change:", err);
          logout();
        }
      } else {
        // No Firebase user: check for mock session (fallback to default catalogue user)
        const saved = localStorage.getItem("mock_user_key") || "catalogue";
        if (saved && MOCK_USERS[saved]) {
          const mock = MOCK_USERS[saved];
          setClientAuthToken(mock.token);
          setCurrentUser({
            uid: `${saved}-uid`,
            email: `${saved}@example.com`,
            ...mock
          });
        } else {
          setCurrentUser(null);
        }
      }
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const login = async (email: string, password: string) => {
    if (!auth) {
      throw new Error("Authentication provider not configured.");
    }
    setLoading(true);
    try {
      if (import.meta.env.DEV) {
        console.log("Firebase sign-in started");
      }
      const credential = await signInWithEmailAndPassword(auth, email, password);
      const firebaseUser = credential.user;
      if (import.meta.env.DEV) {
        console.log("Firebase sign-in successful, UID:", firebaseUser.uid);
      }

      const token = await firebaseUser.getIdToken();
      if (import.meta.env.DEV) {
        console.log("Firebase token obtained");
      }

      setClientAuthToken(token);

      if (import.meta.env.DEV) {
        console.log("Calling /api/auth/me");
      }

      let me;
      try {
        me = await api.getMe();
        if (import.meta.env.DEV) {
          console.log("/api/auth/me response status: success");
          console.log("Profile loaded:", me);
        }
      } catch (profileErr: any) {
        console.error("Backend profile validation failed during login:", profileErr);
        await signOut(auth);
        setClientAuthToken("");
        setCurrentUser(null);

        if (profileErr instanceof ApiError && profileErr.message.includes("profile is not configured")) {
          throw new Error("Authentication succeeded, but your user profile is not configured. Please contact the administrator.");
        } else if (profileErr instanceof ApiError && profileErr.status === 403) {
          throw new Error("This account is inactive. Please contact the administrator.");
        } else {
          throw new Error(profileErr.message || "Authentication succeeded, but unable to load your user profile. Please contact the administrator.");
        }
      }

      const userObject: User = {
        uid: firebaseUser.uid,
        email: firebaseUser.email || "",
        name: me.name || firebaseUser.email?.split("@")[0] || "User",
        role: me.role,
        token: token,
        avatar: (me.name || firebaseUser.email || "U")[0].toUpperCase()
      };

      setCurrentUser(userObject);
      if (import.meta.env.DEV) {
        console.log("Authentication completed");
      }
    } catch (err) {
      setLoading(false);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const loginAs = (key: "catalogue" | "approver" | "admin") => {
    // Save to localStorage for persistence across reloads in mock dev mode
    localStorage.setItem("mock_user_key", key);
    const mock = MOCK_USERS[key];
    setClientAuthToken(mock.token);
    setCurrentUser({
      uid: `${key}-uid`,
      email: `${key}@example.com`,
      ...mock
    });
  };

  return (
    <AuthContext.Provider value={{ currentUser, loading, login, loginAs, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function getDisplayRole(role?: string): string {
  if (!role) return "";
  const cleaned = role.trim().toUpperCase();
  if (cleaned === "APPROVER") return "PRODUCT LAUNCH MANAGER";
  if (cleaned === "CATALOGUE_ADMIN") return "CATALOGUE MANAGER";
  if (cleaned === "PLATFORM_ADMIN") return "PLATFORM ADMINISTRATOR";
  return role.replace("_", " ");
}
