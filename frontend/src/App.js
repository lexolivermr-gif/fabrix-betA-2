import { useEffect } from "react";
import "@/App.css";
import "@/lib/i18n";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import { useAuth } from "@/lib/authStore";
import { setLogoutHandler } from "@/lib/apiClient";

import AppShell from "@/components/AppShell";
import ToastHost from "@/components/ToastHost";

import AuthPage from "@/pages/AuthPage";
import DashboardPage from "@/pages/DashboardPage";
import CreatePage from "@/pages/CreatePage";
import ManualViewerPage from "@/pages/ManualViewerPage";
import CreditsPage from "@/pages/CreditsPage";
import SettingsPage from "@/pages/SettingsPage";
import PublicSharePage from "@/pages/PublicSharePage";
import EngineerPage from "@/pages/EngineerPage";

function Bootstrapper({ children }) {
  const bootstrap = useAuth((s) => s.bootstrap);
  const logout = useAuth((s) => s.logout);
  useEffect(() => {
    setLogoutHandler(logout);
    bootstrap();
    document.title = "Fabrix";
  }, [bootstrap, logout]);
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Bootstrapper>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/share/:id" element={<PublicSharePage />} />
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/create" element={<CreatePage />} />
            <Route path="/manual/:id" element={<ManualViewerPage />} />
            <Route path="/credits" element={<CreditsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/engineer" element={<EngineerPage />} />
          </Route>
        </Routes>
      </Bootstrapper>
      <ToastHost />
    </BrowserRouter>
  );
}
