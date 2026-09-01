function filterCategory(cat, btn) {
    // 1. Aktiv düymə stilini dəyişmək
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.className = "filter-btn text-xs font-bold px-4 py-2 rounded-xl bg-white text-slate-600 hover:text-slate-900 border border-slate-200 interactive-btn shrink-0";
    });
    btn.className = "filter-btn text-xs font-bold px-4 py-2 rounded-xl bg-slate-900 text-white shadow-sm border border-slate-800 interactive-btn shrink-0";

    // 2. Kartları filtrləmək
    document.querySelectorAll('.proposal-card').forEach(card => {
        if (cat === 'all' || card.classList.contains(cat)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}