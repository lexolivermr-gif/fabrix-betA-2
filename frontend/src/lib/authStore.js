import { create } from "zustand";
import { api, setToken } from "./apiClient";

export const useAuth = create((set, get) => ({
  user: null,
  loading: true,

  bootstrap: async () => {
    const token = localStorage.getItem("manuelia_token");
    if (!token) { set({ loading: false, user: null }); return; }
    try {
      const { data } = await api.get("/auth/me");
      set({ user: data, loading: false });
    } catch {
      setToken(null);
      set({ user: null, loading: false });
    }
  },

  signup: async (email, password, name) => {
    const { data } = await api.post("/auth/signup", { email, password, name });
    setToken(data.access_token);
    set({ user: data.user });
    return data.user;
  },

  login: async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.access_token);
    set({ user: data.user });
    return data.user;
  },

  logout: () => {
    setToken(null);
    set({ user: null });
  },

  refresh: async () => {
    try {
      const { data } = await api.get("/auth/me");
      set({ user: data });
      return data;
    } catch { /* ignore */ }
  },

  updatePrefs: async (payload) => {
    const { data } = await api.patch("/auth/me", payload);
    set({ user: data });
    return data;
  },
}));
