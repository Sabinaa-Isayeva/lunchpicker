const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function screen(tokens, request) {
    const elements = {};
    const document = { getElementById(id) {
        return elements[id] ||= { textContent: '', classList: {
            values: new Set(id === 'appScreen' ? ['hidden'] : []),
            add(v) { this.values.add(v); }, remove(v) { this.values.delete(v); },
        } };
    } };
    const context = vm.createContext({ document,
        localStorage: { getItem: key => tokens[key] || null },
        window: { lunchClient: { request, all: async () => [] }, addEventListener() {} },
    });
    vm.runInContext(fs.readFileSync('static/food_admin.js', 'utf8'), context);
    vm.runInContext('loadRestaurants = async () => {}', context);
    return { elements, document, gate: () => vm.runInContext('gate()', context) };
}
test('refresh-only session reaches the shared client and opens staff screen', async () => {
    let called = false;
    const page = screen({ refresh: 'valid' }, async () => { called = true; return { is_staff: true }; });
    await page.gate();
    assert.equal(called, true);
    assert.equal(page.elements.appScreen.classList.values.has('hidden'), false);
    assert.equal(page.elements.gate.classList.values.has('hidden'), true);
});
test('logged out, non-staff and expired sessions show a persistent access message', async () => {
    for (const [tokens, request] of [
        [{}, async () => { throw new Error('must not call'); }],
        [{ access: 'member' }, async () => ({ is_staff: false })],
        [{ access: 'expired' }, async () => { throw { status: 401 }; }],
    ]) {
        const page = screen(tokens, request);
        await page.gate();
        assert.ok(page.elements.gateMsg.textContent);
        assert.equal(page.elements.gate.classList.values.has('hidden'), false);
        assert.equal(page.elements.appScreen.classList.values.has('hidden'), true);
    }
});
