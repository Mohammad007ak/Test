import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";

// Keeps a fund's ledger in sync with the server. Edits apply locally right
// away and are saved one at a time in the background; if the fund changed
// elsewhere (another tab or device), the server's copy wins.
export function useFundSync(fundId) {
  const [state, setState] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const current = useRef(null);
  const version = useRef(0);
  const dirty = useRef(false);
  const chain = useRef(Promise.resolve());

  const applyServer = useCallback((data, serverVersion) => {
    current.current = data;
    version.current = serverVersion;
    dirty.current = false;
    setState(data);
  }, []);

  useEffect(() => {
    let cancelled = false;
    api("GET", `/api/funds/${fundId}`)
      .then(({ data, version: v }) => {
        if (cancelled) return;
        applyServer(data, v);
        setStatus("saved");
      })
      .catch((e) => !cancelled && setError(e));
    return () => {
      cancelled = true;
    };
  }, [fundId, applyServer]);

  const saveIfDirty = useCallback(async () => {
    if (!dirty.current) return;
    dirty.current = false;
    setStatus("saving");
    try {
      const result = await api("PUT", `/api/funds/${fundId}`, { data: current.current, version: version.current });
      version.current = result.version;
      setStatus(dirty.current ? "saving" : "saved");
    } catch (e) {
      if (e.status === 409) {
        applyServer(e.body.data, e.body.version);
        setStatus("saved");
        alert("این صندوق در دستگاه دیگری تغییر کرده بود. آخرین نسخه بارگذاری شد؛ لطفاً تغییر آخر را دوباره انجام دهید.");
      } else {
        dirty.current = true;
        setStatus("error");
      }
    }
  }, [fundId, applyServer]);

  const flush = useCallback(() => {
    chain.current = chain.current.then(saveIfDirty);
    return chain.current;
  }, [saveIfDirty]);

  const update = useCallback(
    (fn) => {
      current.current = fn(current.current);
      setState(current.current);
      dirty.current = true;
      flush();
    },
    [flush],
  );

  return { state, status, error, update, flush, applyServer };
}
