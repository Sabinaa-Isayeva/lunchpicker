'use strict';
const client = window.lunchClient;
const $ = id => document.getElementById(id);
let me, teams = [], team = null, sessions = [], editingSession = null, defaults;
const roleNames = { owner: 'Komanda rəhbəri', member: 'Üzv', guest: 'Qonaq' };
const canManage = () => team && (me.is_staff || team.my_role === 'owner');
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function message(text, error = false) { $('message').hidden = false; $('message').textContent = text; $('message').style.color = error ? '#be123c' : '#047857'; }
function errorText(error) { return Object.values(error.data || { detail: error.message }).flat().join(' '); }
let pendingActions = 0;
async function run(action) {
    pendingActions++;
    $('workspace').inert = true;
    $('workspace').setAttribute('aria-busy', 'true');
    try { await action(); }
    catch (error) { message(errorText(error), true); if (error.status === 401) $('loginRequired').hidden = false; }
    finally {
        pendingActions--;
        if (!pendingActions) { $('workspace').inert = false; $('workspace').setAttribute('aria-busy', 'false'); }
    }
}
function formData(form) { return Object.fromEntries(new FormData(form)); }
function fill(form, values) { for (const element of form.elements) if (element.name && values[element.name] !== undefined) { if (element.type === 'checkbox') element.checked = Boolean(values[element.name]); else element.value = values[element.name]; } }
function button(text, handler, style = '') { const el = document.createElement('button'); el.type = 'button'; el.textContent = text; el.className = style; el.onclick = () => run(handler); return el; }
function row(container, text) { const el = document.createElement('div'); el.className = 'row'; const label = document.createElement('span'); label.textContent = text; el.append(label); container.append(el); return el; }
function dateTime(value) { return new Date(value).toLocaleString('az-AZ'); }
function localTime(value) { const d = new Date(value); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
function bindForm(id, action) { $(id).onsubmit = event => { event.preventDefault(); const submit = event.submitter; if (submit) submit.disabled = true; run(() => action(formData($(id)))).finally(() => { if (submit) submit.disabled = false; }); }; }
function tab(name) {
    if (name === 'system' && !me.is_staff) name = 'teams';
    document.querySelectorAll('[data-panel]').forEach(el => el.hidden = el.dataset.panel !== name);
    document.querySelectorAll('[data-tab]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.tab === name)));
    $('teamPicker').hidden = ['profile', 'system'].includes(name);
    history.replaceState(null, '', '#' + name);
    if (name === 'history') run(loadHistory);
    if (name === 'system') run(loadSystem);
}
async function loadTeams(selected) {
    teams = await client.all('/teams/');
    const stored = Number(selected || localStorage.getItem('active_team'));
    team = teams.find(t => t.id === stored) || teams[0] || null;
    $('teamSelect').innerHTML = teams.map(t => `<option value="${t.id}">${escape(t.name)}</option>`).join('') || '<option value="">Əvvəlcə komanda yaradın və ya dəvətlə qoşulun</option>';
    $('teamList').replaceChildren();
    if (!teams.length) $('teamList').textContent = 'Hələ komandanız yoxdur. Yeni komanda yaradın və ya dəvət linkini açın.';
    for (const item of teams) row($('teamList'), `${item.name} · ${item.member_count} üzv`).append(button('Seç', () => selectTeam(item.id), 'secondary'));
    await selectTeam(team?.id);
}
async function selectTeam(id) {
    team = teams.find(t => t.id === Number(id)) || null;
    if (team) { localStorage.setItem('active_team', team.id); $('teamSelect').value = team.id; }
    $('teamHeading').textContent = team?.name || 'Komanda seçin';
    for (const id of ['editTeamForm', 'inviteMemberForm', 'inviteManagement']) $(id).hidden = !canManage();
    $('newInviteWrap').hidden = true;
    $('sessionForm').hidden = !canManage(); $('sessionPermission').hidden = Boolean(canManage());
    $('members').replaceChildren(); $('inviteLinks').replaceChildren(); $('sessions').replaceChildren();
    if (team) {
        fill($('editTeamForm'), team);
        await loadMembers();
        if (canManage()) await loadInvites();
        await loadSessions();
    }
    resetSession();
    if (location.hash === '#history') await loadHistory();
}
async function loadMembers() {
    const members = await client.all(`/teams/${team.id}/members/`);
    $('members').replaceChildren();
    for (const member of members) {
        const el = row($('members'), `${member.username} · ${roleNames[member.role]}`);
        if (canManage() && member.user !== team.created_by) {
            const select = document.createElement('select'); select.style.width = 'auto'; select.setAttribute('aria-label', member.username + ' rolu');
            select.innerHTML = Object.entries(roleNames).map(([key, name]) => `<option value="${key}">${name}</option>`).join(''); select.value = member.role;
            el.append(select, button('Rol dəyiş', async () => { await client.request(`/teams/${team.id}/members/`, 'PATCH', { username: member.username, role: select.value }); await loadTeams(team.id); }), button('Sil', async () => {
                if (!confirm(`${member.username} komandadan çıxarılsın?`)) return;
                await client.request(`/teams/${team.id}/members/?username=${encodeURIComponent(member.username)}`, 'DELETE'); await loadTeams(team.id);
            }, 'danger'));
        }
    }
}
async function loadInvites() {
    const invites = await client.all(`/teams/${team.id}/invite_link/`);
    $('inviteLinks').replaceChildren();
    for (const invite of invites) {
        const active = invite.is_active && (!invite.expires_at || new Date(invite.expires_at) > new Date());
        const el = row($('inviteLinks'), active ? (invite.expires_at ? dateTime(invite.expires_at) : 'Müddətsiz') : 'Etibarsız');
        if (active) { const link = document.createElement('a'); link.href = invite.url; link.textContent = 'Linki aç'; link.className = 'underline'; el.append(link, button('Ləğv et', async () => { await client.request(`/teams/${team.id}/invite_links/${invite.token}/`, 'DELETE'); await loadInvites(); }, 'danger')); }
    }
}
async function loadSessions() {
    sessions = await client.all(`/sessions/?team=${team.id}`);
    $('sessions').replaceChildren();
    if (!sessions.length) $('sessions').textContent = 'Bu komandada sessiya yoxdur.';
    for (const session of sessions) {
        const el = row($('sessions'), `${session.title} · ${dateTime(session.start_time)} → ${dateTime(session.end_time)}`);
        const link = document.createElement('a'); link.href = `/?team=${team.id}&session=${session.id}`; link.className = 'button'; link.textContent = 'Səsverməyə bax'; el.append(link);
        if (canManage()) el.append(button('Düzəliş', () => { editingSession = session.id; fill($('sessionForm'), { ...session, start_time: localTime(session.start_time), end_time: localTime(session.end_time) }); $('saveSession').textContent = 'Dəyişiklikləri saxla'; $('sessionFormTitle').textContent = 'Sessiyaya düzəliş'; }), button('Klonla', async () => { await client.request(`/sessions/${session.id}/clone/`, 'POST', {}); await loadSessions(); }), button('Sil', async () => { if (confirm('Sessiya və onun səsləri silinsin?')) { await client.request(`/sessions/${session.id}/`, 'DELETE'); await loadSessions(); } }, 'danger'));
        if (new Date(session.end_time) <= new Date()) {
            try { const result = await client.request(`/sessions/${session.id}/result/`); row(el, `Seçildi: ${result.restaurant} (${result.method_display})`); }
            catch (error) { if (error.status !== 404) throw error; if (canManage()) el.append(button('Nəticəni seç', async () => { const result = await client.request(`/sessions/${session.id}/result/`, 'POST', {}); message('Seçildi: ' + result.restaurant); await loadSessions(); })); }
        }
    }
}
function resetSession() {
    editingSession = null; $('sessionForm').reset(); $('saveSession').textContent = 'Sessiya yarat'; $('sessionFormTitle').textContent = 'Sessiya yarat';
    const now = new Date(); fill($('sessionForm'), { start_time: localTime(now), end_time: localTime(new Date(now.getTime() + defaults.voting_deadline_minutes * 60000)), selection_algorithm: defaults.default_selection_algorithm, voting_mode: defaults.default_voting_mode });
    $('sessionForm').elements.is_anonymous.disabled = !defaults.allow_anonymous_voting;
}
async function loadHistory() {
    const form = formData($('historyForm')); const query = new URLSearchParams();
    for (const key of ['start', 'end', 'restaurant']) if (form[key]) query.set(key, form[key]);
    if (form.start && form.end && form.start > form.end) throw new Error('Son tarix başlanğıcdan əvvəl ola bilməz.');
    const path = form.scope === 'me' ? '/analytics/history/me/' : team ? `/analytics/history/team/${team.id}/` : null;
    $('history').replaceChildren(); $('analytics').replaceChildren();
    if (!path) { $('history').textContent = 'Komanda seçin.'; return; }
    const entries = await client.all(path + '?' + query);
    if (!entries.length) $('history').textContent = 'Seçilmiş filtrlər üzrə nəticə yoxdur.';
    for (const item of entries) row($('history'), `${dateTime(item.date)} · ${item.team_name} · ${item.session_title} · ${item.restaurant_name} · ${item.average_price} AZN`);
    if (team) {
        const statsQuery = new URLSearchParams(); for (const key of ['start', 'end']) if (form[key]) statsQuery.set(key, form[key]);
        const stats = await client.request(`/analytics/team/${team.id}/?${statsQuery}`);
        row($('analytics'), `${stats.total_sessions} sessiya · ${stats.closed_sessions_with_result} nəticə · orta ${stats.avg_votes_per_session} səs`);
        for (const item of stats.wins_by_restaurant) row($('analytics'), `${item.selected_proposal__restaurant__name}: ${item.wins} qələbə`);
        for (const item of stats.wins_by_cuisine) row($('analytics'), `${item.selected_proposal__restaurant__cuisine_type}: ${item.count}`);
        for (const item of stats.participation) row($('analytics'), `${item.voter__username}: ${item.votes_cast} səs (anonim sessiyalar daxil deyil)`);
    }
}
async function loadSystem() {
    const stats = await client.request('/analytics/system/'); $('systemMetrics').replaceChildren();
    const labels = { users: 'İstifadəçi', active_users: 'Aktiv istifadəçi', teams: 'Komanda', restaurants: 'Restoran', sessions: 'Sessiya', results: 'Nəticə', votes: 'Səs' };
    for (const [key, value] of Object.entries(stats)) row($('systemMetrics'), `${labels[key]}: ${value}`);
    defaults = await client.request('/settings/'); fill($('settingsForm'), defaults); await loadUsers();
}
async function loadUsers() {
    const users = await client.all('/users/?search=' + encodeURIComponent($('userSearch').value)); $('users').replaceChildren();
    for (const user of users) {
        const el = row($('users'), `${user.username} · ${user.email} · ${user.is_active ? 'Aktiv' : 'Deaktiv'}`);
        if (user.id !== me.id) el.append(button(user.is_staff ? 'Admin rolunu sil' : 'Admin et', async () => { if (confirm(`${user.username} üçün admin rolu dəyişdirilsin?`)) { await client.request(`/users/${user.id}/`, 'PATCH', { is_staff: !user.is_staff }); await loadUsers(); } }), button(user.is_active ? 'Deaktiv et' : 'Aktiv et', async () => { await client.request(`/users/${user.id}/`, 'PATCH', { is_active: !user.is_active }); await loadUsers(); }, 'secondary'));
    }
}
async function init() {
    try { me = await client.request('/users/me/'); defaults = await client.request('/settings/'); }
    catch (error) { $('loginRequired').hidden = false; message(errorText(error), true); return; }
    $('workspace').hidden = false; $('identity').textContent = [me.first_name, me.last_name].filter(Boolean).join(' ') || me.username;
    $('systemTab').hidden = !me.is_staff; $('foodLink').hidden = !me.is_staff; fill($('profileForm'), me);
    document.querySelectorAll('[data-tab]').forEach(el => el.onclick = () => tab(el.dataset.tab));
    $('teamSelect').onchange = () => run(() => selectTeam($('teamSelect').value));
    bindForm('createTeamForm', async data => { const created = await client.request('/teams/', 'POST', data); $('createTeamForm').reset(); await loadTeams(created.id); message('Komanda yaradıldı. İndi üzvləri dəvət edə bilərsiniz.'); });
    bindForm('editTeamForm', async data => { await client.request(`/teams/${team.id}/`, 'PATCH', data); await loadTeams(team.id); message('Komanda yeniləndi.'); });
    $('deleteTeam').onclick = () => run(async () => { if (confirm('Komanda, sessiyalar və tarixçə silinsin?')) { await client.request(`/teams/${team.id}/`, 'DELETE'); await loadTeams(); } });
    bindForm('joinForm', data => { const match = data.invite.trim().match(/(?:^|\/)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\/|$)/i); if (!match) throw new Error('Etibarlı dəvət linki və ya kodu daxil edin.'); location.href = '/join/' + match[1] + '/'; });
    bindForm('inviteMemberForm', async data => { await client.request(`/teams/${team.id}/members/`, 'POST', data); $('inviteMemberForm').reset(); await loadTeams(team.id); message('Üzv əlavə edildi.'); });
    bindForm('inviteLinkForm', async data => { const invite = await client.request(`/teams/${team.id}/invite_link/`, 'POST', { days: Number(data.days) }); $('newInvite').value = location.origin + invite.url; $('newInviteWrap').hidden = false; $('newInvite').select(); await loadInvites(); });
    bindForm('sessionForm', async data => { if (!canManage()) return; if (new Date(data.end_time) <= new Date(data.start_time)) throw new Error('Bitmə vaxtı başlama vaxtından sonra olmalıdır.'); const payload = { ...data, team_id: team.id, start_time: new Date(data.start_time).toISOString(), end_time: new Date(data.end_time).toISOString(), is_recurring: Boolean(data.recurrence_rule), is_anonymous: $('sessionForm').elements.is_anonymous.checked, is_announcement: $('sessionForm').elements.is_announcement.checked }; await client.request(editingSession ? `/sessions/${editingSession}/` : '/sessions/', editingSession ? 'PATCH' : 'POST', payload); resetSession(); await loadSessions(); message('Sessiya saxlanıldı.'); });
    $('cancelSessionEdit').onclick = resetSession;
    bindForm('historyForm', loadHistory);
    bindForm('profileForm', async data => { if (!data.password) delete data.password; me = await client.request(`/users/${me.id}/`, 'PATCH', data); localStorage.setItem('username', me.username); message('Profil yeniləndi.'); $('profileForm').elements.password.value = ''; });
    bindForm('settingsForm', async data => { defaults = await client.request('/settings/', 'PATCH', { ...data, voting_deadline_minutes: Number(data.voting_deadline_minutes), weighted_base_weight: Number(data.weighted_base_weight), allow_anonymous_voting: $('settingsForm').elements.allow_anonymous_voting.checked }); resetSession(); message('Standart qaydalar yeniləndi.'); });
    $('searchUsers').onclick = () => run(loadUsers);
    await loadTeams(new URLSearchParams(location.search).get('team'));
    const initialTab = location.hash.slice(1); tab(['teams', 'sessions', 'history', 'profile', 'system'].includes(initialTab) ? initialTab : 'teams');
}
window.addEventListener('DOMContentLoaded', () => run(init));
