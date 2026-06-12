import React from "react";
import { useToasts } from "../lib/toastStore";

export default function ToastHost() {
  const toasts = useToasts((s) => s.toasts);
  const remove = useToasts((s) => s.remove);
  return (
    <div className="toast-area" data-testid="toast-host">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`toast ${t.kind}`}
          data-testid="toast"
          onClick={() => remove(t.id)}
        >
          {t.msg}
        </div>
      ))}
    </div>
  );
}
