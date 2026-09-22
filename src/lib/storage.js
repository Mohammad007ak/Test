import { createEmptyState } from "./fund.js";

const KEY = "sandogh:v1";

export function loadState() {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // Storage can be unavailable (private mode) or hold broken data.
  }
  return createEmptyState();
}

export function saveState(state) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Nothing else we can do; the export button still works.
  }
}

export function isValidState(value) {
  return (
    value &&
    typeof value === "object" &&
    Array.isArray(value.members) &&
    Array.isArray(value.payments) &&
    Array.isArray(value.loans)
  );
}
