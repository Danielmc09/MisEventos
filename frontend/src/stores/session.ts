import { create } from "zustand";

interface SessionState {
  accessToken: string | null;
  setToken: (token: string) => void;
  clear: () => void;
}

export const useSession = create<SessionState>((set) => ({
  accessToken: null,
  setToken: (accessToken) => set({ accessToken }),
  clear: () => set({ accessToken: null }),
}));
