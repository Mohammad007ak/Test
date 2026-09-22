// Before the server existed, a fund lived only in this browser's storage.
// These helpers let a manager move that fund to their account once.

const LEGACY_KEY = "sandogh:v1";

export function loadLegacyState() {
  try {
    const state = JSON.parse(localStorage.getItem(LEGACY_KEY));
    return state?.fund ? state : null;
  } catch {
    return null;
  }
}

export function clearLegacyState() {
  try {
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // Nothing to clean up.
  }
}
