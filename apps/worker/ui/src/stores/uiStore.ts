/*
 * 이 파일은 Zustand 관련 상태 저장소입니다.
 */

import { create } from 'zustand';

type UiStore = {
  isMobileSidebarOpen: boolean;
  toggleMobileSidebar: () => void;
  setMobileSidebarOpen: (isOpen: boolean) => void;
};

export const useUiStore = create<UiStore>((set) => ({
  isMobileSidebarOpen: false,
  toggleMobileSidebar: () =>
    set((state) => ({
      isMobileSidebarOpen: !state.isMobileSidebarOpen,
    })),
  setMobileSidebarOpen: (isOpen) => set({ isMobileSidebarOpen: isOpen }),
}));
