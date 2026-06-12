import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API_BASE, timeout: 60000 });

let _logout = null;
export const setLogoutHandler = (fn) => { _logout = fn; };

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("manuelia_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && _logout) {
      try { _logout(); } catch (e) { /* noop */ }
    }
    return Promise.reject(err);
  }
);

export const setToken = (t) => {
  if (t) localStorage.setItem("manuelia_token", t);
  else localStorage.removeItem("manuelia_token");
};
