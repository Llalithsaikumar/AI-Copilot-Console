const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "" : null);

if (BASE_URL === null) {
  throw new Error("API base URL is not configured. Set VITE_API_BASE_URL in production.");
}

export const API_BASE = BASE_URL;

export function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
}

export async function fetchWithAuth(url, options = {}, getToken) {
  const token = await getToken();
  
  if (!token) {
    throw new Error("Authentication required - 401 Unauthorized");
  }

  const isFormData = options.body instanceof FormData;
  
  const headers = {
    ...(!isFormData && { "Content-Type": "application/json" }),
    ...(options.headers || {}),
    Authorization: `Bearer ${token}`
  };

  try {
    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error("Unauthorized - Token expired or invalid");
      }
      if (response.status === 403) {
        throw new Error("Forbidden - Session mismatch or access denied");
      }
      
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.message || errorData?.detail || `API Error: ${response.status}`);
    }

    return response;
  } catch (error) {
    console.error(`[API Error] ${url}:`, error);
    throw error;
  }
}
