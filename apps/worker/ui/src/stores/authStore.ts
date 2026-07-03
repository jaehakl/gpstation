/*
 * 이 파일은 Zustand 관련 인증 상태 저장소입니다.
 * - `src/api/api` 모듈을 호출합니다.
 * - 로그인 페이지와 보호 라우트에서 `refreshUser`를 호출해 인증 상태를 채웁니다.
 */

import { useEffect } from 'react';
import { create } from 'zustand';
import {
  dbTables,
  logout,
  startGoogleLogin,
} from '../api/api';
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
      const user = await dbTables.User.fetchMe();
      set({
        user,
        authReady: true,
      });
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
      set({
        user: null,
        authReady: true,
      });
    }
  },
}));

export function useBootstrapAuth() {
  const refreshUser = useAuthStore((state) => state.refreshUser);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);
}
