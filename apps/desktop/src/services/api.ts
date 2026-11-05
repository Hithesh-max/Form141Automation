// Centralized authenticated API client for Form 141 Automation Platform

const TOKEN_KEY = 'form141_auth_token';
const USER_KEY = 'form141_auth_user';

export interface AuthUser {
  id: number;
  username: string;
  role: string;
}

export const getAuthToken = (): string | null => {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setAuthToken = (token: string, user?: AuthUser): void => {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    if (user) {
      sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    }
  } catch (err) {
    console.warn('Failed to persist auth token:', err);
  }
};

export const clearAuthToken = (): void => {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  } catch (err) {
    console.warn('Failed to clear auth token:', err);
  }
};

export const getStoredUser = (): AuthUser | null => {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const getApiBase = (): string => {
  return 'http://localhost:8001';
};

export const getWsUrl = (): string => {
  return 'ws://localhost:8001/api/ws';
};

export const API_BASE = getApiBase();
export const WS_URL = getWsUrl();

type OnUnauthorizedCallback = () => void;
let unauthorizedHandler: OnUnauthorizedCallback | null = null;

export const setUnauthorizedHandler = (cb: OnUnauthorizedCallback): void => {
  unauthorizedHandler = cb;
};

export const apiFetch = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
  const token = getAuthToken();

  const headers = new Headers(options.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Ensure JSON content-type if body is JSON string and header not set
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearAuthToken();
    if (unauthorizedHandler) {
      unauthorizedHandler();
    }
  }

  return res;
};
