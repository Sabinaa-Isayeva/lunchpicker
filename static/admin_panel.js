const API = '/api';
let accessToken = localStorage.getItem('access');
let tickets = [];
let activeStatus = 'pending';

async function api(path, method = 'GET', body = null) { return window.lunchClient.request(path, method, body); }

function paginated(json) { return json.results !== undefined ? json.results : json; }

function showToast(title, message) {
    document.getElementById('toast-title').innerText = title;
    document.getElementById('toast-msg').innerText = message;
    const toast = document.getElementById('toast');
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function formatApiError(e) {
    if (e.data) {
        for (const key in e.data) {
            const v = e.data[key];
            return Array.isArray(v) ? v.join(' ') : String(v);
        }
    }
    return 'Xəta baş verdi.';
}

function escapeHtml(s) {
    return window.LunchAPI.escapeHTML(s);
}

function fmtDate(iso) {
    return new Date(iso).toLocaleString('az-AZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

// ---------- Auth gate ----------
async function gate() {
    if (!accessToken) return deny('Daxil olunmayıb. Əsas səhifədən daxil olun.');
    try {
        const me = await api('/users/me/');
        const teams = await window.lunchClient.all('/teams/');
        if (!me.is_staff && !teams.some(t => t.my_role === 'owner')) return deny('Komanda rəhbəri icazəsi tələb olunur.');
        document.getElementById('gate').classList.add('hidden');
        document.getElementById('appScreen').classList.remove('hidden');
        loadTickets();
    } catch (_) {
        deny('Sessiya bitib. Əsas səhifədən yenidən daxil olun.');
    }
}

function deny(msg) {
    document.getElementById('gateMsg').textContent = msg;
    setTimeout(() => { window.location.href = '/'; }, 1800);
}

// ---------- Tickets ----------
async function loadTickets() {
    try {
        tickets = await window.lunchClient.all('/suggestions/');
        renderStats();
        renderTickets();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

function renderStats() {
    document.getElementById('statPending').innerText = tickets.filter(t => t.status === 'pending').length;
    document.getElementById('statApproved').innerText = tickets.filter(t => t.status === 'approved').length;
    document.getElementById('statRejected').innerText = tickets.filter(t => t.status === 'rejected').length;
}

function setStatus(status, btn) {
    activeStatus = status;
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.className = 'tab-btn px-3 py-1.5 rounded-lg text-slate-600 whitespace-nowrap';
    });
    btn.className = 'tab-btn px-3 py-1.5 rounded-lg bg-slate-900 text-white whitespace-nowrap';
    renderTickets();
}

function statusBadge(status) {
    const map = {
        pending: ['Gözləyir', 'bg-amber-50 text-amber-700 border-amber-200'],
        approved: ['Təsdiqlənib', 'bg-emerald-50 text-emerald-700 border-emerald-200'],
        rejected: ['Rədd edilib', 'bg-rose-50 text-rose-600 border-rose-200'],
    };
    const [label, cls] = map[status] || [status, 'bg-slate-50 text-slate-600 border-slate-200'];
    return `<span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md border ${cls}">${label}</span>`;
}

function renderTickets() {
    const list = document.getElementById('ticketList');
    const visible = activeStatus === 'all' ? tickets : tickets.filter(t => t.status === activeStatus);

    if (!visible.length) {
        list.innerHTML = '<div class="glass-card rounded-3xl p-8 text-center text-xs font-semibold text-slate-400">Bu statusda ticket yoxdur.</div>';
        return;
    }

    list.innerHTML = '';
    visible.forEach(t => {
        const items = (t.menu_items_detail || []).map(mi => escapeHtml(mi.name)).join(', ');
        const card = document.createElement('div');
        card.className = 'glass-card rounded-3xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4' +
            (t.status === 'pending' ? ' border-l-4 border-l-amber-400' : '');
        card.innerHTML = `
            <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                    <p class="text-sm font-bold text-slate-900">${escapeHtml(t.restaurant_name)}</p>
                    ${statusBadge(t.status)}
                </div>
                <p class="text-[11px] text-slate-500 mt-1">
                    <i class="fa-solid fa-user text-slate-400 mr-1"></i>@${escapeHtml(t.username)}
                    &bull; <i class="fa-solid fa-calendar text-slate-400 mr-1"></i>${escapeHtml(t.session_title || '—')}
                    &bull; <i class="fa-solid fa-clock text-slate-400 mr-1"></i>${fmtDate(t.created_at)}
                </p>
                ${items ? `<p class="text-[11px] text-slate-500 mt-1"><i class="fa-solid fa-bowl-food text-slate-400 mr-1"></i>${items}</p>` : ''}
                ${t.note ? `<p class="text-[11px] text-slate-600 mt-1 italic">"${escapeHtml(t.note)}"</p>` : ''}
                ${t.admin_note ? `<p class="text-[10px] font-bold text-rose-500 mt-1">Admin qeydi: ${escapeHtml(t.admin_note)}</p>` : ''}
            </div>
            <div class="flex items-center gap-2 shrink-0">
                ${t.status === 'pending' ? `
                    <button type="button" onclick="decide(${t.id}, true)" class="interactive-btn text-[11px] font-extrabold px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white flex items-center gap-1.5">
                        <i class="fa-solid fa-check"></i> Təsdiqlə
                    </button>
                    <button type="button" onclick="decide(${t.id}, false)" class="interactive-btn text-[11px] font-extrabold px-4 py-2 rounded-xl bg-white border border-rose-300 text-rose-600 hover:bg-rose-50 flex items-center gap-1.5">
                        <i class="fa-solid fa-xmark"></i> Rədd Et
                    </button>` : ''}
            </div>`;
        list.appendChild(card);
    });
}

async function decide(id, approve) {
    let body = {};
    if (!approve) {
        const reason = prompt('Rədd səbəbi (isteğe bağlı):');
        if (reason === null) return;
        body = { admin_note: reason };
    }
    try {
        await api(`/suggestions/${id}/${approve ? 'approve' : 'reject'}/`, 'POST', body);
        showToast(approve ? 'Təsdiqləndi!' : 'Rədd edildi',
                  approve ? 'Təklif səsverməyə çıxarıldı.' : '');
        loadTickets();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

window.addEventListener('DOMContentLoaded', gate);
