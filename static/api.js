/* Shared JWT client for every screen; no build step required. */
(function (root) {
    function escapeHTML(value) {
        return String(value ?? '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[c]));
    }
    function createClient(fetcher, storage) {
        let refreshing = null;
        async function request(path, method = 'GET', body = null, retried = false) {
            const headers = { 'Content-Type': 'application/json' };
            const token = storage.getItem('access');
            if (token) headers.Authorization = 'Bearer ' + token;
            const response = await fetcher('/api' + path, {
                method, headers, body: body === null ? null : JSON.stringify(body),
            });
            if (response.status === 401 && !retried && storage.getItem('refresh')) {
                if (!refreshing) refreshing = (async () => {
                    const refreshed = await fetcher('/api/auth/token/refresh/', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ refresh: storage.getItem('refresh') }),
                    });
                    if (!refreshed.ok) {
                        storage.removeItem('access'); storage.removeItem('refresh');
                        return false;
                    }
                    storage.setItem('access', (await refreshed.json()).access);
                    return true;
                })();
                let ok;
                try { ok = await refreshing; } finally { refreshing = null; }
                if (ok) return request(path, method, body, true);
            }
            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: response.statusText }));
                throw Object.assign(new Error('API error'), { status: response.status, data });
            }
            return response.status === 204 ? null : response.json();
        }
        async function all(path) {
            const items = [];
            let next = path;
            while (next) {
                const page = await request(next);
                if (Array.isArray(page)) return items.concat(page);
                items.push(...page.results);
                if (page.next) {
                    const url = new URL(page.next, 'http://localhost');
                    if (!url.pathname.startsWith('/api/')) throw new Error('Invalid pagination URL');
                    next = url.pathname.slice(4) + url.search;
                } else next = null;
            }
            return items;
        }
        return { request, all };
    }
    const exported = { createClient, escapeHTML };
    if (typeof module !== 'undefined' && module.exports) module.exports = exported;
    else { root.LunchAPI = exported; root.lunchClient = createClient(root.fetch.bind(root), root.localStorage); }
})(typeof window !== 'undefined' ? window : globalThis);
