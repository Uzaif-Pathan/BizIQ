import { useCallback, useEffect, useState } from 'react';
import { api, describeError, ApiError } from '../services/api';

// Loads the latest analysis of a business from the server and lets the page run a new one.
// Only businesses saved on the server (business.synced === true) can have analyses.
export function useLatestAnalysis(business) {
  const onServer = business.synced === true;
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(onServer);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');

  const explain = (e) =>
    e instanceof ApiError && e.status === 404
      ? 'The server no longer has this business (it may have restarted). Create it again with "Add business".'
      : describeError(e);

  useEffect(() => {
    if (!onServer) { setAnalysis(null); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const history = await api.listAnalyses(business.id); // newest first
        const latest = history[0];
        const full = latest ? await api.getAnalysis(latest.analysis_id) : null;
        if (!cancelled) { setAnalysis(full); setError(''); }
      } catch (e) {
        if (!cancelled) setError(explain(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [business.id, onServer]);

  const run = useCallback(async () => {
    setRunning(true);
    setError('');
    try {
      setAnalysis(await api.runAnalysis(business.id));
    } catch (e) {
      setError(explain(e));
    } finally {
      setRunning(false);
    }
  }, [business.id]);

  return { analysis, loading, running, error, run, onServer };
}
