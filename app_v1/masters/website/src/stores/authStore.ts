import { useEffect } from 'react';
import { create } from 'zustand';

import { api, logout, startGoogleLogin } from '../api/api';
import type { UserData } from '../api/types';

type AuthStore = {
  user: UserData | null;
  authReady: boolean;
  refreshUser: () => Promise<UserData | null>;
  startLogin: () => void;
  logoutUser: () => Promise<void>;
};

let refreshUserPromise: Promise<UserData | null> | null = null;

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  authReady: false,

  refreshUser: async () => {
    if (refreshUserPromise) {
      return refreshUserPromise;
    }

    refreshUserPromise = (async () => {
      const user = await api.users.fetchMe();
      set({ user, authReady: true });
      return user;
    })().finally(() => {
      refreshUserPromise = null;
    });

    return refreshUserPromise;
  },

  startLogin: () => {
    startGoogleLogin();
  },

  logoutUser: async () => {
    try {
      await logout();
    } finally {
      set({ user: null, authReady: true });
    }
  },
}));

export function useBootstrapAuth() {
  const refreshUser = useAuthStore((state) => state.refreshUser);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);
}
