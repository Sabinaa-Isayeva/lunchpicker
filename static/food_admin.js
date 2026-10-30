const API = '/api';
let accessToken = localStorage.getItem('access');
let restaurants = [];
let selectedRestaurant = null;
let editingRestaurant = null, editingMenuItem = null, menuItems = [];

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

const cuisineLabels = { european: 'European', turkish: 'Türk', asian: 'Asiya', national: 'Milli' };

// ---------- Auth gate ----------
async function gate() {
    if (!accessToken) return deny('Daxil olunmayıb. Əsas səhifədən daxil olun.');
    try {
        const me = await api('/users/me/');
        if (!me.is_staff) return deny('Bu səhifə yalnız adminlər üçündür.');
        document.getElementById('gate').classList.add('hidden');
        document.getElementById('appScreen').classList.remove('hidden');
        loadRestaurants();
    } catch (_) {
        deny('Sessiya bitib. Əsas səhifədən yenidən daxil olun.');
    }
}

function deny(msg) {
    document.getElementById('gateMsg').textContent = msg;
    setTimeout(() => { window.location.href = '/'; }, 1800);
}

// ---------- Restaurants ----------
async function loadRestaurants() {
    try {
        restaurants = await window.lunchClient.all('/restaurants/');
        selectedRestaurant = null;
        renderRestaurantList();
        showMenuPlaceholder();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

function renderRestaurantList() {
    document.getElementById('restCount').innerText = restaurants.length + ' restoran';
    const list = document.getElementById('restaurantList');
    list.innerHTML = '';
    restaurants.forEach(r => {
        const row = document.createElement('div');
        row.className = 'flex items-center justify-between p-3 rounded-2xl border transition cursor-pointer ' +
            (selectedRestaurant === r.id
                ? 'bg-amber-50 border-amber-300'
                : 'bg-slate-50 border-slate-200 hover:border-amber-300');
        row.onclick = () => selectRestaurant(r.id);
        row.innerHTML = `
            <div class="min-w-0">
                <p class="text-xs font-bold text-slate-800 truncate">${escapeHtml(r.name)}</p>
                <p class="text-[10px] text-slate-400">${cuisineLabels[r.cuisine_type] || r.cuisine_type} &bull; ${Number(r.average_price).toFixed(2)} AZN &bull; ${(r.menu_items || []).length} yemək</p>
            </div>
            <button type="button" data-id="${r.id}" data-name="${escapeHtml(r.name)}" onclick="deleteRestaurant(event, this.dataset.id, this.dataset.name)" class="shrink-0 w-7 h-7 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-300 flex items-center justify-center" title="Sil">
                <i class="fa-solid fa-trash text-[10px]"></i>
            </button>`;
        list.appendChild(row);
        const edit = document.createElement('button'); edit.textContent = 'Düzəliş'; edit.className = 'text-xs px-2 text-amber-700';
        edit.onclick = event => { event.stopPropagation(); editRestaurant(r); }; row.append(edit);
    });
}

async function selectRestaurant(id) {
    selectedRestaurant = id;
    resetMenuForm();
    renderRestaurantList();
    document.getElementById('menuEmpty').classList.add('hidden');
    document.getElementById('menuSection').classList.remove('hidden');
    await loadMenuItems();
}

function showMenuPlaceholder() {
    document.getElementById('menuSection').classList.add('hidden');
    document.getElementById('menuEmpty').classList.remove('hidden');
    document.getElementById('menuTitle').innerText = 'Menyu';
    document.getElementById('menuCount').innerText = '';
}

async function createRestaurant() {
    const name = document.getElementById('nrName').value.trim();
    const price = parseFloat(document.getElementById('nrPrice').value || '0');
    if (!name) return showToast('Xəta', 'Restoran adı daxil edin.');
    try {
        await api(editingRestaurant ? `/restaurants/${editingRestaurant}/` : '/restaurants/', editingRestaurant ? 'PATCH' : 'POST', {
            name,
            cuisine_type: document.getElementById('nrCuisine').value,
            average_price: price,
            address: document.getElementById('nrAddress').value.trim(),
            website_url: document.getElementById('nrWebsite').value.trim(),
            rating: Number(document.getElementById('nrRating').value || 0),
        });
        showToast('Restoran yaradıldı!', name);
        document.getElementById('nrName').value = '';
        document.getElementById('nrPrice').value = '';
        document.getElementById('nrAddress').value = '';
        resetRestaurantForm();
        loadRestaurants();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

async function deleteRestaurant(event, id, name) {
    event.stopPropagation();
    if (!confirm(`"${name}" restoranını silmək istəyirsiniz?`)) return;
    try {
        await api(`/restaurants/${id}/`, 'DELETE');
        showToast('Silindi', name);
        loadRestaurants();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

// ---------- Menu items ----------
async function loadMenuItems() {
    if (!selectedRestaurant) return;
    try {
        const items = await window.lunchClient.all(`/restaurants/${selectedRestaurant}/menu-items/`);
        menuItems = items;
        const restaurant = restaurants.find(r => r.id === selectedRestaurant);
        document.getElementById('menuTitle').innerText = `Menyu — ${restaurant ? restaurant.name : ''}`;
        document.getElementById('menuCount').innerText = items.length + ' yemək';

        const list = document.getElementById('menuList');
        list.innerHTML = '';
        if (!items.length) {
            list.innerHTML = '<p class="text-xs font-semibold text-slate-400 text-center py-4">Bu restoranda hələ yemək yoxdur.</p>';
            return;
        }
        items.forEach(mi => {
            const row = document.createElement('div');
            row.className = 'flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200';
            row.innerHTML = `
                <div class="min-w-0">
                    <p class="text-xs font-bold text-slate-800 truncate">${escapeHtml(mi.name)} ${mi.is_vegetarian ? '<i class="fa-solid fa-leaf text-emerald-500 text-[9px]" title="Vegetarian"></i>' : ''}</p>
                    <p class="text-[10px] text-slate-400 truncate">${Number(mi.price).toFixed(2)} AZN${mi.description ? ' &bull; ' + escapeHtml(mi.description) : ''}</p>
                </div>
                <button type="button" data-id="${mi.id}" data-name="${escapeHtml(mi.name)}" onclick="deleteMenuItem(this.dataset.id, this.dataset.name)" class="shrink-0 w-7 h-7 rounded-lg bg-white border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-300 flex items-center justify-center" title="Sil">
                    <i class="fa-solid fa-trash text-[10px]"></i>
                </button>`;
            list.appendChild(row);
            const edit = document.createElement('button'); edit.textContent = 'Düzəliş'; edit.className = 'text-xs px-2 text-amber-700'; edit.onclick = () => editMenuItem(mi); row.append(edit);
        });
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

async function createMenuItem() {
    if (!selectedRestaurant) return showToast('Xəta', 'Əvvəlcə restoran seçin.');
    const name = document.getElementById('miName').value.trim();
    const price = parseFloat(document.getElementById('miPrice').value || '0');
    if (!name || price < 0) return showToast('Xəta', 'Ad və düzgün qiymət daxil edin.');
    try {
        await api(`/restaurants/${selectedRestaurant}/menu-items/${editingMenuItem ? editingMenuItem + '/' : ''}`, editingMenuItem ? 'PATCH' : 'POST', {
            name,
            price,
            is_vegetarian: document.getElementById('miVeg').checked,
            is_vegan: document.getElementById('miVegan').checked,
            is_gluten_free: document.getElementById('miGlutenFree').checked,
            description: document.getElementById('miDesc').value.trim(),
        });
        showToast('Yemək əlavə olundu!', `${name} bütün istifadəçilər üçün görünür.`);
        document.getElementById('miName').value = '';
        document.getElementById('miDesc').value = '';
        document.getElementById('miPrice').value = '';
        document.getElementById('miVeg').checked = false;
        resetMenuForm();
        await loadMenuItems();
        restaurants = await window.lunchClient.all('/restaurants/');
        renderRestaurantList();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

async function deleteMenuItem(id, name) {
    if (!confirm(`"${name}" yeməyini silmək istəyirsiniz?`)) return;
    try {
        await api(`/restaurants/${selectedRestaurant}/menu-items/${id}/`, 'DELETE');
        showToast('Silindi', name);
        loadMenuItems();
    } catch (e) {
        showToast('Xəta', formatApiError(e));
    }
}

window.addEventListener('DOMContentLoaded', gate);

function editRestaurant(restaurant) {
    editingRestaurant = restaurant.id;
    for (const [id, key] of Object.entries({ nrName: 'name', nrPrice: 'average_price', nrAddress: 'address', nrCuisine: 'cuisine_type', nrWebsite: 'website_url', nrRating: 'rating' })) document.getElementById(id).value = restaurant[key];
    document.getElementById('saveRestaurant').textContent = 'Dəyişiklikləri saxla';
    document.getElementById('nrName').scrollIntoView({ block: 'center' });
}
function resetRestaurantForm() {
    editingRestaurant = null;
    for (const id of ['nrName', 'nrPrice', 'nrAddress', 'nrWebsite', 'nrRating']) document.getElementById(id).value = '';
    document.getElementById('saveRestaurant').textContent = 'Restoran Yarat';
}
function editMenuItem(item) {
    editingMenuItem = item.id;
    for (const [id, key] of Object.entries({ miName: 'name', miPrice: 'price', miDesc: 'description' })) document.getElementById(id).value = item[key];
    for (const [id, key] of Object.entries({ miVeg: 'is_vegetarian', miVegan: 'is_vegan', miGlutenFree: 'is_gluten_free' })) document.getElementById(id).checked = item[key];
    document.getElementById('saveMenuItem').textContent = 'Dəyişiklikləri saxla';
}
function resetMenuForm() {
    editingMenuItem = null;
    for (const id of ['miName', 'miPrice', 'miDesc']) document.getElementById(id).value = '';
    for (const id of ['miVeg', 'miVegan', 'miGlutenFree']) document.getElementById(id).checked = false;
    document.getElementById('saveMenuItem').textContent = 'Menyuya Əlavə Et';
}
