const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createClient, escapeHTML } = require('../../static/api.js');
function storage(values = {}) { return { getItem: key => values[key] || null, setItem: (key, value) => values[key] = value, removeItem: key => delete values[key] }; }
const response = (status, data) => ({ status, ok: status >= 200 && status < 300, json: async () => data });

test('user strings are escaped for text and quoted HTML attributes', () => {
    assert.equal(escapeHTML('<img src=x onerror="alert(1)" data-a=\'&\'>'), '&lt;img src=x onerror=&quot;alert(1)&quot; data-a=&#39;&amp;&#39;&gt;');
    assert.equal(escapeHTML(null), '');
});

test('refresh retries return parsed data and preserve the request body', async () => {
    const calls = [];
    const store = storage({ access: 'old', refresh: 'refresh' });
    const client = createClient(async (path, options) => {
        calls.push({ path, options });
        if (path.endsWith('/refresh/')) return response(200, { access: 'new' });
        return options.headers.Authorization === 'Bearer old' ? response(401, {}) : response(201, { id: 7 });
    }, store);
    assert.deepEqual(await client.request('/teams/', 'POST', { name: 'Crew' }), { id: 7 });
    assert.equal(calls[2].options.body, '{"name":"Crew"}');
    assert.equal(store.getItem('access'), 'new');
});
test('failed refresh clears expired credentials and rejects once', async () => {
    let calls = 0;
    const store = storage({ access: 'old', refresh: 'expired' });
    const client = createClient(async () => { calls++; return response(401, { detail: 'Expired' }); }, store);
    await assert.rejects(client.request('/users/me/'), error => error.status === 401);
    assert.equal(calls, 2); assert.equal(store.getItem('access'), null);
});
test('pagination loads every page and accepts bare arrays', async () => {
    const client = createClient(async path => path.includes('page=2') ? response(200, { results: [2], next: null }) : response(200, { results: [1], next: 'https://example.org/api/teams/?page=2' }), storage());
    assert.deepEqual(await client.all('/teams/'), [1, 2]);
    assert.deepEqual(await createClient(async () => response(200, [1]), storage()).all('/members/'), [1]);
});
test('empty success and validation errors have consistent return types', async () => {
    assert.equal(await createClient(async () => response(204), storage()).request('/item/', 'DELETE'), null);
    await assert.rejects(createClient(async () => response(400, { name: ['Required'] }), storage()).request('/teams/'), error => error.data.name[0] === 'Required');
});
