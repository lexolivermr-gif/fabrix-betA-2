import React, { useEffect } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useAuth } from "../lib/authStore";

export default function AppShell() {
  const user = useAuth((s) => s.user);
  const loading = useAuth((s) => s.loading);
  const navigate = useNavigate();
  const loc = useLocation();

  useEffect(() => {
    if (!loading && !user) {
      navigate(`/auth?next=${encodeURIComponent(loc.pathname)}`);
    }
  }, [user, loading, navigate, loc.pathname]);

  if (loading) {
    return (
      <div style={{ display:"flex", alignItems:"center", justifyContent:"center", minHeight: "100vh" }}>
        <div className="gen"><div className="spinner" /><div className="sub">Chargement…</div></div>
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="app">
      <div className="amb amb1" />
      <div className="amb amb2" />
      <Sidebar />
      <div className="main">
        <Outlet />
      </div>
    </div>
  );
}
