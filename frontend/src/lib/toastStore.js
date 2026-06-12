import { create } from "zustand";

let idCounter = 0;

export const useToasts = create((set, get) => ({
  toasts: [],
  push: (msg, kind = "default", ttl = 3500) => {
    const id = ++idCounter;
    set({ toasts: [...get().toasts, { id, msg, kind }] });
    setTimeout(() => {
      set({ toasts: get().toasts.filter((t) => t.id !== id) });
    }, ttl);
    return id;
  },
  remove: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}));

export const toast = {
  success: (m) => useToasts.getState().push(m, "success"),
  error:   (m) => useToasts.getState().push(m, "error", 5000),
  warn:    (m) => useToasts.getState().push(m, "warning"),
  info:    (m) => useToasts.getState().push(m, "default"),
};
