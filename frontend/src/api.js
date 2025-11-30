const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function runAgent(payload) {
  const response = await fetch(`${API_BASE}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Failed to reach agent.";
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (err) {
      // ignore parse error
    }
    throw new Error(detail);
  }

  return response.json();
}

export const apiBase = API_BASE;
