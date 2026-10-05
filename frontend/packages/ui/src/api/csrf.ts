/**
 * Reads the CSRF token from document.cookie (cookie name: eduneo_csrf).
 */
export function getCsrfToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const cookie of cookies) {
    const [name, ...valParts] = cookie.split("=");
    if (name.trim() === "eduneo_csrf") {
      return decodeURIComponent(valParts.join("="));
    }
  }
  return null;
}
