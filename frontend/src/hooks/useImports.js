import { useCallback, useEffect, useState } from 'react';
import { api, describeError, ApiError } from '../services/api';
import { hasUsableImport } from '../utils/imports';

// Loads the data imports of a business from the server and uploads new files.
// Only businesses saved on the server (business.synced === true) have imports.
// `business.hasData` follows the server: true only while at least one import was validated and stored.
// If the server does not know the business (404, for example after a restart), the business is marked
// as not saved on the server, the same way useLatestAnalysis does.
export function useImports(business, setState) {
  const onServer = business.synced === true;
  const [imports, setImports] = useState([]);
  const [loading, setLoading] = useState(onServer);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const markUnsynced = useCallback(() => {
    setState?.((s) => ({
      ...s,
      businesses: s.businesses.map((b) => (b.id === business.id ? { ...b, synced: false } : b)),
    }));
  }, [business.id, setState]);

  // Keep the local "has data" flag equal to what the server really holds.
  const syncHasData = useCallback((list) => {
    const usable = hasUsableImport(list);
    setState?.((s) => {
      const current = s.businesses.find((b) => b.id === business.id);
      if (!current || !!current.hasData === usable) return s;
      return {
        ...s,
        businesses: s.businesses.map((b) =>
          b.id === business.id ? { ...b, hasData: usable, level: usable ? 'Standard Data' : b.level } : b,
        ),
      };
    });
  }, [business.id, setState]);

  const load = useCallback(async () => {
    if (!onServer) { setImports([]); setLoading(false); return; }
    setLoading(true);
    try {
      const list = await api.listImports(business.id); // newest first
      setImports(list);
      setError('');
      syncHasData(list);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) markUnsynced();
      else setError(describeError(e));
    } finally {
      setLoading(false);
    }
  }, [business.id, onServer, markUnsynced, syncHasData]);

  useEffect(() => { load(); }, [load]);

  // Sends one CSV. Resolves with the import record; throws ApiError (shown by the caller) when the file is rejected.
  const upload = useCallback(async (dataType, file) => {
    setUploading(true);
    try {
      const item = await api.uploadImport(business.id, dataType, file);
      const list = [item, ...imports.filter((i) => i.id !== item.id)];
      setImports(list);
      setError('');
      syncHasData(list);
      return item;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) markUnsynced();
      throw e;
    } finally {
      setUploading(false);
    }
  }, [business.id, imports, markUnsynced, syncHasData]);

  return { imports, loading, uploading, error, reload: load, upload };
}
