// ============================================================
// aniprotech - app.js (Production)
// ============================================================

// --- Toast Notifications ---
function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    const icons = { success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>', error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>', warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>', info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>' };
    toast.innerHTML = '<span class="toast-icon">' + (icons[type] || icons.info) + '</span><span class="toast-message">' + message + '</span><button class="toast-close" onclick="this.parentElement.remove()">&times;</button>';
    container.appendChild(toast);
    requestAnimationFrame(function() { toast.classList.add('toast-show'); });
    setTimeout(function() { toast.classList.remove('toast-show'); setTimeout(function() { toast.remove(); }, 300); }, 5000);
}

// --- Mobile Menu ---
function toggleMobileMenu() {
    var nav = document.getElementById('main-nav');
    var overlay = document.getElementById('mobile-overlay');
    nav.classList.toggle('mobile-open');
    overlay.classList.toggle('active');
    document.body.classList.toggle('no-scroll');
}
window.toggleMobileMenu = toggleMobileMenu;

// --- View Switcher ---
function showView(viewId) {
    document.querySelectorAll('.view-section').forEach(function(el) {
        el.classList.remove('active');
        el.style.display = 'none';
    });
    var target = document.getElementById(viewId);
    if (target) {
        target.classList.add('active');
        target.style.display = 'block';
    }
    document.querySelectorAll('.nav-item').forEach(function(el) { el.classList.remove('active'); });
    var navMap = {
        'dashboard-view': 'nav-dashboard',
        'invoices-view': 'nav-invoices',
        'create-invoice-view': 'nav-invoices',
        'view-invoice-view': 'nav-invoices',
        'bills-view': 'nav-bills',
        'reports-view': 'nav-reports',
        'contacts-view': 'nav-contacts',
        'employees-view': 'nav-people',
        'employee-detail-view': 'nav-people',
        'departments-view': 'nav-people',
        'attendance-view': 'nav-people',
        'onboarding-hub-view': 'nav-onboarding',
        'recruitment-view': 'nav-recruitment',
        'payroll-view': 'nav-payroll',
        'payslip-detail-view': 'nav-payroll',
        'orgchart-view': 'nav-org',
        'settings-view': 'nav-settings'
    };
    var navId = navMap[viewId];
    if (navId) { var navEl = document.getElementById(navId); if (navEl) navEl.classList.add('active'); }
    if (viewId === 'invoices-view' && typeof fetchInvoices === 'function') fetchInvoices();
    if (viewId === 'create-invoice-view' && typeof fetchNextInvoiceNumber === 'function') fetchNextInvoiceNumber();
    if (viewId === 'create-invoice-view' && typeof setupContactAutocomplete === 'function') setupContactAutocomplete();
    if (viewId === 'settings-view' && typeof loadGmailStatus === 'function') loadGmailStatus();
    if (viewId === 'settings-view' && typeof loadSettings === 'function') loadSettings();
    if (viewId === 'reports-view' && typeof loadReports === 'function') loadReports();
    // Close mobile menu
    document.getElementById('main-nav').classList.remove('mobile-open');
    document.getElementById('mobile-overlay').classList.remove('active');
    document.body.classList.remove('no-scroll');
}
window.showView = showView;

// --- Utility ---
var allInvoices = [];
var currentFilter = 'all';

function formatCurrency(amount, currency) {
    currency = currency || 'USD';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency }).format(amount || 0);
}

// --- Auth ---
async function checkAuthStatus() {
    var loginBtn = document.getElementById('login-btn');
    var userInfo = document.getElementById('user-info');
    try {
        var res = await fetch('/api/auth/me');
        var data = await res.json();
        if (data.user) {
            if (loginBtn) loginBtn.style.display = 'none';
            if (userInfo) {
                userInfo.style.display = 'flex';
                var name = data.user.name || data.user.email;
                var avatar = document.getElementById('user-avatar');
                if (avatar) { avatar.textContent = name[0].toUpperCase(); avatar.title = name; }
            }
        } else {
            if (loginBtn) loginBtn.style.display = 'inline-block';
            if (userInfo) userInfo.style.display = 'none';
        }
    } catch (e) {
        console.error("Auth check failed", e);
        if (loginBtn) loginBtn.style.display = 'inline-block';
        if (userInfo) userInfo.style.display = 'none';
    }
}

function handleLogout() {
    window.location.href = '/api/auth/logout';
}
window.handleLogout = handleLogout;

// --- Dashboard ---
async function fetchDashboardData() {
    try {
        var response = await fetch('/api/dashboard-summary');
        if (!response.ok) {
            var container = document.getElementById('cash-flow-container');
            if (container) container.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:40px;"><a href="/api/auth/login" style="color:var(--accent-cyan);">Sign in</a> to view dashboard</div>';
            return;
        }
        renderDashboard(await response.json());
    } catch (error) {
        console.error('Dashboard load failed:', error);
        var container2 = document.getElementById('cash-flow-container');
        if (container2) container2.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:40px;">Failed to load</div>';
    }
}

function renderDashboard(data) {
    var s = data.summary || {};
    document.getElementById('dash-total-invoiced').textContent = formatCurrency(s.total_invoiced);
    document.getElementById('dash-total-revenue').textContent = formatCurrency(s.total_revenue);
    document.getElementById('dash-invoices-owed').textContent = formatCurrency(s.invoices_owed);
    document.getElementById('dash-total-count').textContent = s.total_count || 0;
    document.getElementById('dash-paid-count').textContent = s.paid_count || 0;
    document.getElementById('dash-pending-count').textContent = s.pending_count || 0;
    document.getElementById('dash-draft-count').textContent = s.draft_count || 0;
    renderCashFlowChart(data.cash_flow);
}

function renderCashFlowChart(cashFlowData) {
    var container = document.getElementById('cash-flow-container');
    if (!container) return;
    var maxTotal = Math.max.apply(null, cashFlowData.money_in.concat(cashFlowData.money_out));
    var html = '<div class="chart-bars">';
    for (var i = 0; i < cashFlowData.months.length; i++) {
        var hIn = (cashFlowData.money_in[i] / maxTotal) * 100;
        var hOut = (cashFlowData.money_out[i] / maxTotal) * 100;
        html += '<div class="chart-month"><div class="bar-group"><div class="bar in" style="height:' + hIn + '%" title="In: ' + formatCurrency(cashFlowData.money_in[i]) + '"></div><div class="bar out" style="height:' + hOut + '%" title="Out: ' + formatCurrency(cashFlowData.money_out[i]) + '"></div></div><span class="month-label">' + cashFlowData.months[i] + '</span></div>';
    }
    html += '</div><div class="chart-legend"><div class="legend-item"><div class="legend-color in"></div><span>Money in</span></div><div class="legend-item"><div class="legend-color out"></div><span>Money out</span></div></div>';
    container.innerHTML = html;
}

// --- Invoices ---
async function fetchInvoices() {
    try {
        var response = await fetch('/api/invoices');
        if (!response.ok) throw new Error('Failed');
        allInvoices = await response.json();
        renderInvoices(allInvoices);
    } catch (error) {
        var tbody = document.getElementById('invoices-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="loading">Failed to load invoices.</td></tr>';
    }
}
window.fetchInvoices = fetchInvoices;

function renderInvoices(invoices) {
    var tbody = document.getElementById('invoices-table-body');
    var countSpan = document.getElementById('invoice-count');
    if (countSpan) countSpan.textContent = invoices.length + ' item' + (invoices.length !== 1 ? 's' : '');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (invoices.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-secondary);">No invoices found.</td></tr>';
        return;
    }
    invoices.forEach(function(inv) {
        var statusClass = (inv.status || '').toLowerCase().replace(/\s+/g, '-');
        var opens = inv.open_count || 0;
        var openBadge = opens > 0 ? '<span style="color:var(--primary-color);font-weight:600;">' + opens + '</span>' : '<span style="color:var(--text-secondary);">0</span>';
        tbody.insertAdjacentHTML('beforeend', '<tr><td><a href="#" class="link" onclick="event.preventDefault();viewInvoice(\'' + inv.number + '\')">' + inv.number + '</a></td><td>' + (inv.ref || '-') + '</td><td>' + inv.to + '</td><td>' + inv.date + '</td><td>' + inv.due_date + '</td><td class="text-right">' + formatCurrency(inv.paid) + '</td><td class="text-right">' + formatCurrency(inv.due) + '</td><td><span class="status-pill status-' + statusClass + '">' + inv.status + '</span></td><td class="text-right">' + openBadge + '</td><td>' + (inv.sent || '-') + '</td></tr>');
    });
}

function filterInvoices(status, btn) {
    currentFilter = status;
    document.querySelectorAll('.invoices-tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    var filtered = status === 'all' ? allInvoices : allInvoices.filter(function(inv) { return (inv.status || '').toLowerCase() === status; });
    renderInvoices(filtered);
}
window.filterInvoices = filterInvoices;

function searchInvoices() {
    var q = (document.getElementById('invoice-search').value || '').toLowerCase();
    var filtered = allInvoices.filter(function(inv) {
        return (inv.number || '').toLowerCase().indexOf(q) >= 0 || (inv.to || '').toLowerCase().indexOf(q) >= 0 || (inv.ref || '').toLowerCase().indexOf(q) >= 0 || (inv.email || '').toLowerCase().indexOf(q) >= 0;
    });
    renderInvoices(filtered);
}
window.searchInvoices = searchInvoices;

var searchDebounce = null;
function handleGlobalSearch(e) {
    clearTimeout(searchDebounce);
    var q = e.target.value.trim().toLowerCase();
    if (e.key === 'Enter') {
        if (!q) return;
        runGlobalSearch(q);
        return;
    }
    searchDebounce = setTimeout(function() {
        if (q.length >= 2) runGlobalSearch(q);
        else hideSearchResults();
    }, 300);
}

function runGlobalSearch(q) {
    var results = [];
    allInvoices.forEach(function(inv) {
        var text = (inv.number + ' ' + (inv.client_name || '') + ' ' + (inv.client_email || '') + ' ' + (inv.status || '')).toLowerCase();
        if (text.includes(q)) results.push({ type: 'invoice', label: inv.number + ' — ' + (inv.client_name || 'No client'), status: inv.status, view: 'invoices-view' });
    });
    if (typeof allContacts !== 'undefined') {
        allContacts.forEach(function(c) {
            var text = ((c.name || '') + ' ' + (c.email || '') + ' ' + (c.phone || '')).toLowerCase();
            if (text.includes(q)) results.push({ type: 'contact', label: (c.name || c.email || 'Unknown'), sub: c.email || '', view: 'contacts-view' });
        });
    }
    if (typeof allEmployees !== 'undefined') {
        allEmployees.forEach(function(emp) {
            var text = ((emp.first_name || '') + ' ' + (emp.last_name || '') + ' ' + (emp.email || '') + ' ' + (emp.job_title || '') + ' ' + (emp.department || '')).toLowerCase();
            if (text.includes(q)) results.push({ type: 'employee', label: (emp.first_name + ' ' + emp.last_name).trim(), sub: emp.email || emp.job_title || '', view: 'employees-view' });
        });
    }
    if (typeof allPayslips !== 'undefined') {
        allPayslips.forEach(function(ps) {
            var text = ((ps.employee_name || '') + ' ' + (ps.period || '') + ' ' + (ps.status || '')).toLowerCase();
            if (text.includes(q)) results.push({ type: 'payslip', label: (ps.employee_name || 'Unknown') + ' — ' + (ps.period || ''), sub: ps.status || '', view: 'payroll-view' });
        });
    }
    showSearchResults(results, q);
}

function showSearchResults(results, q) {
    hideSearchResults();
    var bar = document.querySelector('.search-bar');
    if (!bar) return;
    var dropdown = document.createElement('div');
    dropdown.id = 'search-results-dropdown';
    dropdown.style.cssText = 'position:absolute;top:100%;left:0;right:0;margin-top:4px;background:rgba(17,24,39,0.98);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.12);border-radius:12px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.5);';
    if (results.length === 0) {
        dropdown.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);font-size:0.85rem;">No results for "' + esc(q) + '"</div>';
    } else {
        var types = { invoice: 'Invoices', contact: 'Contacts', employee: 'People', payslip: 'Payroll' };
        var icons = { invoice: '&#128196;', contact: '&#128100;', employee: '&#128101;', payslip: '&#128176;' };
        var grouped = {};
        results.forEach(function(r) {
            if (!grouped[r.type]) grouped[r.type] = [];
            grouped[r.type].push(r);
        });
        var html = '';
        for (var type in grouped) {
            html += '<div style="padding:8px 14px 4px;font-size:0.72rem;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;">' + (types[type] || type) + '</div>';
            grouped[type].slice(0, 5).forEach(function(r) {
                var highlight = esc(r.label).replace(new RegExp('(' + esc(q) + ')', 'gi'), '<strong style="color:var(--primary-color);">$1</strong>');
                html += '<div class="search-result-item" onclick="handleSearchResultClick(\'' + r.view + '\')" style="padding:8px 14px;cursor:pointer;display:flex;align-items:center;gap:10px;transition:background 0.15s;">' +
                    '<span style="font-size:1rem;">' + (icons[r.type] || '&#128269;') + '</span>' +
                    '<div style="min-width:0;">' +
                        '<div style="font-size:0.85rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + highlight + '</div>' +
                        (r.sub ? '<div style="font-size:0.75rem;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + esc(r.sub) + '</div>' : '') +
                    '</div>' +
                    (r.status ? '<span style="margin-left:auto;font-size:0.7rem;padding:2px 6px;border-radius:8px;background:rgba(255,255,255,0.08);color:var(--text-secondary);">' + esc(r.status) + '</span>' : '') +
                '</div>';
            });
        }
        dropdown.innerHTML = html;
    }
    bar.style.position = 'relative';
    bar.appendChild(dropdown);
    var items = dropdown.querySelectorAll('.search-result-item');
    items.forEach(function(item) {
        item.addEventListener('mouseenter', function() { item.style.background = 'rgba(255,255,255,0.08)'; });
        item.addEventListener('mouseleave', function() { item.style.background = 'transparent'; });
    });
}

function hideSearchResults() {
    var existing = document.getElementById('search-results-dropdown');
    if (existing) existing.remove();
}

function handleSearchResultClick(view) {
    hideSearchResults();
    document.getElementById('global-search').value = '';
    showView(view);
}

document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-bar')) hideSearchResults();
});
window.handleGlobalSearch = handleGlobalSearch;
window.handleSearchResultClick = handleSearchResultClick;

async function fetchNextInvoiceNumber() {
    try {
        var response = await fetch('/api/next-invoice-number');
        if (response.ok) {
            var data = await response.json();
            var numInput = document.getElementById('inv-number');
            if (numInput && !numInput.value) numInput.value = data.next_number;
        }
    } catch (e) { console.error(e); }
}
window.fetchNextInvoiceNumber = fetchNextInvoiceNumber;

// --- Logo ---
function loadSavedLogo() {
    var savedLogo = localStorage.getItem('company_logo');
    if (savedLogo) {
        var el = document.getElementById('logo-img-create');
        if (el) { el.src = savedLogo; el.style.display = 'block'; }
        var txt = document.getElementById('logo-upload-text');
        if (txt) txt.style.display = 'none';
    }
    fetch('/api/client/logo').then(function(r) { return r.json(); }).then(function(data) {
        if (data.logo_url) {
            localStorage.setItem('company_logo', data.logo_url);
            var el = document.getElementById('logo-img-create');
            if (el) { el.src = data.logo_url; el.style.display = 'block'; }
            var txt = document.getElementById('logo-upload-text');
            if (txt) txt.style.display = 'none';
        }
    }).catch(function() {});
}

function setupLogoUpload() {
    var logoUpload = document.getElementById('logo-upload');
    if (logoUpload) {
        logoUpload.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (file) {
                var reader = new FileReader();
                reader.onload = function(event) {
                    var b64 = event.target.result;
                    localStorage.setItem('company_logo', b64);
                    fetch('/api/client/logo', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ logo_url: b64 })
                    }).catch(function() {});
                    var img = document.getElementById('logo-img-create');
                    if (img) { img.src = b64; img.style.display = 'block'; }
                    var txt = document.getElementById('logo-upload-text');
                    if (txt) txt.style.display = 'none';
                };
                reader.readAsDataURL(file);
            }
        });
    }
}

// --- View Invoice ---
async function viewInvoice(number) {
    try {
        var response = await fetch('/api/invoices/' + encodeURIComponent(number));
        if (!response.ok) throw new Error('Failed');
        var inv = await response.json();
        document.getElementById('view-inv-title').textContent = 'Invoice ' + inv.number;
        document.getElementById('view-inv-number-val').textContent = inv.number;
        document.getElementById('view-inv-status').textContent = inv.status;
        document.getElementById('view-inv-status').className = 'status-pill status-' + (inv.status || '').toLowerCase().replace(/\s+/g, '-');
        document.getElementById('view-inv-contact').textContent = inv.to;
        var emailD = document.getElementById('view-inv-email-display');
        if (emailD) emailD.textContent = inv.email || 'No email';
        var phoneD = document.getElementById('view-inv-phone-display');
        if (phoneD) phoneD.textContent = inv.phone_number || 'No phone';
        document.getElementById('view-inv-issue-date').textContent = inv.date;
        document.getElementById('view-inv-due-date').textContent = inv.due_date;
        var dueVal = document.getElementById('view-inv-due-val');
        if (dueVal) dueVal.textContent = (inv.due || 0).toFixed(2);

        var openTracking = document.getElementById('view-inv-open-tracking');
        var openCountEl = document.getElementById('view-inv-open-count');
        var lastOpenedEl = document.getElementById('view-inv-last-opened');
        if (openTracking && inv.open_count !== undefined) {
            if (inv.open_count > 0) {
                openTracking.style.display = 'flex';
                if (openCountEl) openCountEl.textContent = inv.open_count;
                if (lastOpenedEl) lastOpenedEl.textContent = inv.last_opened || 'Never';
            } else {
                openTracking.style.display = 'none';
            }
        }

        var savedLogo = localStorage.getItem('company_logo');
        var logoV = document.getElementById('logo-preview-view');
        if (savedLogo && logoV) { logoV.src = savedLogo; logoV.style.display = 'block'; }
        else if (logoV) {
            fetch('/api/client/logo').then(function(r) { return r.json(); }).then(function(data) {
                if (data.logo_url && logoV) { logoV.src = data.logo_url; logoV.style.display = 'block'; localStorage.setItem('company_logo', data.logo_url); }
                else if (logoV) logoV.style.display = 'none';
            }).catch(function() { logoV.style.display = 'none'; });
        }

        // Company details
        var companyDetails = document.getElementById('view-inv-company-details');
        if (inv.company && inv.company.name) {
            companyDetails.style.display = 'block';
            document.getElementById('view-inv-company-name').textContent = inv.company.name;
            document.getElementById('view-inv-company-address').textContent = inv.company.address || '';
            document.getElementById('view-inv-company-email').textContent = inv.company.email ? 'Email: ' + inv.company.email : '';
            document.getElementById('view-inv-company-phone').textContent = inv.company.phone_number ? 'Phone: ' + inv.company.phone_number : '';
            document.getElementById('view-inv-company-abn').textContent = inv.company.abn ? 'ABN: ' + inv.company.abn : '';
        } else {
            companyDetails.style.display = 'none';
        }

        var tbody = document.getElementById('view-line-items-body');
        tbody.innerHTML = '';
        var subtotal = 0, vat = 0;
        if (inv.line_items) {
            inv.line_items.forEach(function(item) {
                var amount = item.qty * item.price;
                if (item.disc && item.disc > 0) amount *= (1 - item.disc / 100);
                var itemVat = 0;
                var taxType = inv.tax_type || 'exclusive';
                if (taxType === 'exclusive') { itemVat = amount * 0.20; }
                else if (taxType === 'inclusive') { itemVat = amount - (amount / 1.20); amount -= itemVat; }
                subtotal += amount; vat += itemVat;
                tbody.insertAdjacentHTML('beforeend', '<tr><td style="padding:12px 16px;vertical-align:top;">' + (item.name || '') + '</td><td style="padding:12px 16px;word-wrap:break-word;overflow-wrap:break-word;max-width:280px;vertical-align:top;">' + item.description + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + item.qty + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + item.price.toFixed(2) + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + (item.disc || 0) + '%</td><td style="padding:12px 16px;vertical-align:top;">20% VAT</td><td style="padding:12px 16px;text-align:right;font-weight:600;vertical-align:top;">' + amount.toFixed(2) + '</td></tr>');
            });
        }
        document.getElementById('view-summary-subtotal').textContent = subtotal.toFixed(2);
        document.getElementById('view-summary-vat').textContent = vat.toFixed(2);
        document.getElementById('view-summary-total').textContent = (subtotal + vat).toFixed(2);

        document.getElementById('view-invoice-delete-btn').dataset.number = inv.number;
        document.getElementById('view-invoice-paid-btn').dataset.number = inv.number;

        var backBtn = document.getElementById('preview-back-btn');
        if (backBtn) backBtn.style.display = 'none';
        document.querySelectorAll('.invoice-action-btn').forEach(function(btn) { btn.style.display = 'inline-block'; });
        showView('view-invoice-view');
    } catch (e) {
        showToast('Failed to load invoice', 'error');
    }
}
window.viewInvoice = viewInvoice;

// --- Generate PDF ---
function generateInvoicePDF() {
    var jsPDF = window.jspdf.jsPDF;
    var doc = new jsPDF({ unit: 'pt', format: 'letter' });
    var w = 612, h = 792;
    var ml = 50, mr = w - 50;
    var pageBottom = h - 30;
    var y = 36;

    var number = document.getElementById('view-inv-number-val').textContent || 'Invoice';
    var contact = document.getElementById('view-inv-contact').textContent || '';
    var email = document.getElementById('view-inv-email-display').textContent || '';
    var phone = document.getElementById('view-inv-phone-display').textContent || '';
    var issueDate = document.getElementById('view-inv-issue-date').textContent || '';
    var dueDate = document.getElementById('view-inv-due-date').textContent || '';
    var subtotal = document.getElementById('view-summary-subtotal').textContent || '0.00';
    var vat = document.getElementById('view-summary-vat').textContent || '0.00';
    var total = document.getElementById('view-summary-total').textContent || '0.00';
    var savedLogo = localStorage.getItem('company_logo') || '';

    var companyName = document.getElementById('view-inv-company-name');
    var companyAddr = document.getElementById('view-inv-company-address');
    var companyEmail = document.getElementById('view-inv-company-email');
    var companyPhone = document.getElementById('view-inv-company-phone');
    var companyAbn = document.getElementById('view-inv-company-abn');
    var company = companyName ? companyName.textContent : '';
    var compAddr = companyAddr ? companyAddr.textContent : '';
    var compEmail = companyEmail ? companyEmail.textContent.replace('Email: ', '') : '';
    var compPhone = companyPhone ? companyPhone.textContent.replace('Phone: ', '') : '';
    var compAbn = companyAbn ? companyAbn.textContent.replace('ABN: ', '') : '';

    doc.setFillColor(30, 41, 59);
    doc.rect(0, 0, w, 4, 'F');

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(28);
    doc.setTextColor(30, 41, 59);
    doc.text('TAX INVOICE', ml, y + 20);
    y += 50;

    if (savedLogo) {
        try { doc.addImage(savedLogo, 'PNG', mr - 100, 10, 100, 36); } catch(e) {}
    }

    var compY = 54;
    if (company) {
        doc.setFontSize(11);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 41, 59);
        doc.text(company.substring(0, 44), mr, compY, { align: 'right' });
        compY += 14;
    }
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100, 116, 139);
    if (compAddr) {
        compAddr.split(',').forEach(function(p) {
            p = p.trim();
            if (p) { doc.text(p.substring(0, 42), mr, compY, { align: 'right' }); compY += 12; }
        });
    }
    if (compPhone) { doc.text('Tel: ' + compPhone, mr, compY, { align: 'right' }); compY += 12; }
    if (compEmail) { doc.text(compEmail, mr, compY, { align: 'right' }); compY += 12; }

    var custY = y;
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(148, 163, 184);
    doc.text('SOLD TO', ml, custY);
    custY += 14;
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    if (contact) {
        contact.split(',').forEach(function(p) {
            p = p.trim();
            if (p) { doc.text(p.substring(0, 48), ml, custY); custY += 14; }
        });
    }
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100, 116, 139);
    if (email && email !== 'No email') { doc.text(email, ml, custY); custY += 12; }
    if (phone && phone !== 'No phone') { doc.text(phone, ml, custY); custY += 12; }

    y = Math.max(custY, compY) + 12;
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(ml, y, mr, y);
    y += 14;

    var detW = (mr - ml) / 3;
    var detLabels = ['INVOICE DATE', 'DUE DATE', 'INVOICE NO'];
    var detValues = [issueDate || '-', dueDate || '-', number];
    detLabels.forEach(function(label, i) {
        var dx = ml + detW * i;
        doc.setFontSize(7);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(148, 163, 184);
        doc.text(label, dx + 8, y);
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 41, 59);
        doc.text(detValues[i], dx + 8, y + 14);
    });
    y += 32;
    doc.line(ml, y, mr, y);
    y += 20;

    // ===== LINE ITEMS TABLE =====
    // Page: w=612, h=792, ml=50, mr=562, usable=512
    // Columns: Item(82) Desc(188) Qty(40) Price(60) Disc(48) Amount(80) + gaps=22
    var COL = {
        itemL: ml,       itemR: ml + 82,
        descL: ml + 88,  descR: ml + 276,
        qtyR:  mr - 148,
        priceR: mr - 92,
        discR: mr - 44,
        amountR: mr
    };

    function clipText(text, maxW) {
        var t = text || '-';
        while (t.length > 0 && doc.getTextWidth(t) > maxW) t = t.slice(0, -1);
        return t || '-';
    }

    function drawTableHeader(doc, yPos) {
        doc.setFillColor(30, 41, 59);
        doc.rect(ml, yPos, mr - ml, 20, 'F');
        doc.setFontSize(7.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(220, 225, 235);
        doc.text('Item', COL.itemL + 4, yPos + 13);
        doc.text('Description', COL.descL + 4, yPos + 13);
        doc.text('Qty', COL.qtyR, yPos + 13, { align: 'right' });
        doc.text('Unit Price', COL.priceR, yPos + 13, { align: 'right' });
        doc.text('Disc', COL.discR, yPos + 13, { align: 'right' });
        doc.text('Amount GBP', COL.amountR - 4, yPos + 13, { align: 'right' });
        return yPos + 24;
    }

    function drawPageNum(doc) {
        doc.setFontSize(7);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(148, 163, 184);
        doc.text(number + ' | aniprotech', ml, h - 14);
    }

    doc.setFontSize(9.5);
    doc.setFont('helvetica', 'normal');
    y = drawTableHeader(doc, y);

    var rows = [];
    document.querySelectorAll('#view-line-items-body tr').forEach(function(tr) {
        var cells = tr.querySelectorAll('td');
        if (cells.length < 7) return;
        rows.push({
            name: cells[0].textContent,
            desc: cells[1].textContent,
            qty: cells[2].textContent,
            price: cells[3].textContent,
            disc: (cells[4].textContent || '0').replace('%', '').trim(),
            amount: cells[6].textContent
        });
    });

    var rowIdx = 0;
    var pageNum = 1;

    function reservedHeight() {
        return 24 + 16 + 16 + 6 + 14 + 14 + 24 + 38 + 24 + 14 + 36 + 80 + 30;
    }

    var descMaxW = COL.descR - COL.descL - 8;

    rows.forEach(function(row) {
        doc.setFontSize(9.5);
        doc.setFont('helvetica', 'normal');

        var nameMaxW = COL.itemR - COL.itemL - 8;
        var nameLines = doc.splitTextToSize(row.name || '-', nameMaxW);
        var descLines = doc.splitTextToSize(row.desc || '-', descMaxW);
        var maxLines = Math.max(nameLines.length, descLines.length);
        var rowH = Math.max(22, maxLines * 12 + 10);

        if (y + rowH + reservedHeight() > pageBottom) {
            drawPageNum(doc);
            doc.addPage();
            pageNum++;
            y = 40;
            y = drawTableHeader(doc, y);
        }

        if (rowIdx % 2 === 0) {
            doc.setFillColor(248, 250, 252);
            doc.rect(ml, y, mr - ml, rowH, 'F');
        }

        doc.setFontSize(9.5);

        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 41, 59);
        var nameC = nameLines.map(function(l) { return clipText(l, nameMaxW); });
        doc.text(nameC, COL.itemL + 4, y + 14);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        var descC = descLines.map(function(l) { return clipText(l, descMaxW); });
        doc.text(descC, COL.descL + 4, y + 14);

        doc.text(row.qty, COL.qtyR, y + 14, { align: 'right' });
        doc.text(row.price, COL.priceR, y + 14, { align: 'right' });
        doc.text(row.disc, COL.discR, y + 14, { align: 'right' });

        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 41, 59);
        doc.text(row.amount, COL.amountR - 4, y + 14, { align: 'right' });

        y += rowH;
        rowIdx++;
    });

    if (rowIdx === 0) {
        doc.setFillColor(248, 250, 252);
        doc.rect(ml, y, mr - ml, 22, 'F');
        doc.setFontSize(9);
        doc.setTextColor(148, 163, 184);
        doc.text('No line items', COL.descL + 4, y + 14);
        y += 22;
    }

    drawPageNum(doc);

    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(ml, y, mr, y);
    y += 16;

    // ===== TOTALS =====
    var totLabelX = mr - 170;
    var totValX = mr - 8;

    doc.setFontSize(9.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100, 116, 139);
    doc.text('Subtotal', totLabelX, y);
    doc.setTextColor(30, 41, 59);
    doc.text(subtotal, totValX, y, { align: 'right' });
    y += 16;

    doc.setTextColor(100, 116, 139);
    doc.text('VAT (0%)', totLabelX, y);
    doc.setTextColor(30, 41, 59);
    doc.text(vat, totValX, y, { align: 'right' });
    y += 6;

    doc.setDrawColor(200, 210, 220);
    doc.setLineWidth(0.3);
    doc.line(totLabelX, y, totValX, y);
    y += 14;

    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('TOTAL GBP', totLabelX, y);
    doc.text(total, totValX, y, { align: 'right' });
    y += 24;

    // ===== Due Date =====
    doc.setFillColor(254, 243, 199);
    doc.roundedRect(ml, y, mr - ml, 26, 4, 4, 'F');
    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(146, 64, 14);
    doc.text('Payment is due by ' + dueDate + '. Please reference ' + number + ' when paying.', ml + 10, y + 16);
    y += 38;

    // ===== View and pay online =====
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(14, 165, 233);
    var payLink = 'View and pay online now';
    doc.text(payLink, ml, y);
    doc.link(ml, y - 9, doc.getTextWidth(payLink), 12, { url: window.location.origin + '/login.html' });
    y += 24;

    // ==========================================
    // PAYMENT ADVICE SLIP
    // ==========================================
    doc.setDrawColor(160, 170, 180);
    doc.setLineWidth(0.4);
    doc.setLineDashPattern([6, 4], 0);
    doc.line(ml, y, mr, y);
    doc.setLineDashPattern([], 0);
    doc.setFontSize(12);
    doc.setTextColor(160, 170, 180);
    doc.text('\u2702', ml - 2, y - 3);
    y += 14;

    // PAYMENT ADVICE header
    doc.setFillColor(248, 250, 252);
    doc.roundedRect(ml, y - 4, mr - ml, 28, 4, 4, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(13);
    doc.setTextColor(30, 41, 59);
    doc.text('PAYMENT ADVICE', ml + 10, y + 14);
    y += 36;

    // Two-column layout
    var stubLeft = ml + 10;
    var stubRight = w / 2 + 20;
    var stubRightVal = stubRight + 80;
    var slY = y;

    // Left: Company info
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(148, 163, 184);
    doc.text('PAY TO', stubLeft, slY);
    slY += 14;
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9.5);
    doc.setTextColor(30, 41, 59);
    if (company) { doc.text(company.substring(0, 38), stubLeft, slY); slY += 12; }
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(100, 116, 139);
    if (compAddr) {
        compAddr.split(',').forEach(function(p) {
            p = p.trim();
            if (p) { doc.text(p.substring(0, 38), stubLeft, slY); slY += 11; }
        });
    }
    if (compPhone) { doc.text('Tel: ' + compPhone, stubLeft, slY); slY += 11; }

    // Right: Invoice details — fixed alignment
    var srY = y;
    var srPairs = [
        ['Customer', contact.substring(0, 38)],
        ['Invoice Number', number],
        ['Amount Due', total],
        ['Due Date', dueDate]
    ];
    srPairs.forEach(function(pair) {
        doc.setFontSize(8);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(30, 41, 59);
        doc.text(pair[0], stubRight, srY);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        doc.text(pair[1] || '-', stubRightVal, srY);
        srY += 16;
    });
    // Amount Enclosed line with underline
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Amount Enclosed', stubRight, srY);
    doc.setDrawColor(180, 190, 200);
    doc.setLineWidth(0.3);
    doc.line(stubRightVal, srY + 3, stubRightVal + 100, srY + 3);
    srY += 16;

    // Footer
    var footY = Math.max(slY, srY) + 16;
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.3);
    doc.line(ml, footY, mr, footY);
    footY += 10;
    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(180, 190, 200);
    doc.text('Company Registration No: ' + (compAbn || '13930191') + '  |  Registered Office: ' + (compAddr || 'N/A'), ml, footY);

    return doc;
}

// --- Send Email ---
async function sendEmail() {
    var number = document.getElementById('view-inv-number-val').textContent;
    if (!number) return;

    var logoData = localStorage.getItem('company_logo') || '';

    var pdfB64 = '';
    try {
        var doc = generateInvoicePDF();
        pdfB64 = doc.output('datauristring').split(',')[1];
    } catch (e) { console.error('PDF generation failed:', e); }

    try {
        var res = await fetch('/api/invoices/' + encodeURIComponent(number) + '/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logo_data: logoData, pdf_data: pdfB64 })
        });
        var data = await res.json();
        if (res.ok) {
            showToast('Email sent via Gmail API with PDF attached!', 'success');
            fetchInvoices();
            viewInvoice(number);
        } else {
            showToast('Failed: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        showToast('Failed to send email: ' + e, 'error');
    }
}
window.sendEmail = sendEmail;

// --- Send WhatsApp ---
async function sendWhatsApp() {
    var number = document.getElementById('view-inv-number-val').textContent;
    if (!number) return;
    try {
        var res = await fetch('/api/invoices/' + encodeURIComponent(number) + '/send-whatsapp', { method: 'POST' });
        var data = await res.json();
        if (res.ok) { showToast('WhatsApp sent!', 'success'); fetchInvoices(); }
        else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.sendWhatsApp = sendWhatsApp;

// --- Delete Invoice ---
async function deleteInvoice(number) {
    if (!confirm('Delete invoice ' + number + '?')) return;
    try {
        var res = await fetch('/api/invoices/' + encodeURIComponent(number), { method: 'DELETE' });
        if (res.ok) { showToast('Invoice deleted', 'success'); fetchInvoices(); showView('invoices-view'); }
        else { var data = await res.json(); showToast('Delete failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Delete failed: ' + e, 'error'); }
}
window.deleteInvoice = deleteInvoice;

// --- Mark as Paid ---
async function markAsPaid(number) {
    if (!confirm('Mark invoice ' + number + ' as paid?')) return;
    try {
        var res = await fetch('/api/invoices/' + encodeURIComponent(number) + '/mark-paid', { method: 'POST' });
        if (res.ok) { showToast('Marked as paid', 'success'); fetchInvoices(); viewInvoice(number); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.markAsPaid = markAsPaid;

// --- Invoice Calculations ---
function calculateTotals() {
    var subtotal = 0, totalVat = 0;
    var taxType = (document.getElementById('tax-type') || {}).value || 'exclusive';
    document.querySelectorAll('.line-item-row').forEach(function(row) {
        var qty = parseFloat(row.querySelector('.item-qty') ? row.querySelector('.item-qty').value : 0) || 0;
        var price = parseFloat(row.querySelector('.item-price') ? row.querySelector('.item-price').value : 0) || 0;
        var disc = parseFloat(row.querySelector('.item-disc') ? row.querySelector('.item-disc').value : 0) || 0;
        var amount = qty * price;
        if (disc > 0) amount *= (1 - disc / 100);
        var vat = 0;
        if (taxType === 'exclusive') { vat = amount * 0.20; }
        else if (taxType === 'inclusive') { vat = amount - (amount / 1.20); amount -= vat; }
        var amountEl = row.querySelector('.item-amount');
        var taxEl = row.querySelector('.item-tax-amount');
        if (amountEl) amountEl.textContent = amount.toFixed(2);
        if (taxEl) taxEl.textContent = vat.toFixed(2);
        subtotal += amount;
        totalVat += vat;
    });
    var subEl = document.getElementById('summary-subtotal');
    var vatEl = document.getElementById('summary-vat');
    var totalEl = document.getElementById('summary-total');
    if (subEl) subEl.textContent = subtotal.toFixed(2);
    if (vatEl) vatEl.textContent = totalVat.toFixed(2);
    if (totalEl) totalEl.textContent = (subtotal + totalVat).toFixed(2);
}
window.calculateTotals = calculateTotals;

function addLineItemRow() {
    var tbody = document.getElementById('line-items-body');
    if (!tbody) return;
    var html = '<tr class="line-item-row" style="border-bottom:1px solid var(--border-color);background:var(--surface-color);">' +
        '<td style="padding:8px;text-align:center;color:var(--text-secondary);cursor:grab;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/>' +
        '<circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/>' +
        '</svg></td>' +
        '<td style="padding:0;"><input type="text" class="table-input item-name" style="width:100%;" placeholder="Item name"></td>' +
        '<td style="padding:0;"><textarea class="table-input item-desc" rows="1" style="width:100%;resize:vertical;min-height:32px;overflow:hidden;line-height:1.4;" ' +
        'oninput="this.style.height=\'auto\';this.style.height=this.scrollHeight+\'px\';"></textarea></td>' +
        '<td style="padding:0;"><input type="number" class="table-input item-qty" style="width:100%;text-align:right;" value="0" step="1" min="0"></td>' +
        '<td style="padding:0;"><input type="number" class="table-input item-price" style="width:100%;text-align:right;" value="0" step="0.01" min="0"></td>' +
        '<td style="padding:0;"><input type="number" class="table-input item-disc" style="width:100%;text-align:right;" placeholder="0" step="1" min="0" max="100"></td>' +
        '<td style="padding:0;"><select class="table-input" style="width:100%;"><option>200 - Sales</option></select></td>' +
        '<td style="padding:0;"><select class="table-input" style="width:100%;"><option>20% VAT</option><option>No Tax</option></select></td>' +
        '<td style="padding:12px 8px;text-align:right;" class="item-tax-amount">0.00</td>' +
        '<td style="padding:12px 8px;text-align:right;font-weight:500;" class="item-amount">0.00</td>' +
        '<td style="padding:8px;text-align:center;">' +
        '<button type="button" class="btn-icon delete-row" style="color:var(--danger-color);cursor:pointer;background:none;border:none;">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
        '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
        '</button></td></tr>';
    tbody.insertAdjacentHTML('beforeend', html);
}
window.addLineItemRow = addLineItemRow;

// --- Preview Invoice ---
function previewInvoice() {
    var contact = document.getElementById('inv-contact').value || 'Draft';
    var email = document.getElementById('inv-email') ? document.getElementById('inv-email').value : '';
    var phone = document.getElementById('inv-phone') ? document.getElementById('inv-phone').value : '';
    var issue_date = document.getElementById('inv-issue-date').value || '';
    var due_date = document.getElementById('inv-due-date').value || '';
    var invoice_number = document.getElementById('inv-number').value || 'DRAFT';

    document.getElementById('view-inv-title').textContent = 'Invoice ' + invoice_number;
    document.getElementById('view-inv-status').textContent = 'Preview';
    document.getElementById('view-inv-status').className = 'status-pill';
    document.getElementById('view-inv-contact').textContent = contact;
    var emailD = document.getElementById('view-inv-email-display');
    if (emailD) emailD.textContent = email || 'No email';
    var phoneD = document.getElementById('view-inv-phone-display');
    if (phoneD) phoneD.textContent = phone || 'No phone';
    document.getElementById('view-inv-issue-date').textContent = issue_date;
    document.getElementById('view-inv-due-date').textContent = due_date;
    document.getElementById('view-inv-number-val').textContent = invoice_number;

    var tbody = document.getElementById('view-line-items-body');
    tbody.innerHTML = '';
    var taxType = (document.getElementById('tax-type') || {}).value || 'exclusive';

    document.querySelectorAll('.line-item-row').forEach(function(row) {
        var name = row.querySelector('.item-name') ? row.querySelector('.item-name').value : '';
        var desc = row.querySelector('.item-desc') ? row.querySelector('.item-desc').value : '';
        var qty = parseFloat(row.querySelector('.item-qty') ? row.querySelector('.item-qty').value : 0) || 0;
        var price = parseFloat(row.querySelector('.item-price') ? row.querySelector('.item-price').value : 0) || 0;
        var disc = parseFloat(row.querySelector('.item-disc') ? row.querySelector('.item-disc').value : 0) || 0;
        if (name || desc || qty > 0 || price > 0) {
            var amount = qty * price;
            if (disc > 0) amount *= (1 - disc / 100);
            var vat = 0;
            if (taxType === 'exclusive') { vat = amount * 0.20; }
            else if (taxType === 'inclusive') { vat = amount - (amount / 1.20); amount -= vat; }
            tbody.insertAdjacentHTML('beforeend', '<tr><td style="padding:12px 16px;vertical-align:top;">' + name + '</td><td style="padding:12px 16px;word-wrap:break-word;overflow-wrap:break-word;max-width:280px;vertical-align:top;">' + desc + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + qty + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + price.toFixed(2) + '</td><td style="padding:12px 16px;text-align:right;vertical-align:top;">' + disc + '%</td><td style="padding:12px 16px;vertical-align:top;">20% VAT</td><td style="padding:12px 16px;text-align:right;font-weight:600;vertical-align:top;">' + amount.toFixed(2) + '</td></tr>');
        }
    });

    document.getElementById('view-summary-subtotal').textContent = document.getElementById('summary-subtotal').textContent;
    document.getElementById('view-summary-vat').textContent = document.getElementById('summary-vat').textContent;
    document.getElementById('view-summary-total').textContent = document.getElementById('summary-total').textContent;

    var backBtn = document.getElementById('preview-back-btn');
    if (backBtn) backBtn.style.display = 'inline-block';
    document.querySelectorAll('.invoice-action-btn').forEach(function(btn) { btn.style.display = 'none'; });
    showView('view-invoice-view');
}
window.previewInvoice = previewInvoice;

// --- Submit Invoice ---
async function submitComplexInvoice(status) {
    status = status || 'Awaiting Payment';
    var contact = document.getElementById('inv-contact').value;
    if (!contact) { showToast('Customer name is required', 'error'); return; }

    var line_items = [];
    document.querySelectorAll('.line-item-row').forEach(function(row) {
        var name = row.querySelector('.item-name') ? row.querySelector('.item-name').value : '';
        var desc = row.querySelector('.item-desc') ? row.querySelector('.item-desc').value : '';
        var qty = parseFloat(row.querySelector('.item-qty') ? row.querySelector('.item-qty').value : 0) || 0;
        var price = parseFloat(row.querySelector('.item-price') ? row.querySelector('.item-price').value : 0) || 0;
        var disc = parseFloat(row.querySelector('.item-disc') ? row.querySelector('.item-disc').value : 0) || 0;
        if (name || desc || qty > 0 || price > 0) {
            line_items.push({ name: name, description: desc, qty: qty, price: price, disc: disc, account: '200 - Sales', tax_rate: '20% (VAT on Income)' });
        }
    });
    if (line_items.length === 0) { showToast('Add at least one line item', 'error'); return; }

    var payload = {
        contact: contact,
        email: document.getElementById('inv-email') ? document.getElementById('inv-email').value : '',
        phone_number: document.getElementById('inv-phone') ? document.getElementById('inv-phone').value : '',
        issue_date: document.getElementById('inv-issue-date').value,
        due_date: document.getElementById('inv-due-date').value,
        invoice_number: document.getElementById('inv-number').value,
        reference: document.getElementById('inv-ref').value,
        line_items: line_items,
        tax_type: (document.getElementById('tax-type') || {}).value || 'exclusive'
    };

    try {
        var response = await fetch('/api/invoices', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!response.ok) { var err = await response.json(); throw new Error(err.detail || 'Failed'); }
        var invData = await response.json();
        document.getElementById('complex-invoice-form').reset();
        document.getElementById('line-items-body').innerHTML = '';
        addLineItemRow();
        calculateTotals();

        if (status === 'Awaiting Payment' && payload.email) {
            showToast('Invoice created! Sending email...', 'info');
            await viewInvoice(invData.number);
            await sendEmail();
        } else if (status === 'Awaiting Payment' && !payload.email) {
            showToast('Invoice created! No email address — add one to send.', 'warning');
            showView('invoices-view');
        } else {
            showToast('Invoice saved as draft', 'success');
            showView('invoices-view');
        }
    } catch (e) { showToast('Failed: ' + e.message, 'error'); }
}
window.submitComplexInvoice = submitComplexInvoice;

// --- PDF Download ---
function downloadPDF() {
    var number = document.getElementById('view-inv-number-val').textContent || 'invoice';
    var doc = generateInvoicePDF();
    doc.save(number + '.pdf');
}
window.downloadPDF = downloadPDF;

// --- PDF Preview ---
function previewPDF() {
    var doc = generateInvoicePDF();
    var pdfBlob = doc.output('blob');
    var pdfUrl = URL.createObjectURL(pdfBlob);
    window.open(pdfUrl, '_blank');
}
window.previewPDF = previewPDF;

// --- Reports ---
async function loadReports() {
    try {
        var res = await fetch('/api/invoices');
        var invoices = await res.json();
        var statusCounts = {};
        invoices.forEach(function(inv) { statusCounts[inv.status] = (statusCounts[inv.status] || 0) + 1; });
        var chartEl = document.getElementById('reports-status-chart');
        if (chartEl) {
            var html = '<div style="display:flex;flex-direction:column;gap:12px;">';
            var colors = { 'Draft': '#94a3b8', 'Sent': '#00f0ff', 'Awaiting Payment': '#fcd34d', 'Paid': '#39ff14' };
            for (var status in statusCounts) {
                var pct = Math.round((statusCounts[status] / invoices.length) * 100);
                html += '<div><div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>' + status + '</span><span>' + statusCounts[status] + ' (' + pct + '%)</span></div><div style="height:8px;background:rgba(255,255,255,0.1);border-radius:4px;overflow:hidden;"><div style="height:100%;width:' + pct + '%;background:' + (colors[status] || '#94a3b8') + ';border-radius:4px;"></div></div></div>';
            }
            html += '</div>';
            chartEl.innerHTML = html;
        }
        // Revenue chart
        var revEl = document.getElementById('reports-chart-container');
        if (revEl) {
            var monthly = {};
            invoices.forEach(function(inv) { var m = inv.date ? inv.date.substring(0, 7) : 'Unknown'; monthly[m] = (monthly[m] || 0) + inv.due; });
            var months = Object.keys(monthly).sort();
            if (months.length === 0) { revEl.innerHTML = '<div class="loading">No revenue data</div>'; return; }
            var maxRev = Math.max.apply(null, Object.values(monthly));
            var barHtml = '<div class="chart-bars" style="height:150px;">';
            months.forEach(function(m) {
                var h = (monthly[m] / maxRev) * 100;
                barHtml += '<div class="chart-month"><div class="bar-group"><div class="bar in" style="height:' + h + '%"></div></div><span class="month-label">' + m + '</span></div>';
            });
            barHtml += '</div>';
            revEl.innerHTML = barHtml;
        }
    } catch (e) { console.error('Reports error:', e); }
}
window.loadReports = loadReports;

// --- Gmail API Status ---
async function loadGmailStatus() {
    try {
        var res = await fetch('/api/gmail/status');
        var data = await res.json();
        var statusEl = document.getElementById('gmail-status');
        var loginBtn = document.getElementById('gmail-login-btn');
        var emailEl = document.getElementById('gmail-email');
        var demoSection = document.getElementById('demo-email-section');
        if (!statusEl) return;
        if (data.gmail_ready) {
            statusEl.textContent = 'Connected';
            statusEl.style.color = 'var(--success-color)';
            emailEl.textContent = data.user_email || data.user_name || 'Connected';
            emailEl.style.display = 'block';
            loginBtn.style.display = 'none';
            if (demoSection) demoSection.style.display = 'block';
        } else if (data.logged_in) {
            statusEl.textContent = 'Logged in (re-login for refresh token)';
            statusEl.style.color = 'var(--warning-color)';
            emailEl.textContent = data.user_email || '';
            emailEl.style.display = data.user_email ? 'block' : 'none';
            loginBtn.style.display = 'inline-block';
            if (demoSection) demoSection.style.display = 'none';
        } else {
            statusEl.textContent = 'Not connected';
            statusEl.style.color = 'var(--danger-color)';
            emailEl.style.display = 'none';
            loginBtn.style.display = 'inline-block';
            if (demoSection) demoSection.style.display = 'none';
        }
    } catch (e) { var s = document.getElementById('gmail-status'); if (s) s.textContent = 'Error'; }
}
window.loadGmailStatus = loadGmailStatus;

async function testGmailSend() {
    var toEmail = document.getElementById('demo-email').value;
    var btn = document.getElementById('send-demo-btn');
    if (!toEmail) { showToast('Enter a recipient email', 'error'); return; }
    if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }
    try {
        var res = await fetch('/api/send-test-email', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to_email: toEmail, subject: 'Test Invoice - aniprotech', body: 'Test email from aniprotech via Gmail API.' }) });
        var data = await res.json();
        if (res.ok) showToast('Email sent!', 'success');
        else showToast('Failed: ' + (data.detail || 'Error'), 'error');
    } catch (e) { showToast('Failed: ' + e, 'error'); }
    if (btn) { btn.disabled = false; btn.textContent = 'Send 10'; }
}
window.testGmailSend = testGmailSend;

async function sendDemoEmail(count) {
    count = count || 1;
    var toEmail = document.getElementById('demo-email').value || 'udayyyv@gmail.com';
    var btn = document.getElementById('send-demo-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Sending ' + count + '...'; }
    var success = 0, fail = 0;
    for (var i = 0; i < count; i++) {
        try {
            var res = await fetch('/api/send-test-email', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to_email: toEmail, subject: 'Demo Invoice #' + (i + 1), body: 'Demo email ' + (i + 1) + ' of ' + count + ' from aniprotech via Gmail API.' }) });
            if (res.ok) success++; else fail++;
        } catch (e) { fail++; }
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Send ' + count; }
    if (fail > 0) showToast('Sent ' + success + '/' + count + ' (' + fail + ' failed). Ensure you are logged in with Google.', 'warning');
    else showToast(success + ' emails sent to ' + toEmail, 'success');
}
window.sendDemoEmail = sendDemoEmail;

// --- Settings ---
async function saveCompanyDetails() {
    var payload = {
        company_name: document.getElementById('settings-company-name') ? document.getElementById('settings-company-name').value : '',
        email: document.getElementById('settings-company-email') ? document.getElementById('settings-company-email').value : '',
        phone_number: document.getElementById('settings-company-phone') ? document.getElementById('settings-company-phone').value : '',
        company_address: document.getElementById('settings-company-address') ? document.getElementById('settings-company-address').value : ''
    };
    try {
        var res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var data = await res.json();
        if (res.ok) {
            showToast('Company details saved successfully!', 'success');
        } else {
            showToast('Failed to save: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        showToast('Failed to save: ' + e, 'error');
    }
}
window.saveCompanyDetails = saveCompanyDetails;

async function saveSettings() {
    var payload = {
        company_name: document.getElementById('settings-company-name') ? document.getElementById('settings-company-name').value : '',
        email: document.getElementById('settings-company-email') ? document.getElementById('settings-company-email').value : '',
        phone_number: document.getElementById('settings-company-phone') ? document.getElementById('settings-company-phone').value : '',
        company_address: document.getElementById('settings-company-address') ? document.getElementById('settings-company-address').value : '',
        company_abn: document.getElementById('settings-company-abn') ? document.getElementById('settings-company-abn').value : '',
        company_website: document.getElementById('settings-company-website') ? document.getElementById('settings-company-website').value : '',
        currency: document.getElementById('setting-currency') ? document.getElementById('setting-currency').value : 'USD',
        tax_rate: document.getElementById('setting-tax-rate') ? document.getElementById('setting-tax-rate').value : '20',
        default_payment_terms: document.getElementById('setting-payment-terms') ? document.getElementById('setting-payment-terms').value : '14',
        invoice_prefix: document.getElementById('setting-invoice-prefix') ? document.getElementById('setting-invoice-prefix').value : 'INV-'
    };
    try {
        var res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var data = await res.json();
        if (res.ok) {
            showToast('Settings saved successfully!', 'success');
        } else {
            showToast('Failed to save settings: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (e) {
        showToast('Failed to save settings: ' + e, 'error');
    }
}
window.saveSettings = saveSettings;

async function loadSettings() {
    try {
        var res = await fetch('/api/settings');
        if (!res.ok) return;
        var data = await res.json();
        if (data.company_name !== undefined) { var el = document.getElementById('settings-company-name'); if (el) el.value = data.company_name; }
        if (data.email !== undefined) { var el = document.getElementById('settings-company-email'); if (el) el.value = data.email; }
        if (data.phone_number !== undefined) { var el = document.getElementById('settings-company-phone'); if (el) el.value = data.phone_number; }
        if (data.company_address !== undefined) { var el = document.getElementById('settings-company-address'); if (el) el.value = data.company_address; }
        if (data.company_abn !== undefined) { var el = document.getElementById('settings-company-abn'); if (el) el.value = data.company_abn; }
        if (data.company_website !== undefined) { var el = document.getElementById('settings-company-website'); if (el) el.value = data.company_website; }
        if (data.currency !== undefined) { var el = document.getElementById('setting-currency'); if (el) el.value = data.currency; }
        if (data.tax_rate !== undefined) { var el = document.getElementById('setting-tax-rate'); if (el) el.value = data.tax_rate; }
        if (data.default_payment_terms !== undefined) { var el = document.getElementById('setting-payment-terms'); if (el) el.value = data.default_payment_terms; }
        if (data.invoice_prefix !== undefined) { var el = document.getElementById('setting-invoice-prefix'); if (el) el.value = data.invoice_prefix; }
    } catch (e) { console.error('Failed to load settings:', e); }
    fetch('/api/client/logo').then(function(r) { return r.json(); }).then(function(data) {
        if (data.logo_url) {
            var img = document.getElementById('settings-logo-img');
            var txt = document.getElementById('settings-logo-text');
            if (img) { img.src = data.logo_url; img.style.display = 'block'; }
            if (txt) txt.style.display = 'none';
            localStorage.setItem('company_logo', data.logo_url);
        }
    }).catch(function() {});
}
window.loadSettings = loadSettings;

function handleSettingsLogoUpload(e) {
    var file = e.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { showToast('File too large. Max 2MB.', 'error'); return; }
    var reader = new FileReader();
    reader.onload = function(ev) {
        var b64 = ev.target.result;
        localStorage.setItem('company_logo', b64);
        fetch('/api/client/logo', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logo_url: b64 })
        }).then(function() {
            showToast('Logo saved!', 'success');
        }).catch(function() {
            showToast('Failed to save logo', 'error');
        });
        var img = document.getElementById('settings-logo-img');
        var txt = document.getElementById('settings-logo-text');
        if (img) { img.src = b64; img.style.display = 'block'; }
        if (txt) txt.style.display = 'none';
    };
    reader.readAsDataURL(file);
}
window.handleSettingsLogoUpload = handleSettingsLogoUpload;

// --- Contact Autocomplete ---
var contactDropdownTimeout = null;

function setupContactAutocomplete() {
    var wrap = document.getElementById('contact-autocomplete-wrap');
    if (!wrap) return;
    var input = document.getElementById('inv-contact');
    var dropdown = document.getElementById('contact-autocomplete-dropdown');
    if (!input || !dropdown) return;

    input.addEventListener('input', function() {
        var val = input.value.trim();
        clearTimeout(contactDropdownTimeout);
        if (val.length < 1) { dropdown.classList.remove('show'); return; }
        contactDropdownTimeout = setTimeout(function() {
            fetch('/api/contacts/search?q=' + encodeURIComponent(val))
                .then(function(r) { return r.json(); })
                .then(function(contacts) {
                    dropdown.innerHTML = '';
                    contacts.forEach(function(c) {
                        var div = document.createElement('div');
                        div.className = 'contact-autocomplete-item';
                        var initial = (c.name || '?')[0].toUpperCase();
                        div.innerHTML = '<div class="ca-icon">' + initial + '</div><div><div class="ca-name">' + c.name + '</div>' + (c.email ? '<div class="ca-email">' + c.email + '</div>' : '') + '</div>';
                        div.addEventListener('click', function() {
                            input.value = c.name;
                            var emailEl = document.getElementById('inv-email');
                            if (emailEl && c.email) emailEl.value = c.email;
                            var phoneEl = document.getElementById('inv-phone');
                            if (phoneEl && c.phone_number) phoneEl.value = c.phone_number;
                            dropdown.classList.remove('show');
                        });
                        dropdown.appendChild(div);
                    });
                    if (val.length > 0) {
                        var newDiv = document.createElement('div');
                        newDiv.className = 'contact-autocomplete-new';
                        newDiv.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Create new contact: <strong>' + val + '</strong>';
                        newDiv.addEventListener('click', function() {
                            input.value = val;
                            dropdown.classList.remove('show');
                        });
                        dropdown.appendChild(newDiv);
                    }
                    dropdown.classList.add('show');
                });
        }, 200);
    });

    input.addEventListener('blur', function() {
        setTimeout(function() { dropdown.classList.remove('show'); }, 200);
    });

    input.addEventListener('focus', function() {
        if (input.value.trim().length > 0) {
            input.dispatchEvent(new Event('input'));
        }
    });
}

// ============================================================
// HR MODULE
// ============================================================

var allContacts = [];
var allEmployees = [];
var allPayslips = [];
var currentEmpFilter = '';
var currentPsFilter = '';
var currentEmployeeId = null;
var currentPayslipId = null;

async function preloadSearchData() {
    try {
        var [cRes, empRes, psRes] = await Promise.all([
            fetch('/api/contacts').then(function(r) { return r.ok ? r.json() : []; }).catch(function() { return []; }),
            fetch('/api/employees').then(function(r) { return r.ok ? r.json() : []; }).catch(function() { return []; }),
            fetch('/api/payslips').then(function(r) { return r.ok ? r.json() : []; }).catch(function() { return []; })
        ]);
        allContacts = cRes || [];
        allEmployees = empRes || [];
        allPayslips = psRes || [];
    } catch (e) {}
}

// --- HR Stats ---
async function loadHRStats() {
    try {
        var res = await fetch('/api/hr/stats');
        if (!res.ok) return;
        var s = await res.json();
        var el = function(id) { return document.getElementById(id); };
        if (el('hr-total')) el('hr-total').textContent = s.total || 0;
        if (el('hr-active')) el('hr-active').textContent = s.active || 0;
        if (el('hr-onboarding')) el('hr-onboarding').textContent = s.onboarding || 0;
        if (el('hr-offboarding')) el('hr-offboarding').textContent = s.offboarding || 0;
        if (el('hr-depts')) el('hr-depts').textContent = s.departments || 0;
    } catch (e) { console.error('HR stats error:', e); }
}

// --- Employees ---
async function fetchEmployees(statusFilter) {
    try {
        var url = '/api/employees';
        if (statusFilter) url += '?status=' + encodeURIComponent(statusFilter);
        var res = await fetch(url);
        if (!res.ok) throw new Error('Failed');
        allEmployees = await res.json();
        renderEmployees(allEmployees);
        var countEl = document.getElementById('employee-count');
        if (countEl) countEl.textContent = allEmployees.length + ' item' + (allEmployees.length !== 1 ? 's' : '');
    } catch (e) {
        var tbody = document.getElementById('employees-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="loading">Failed to load employees.</td></tr>';
    }
}

function renderEmployees(employees) {
    var tbody = document.getElementById('employees-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (employees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-secondary);">No employees found.</td></tr>';
        return;
    }
    employees.forEach(function(e) {
        var statusClass = (e.status || '').toLowerCase().replace(/\s+/g, '-');
        var typeLabel = (e.employment_type || '').replace('_', ' ');
        tbody.insertAdjacentHTML('beforeend', '<tr><td><a href="#" class="link" onclick="event.preventDefault();viewEmployee(' + e.id + ')">' + e.first_name + ' ' + e.last_name + '</a><br><span style="font-size:0.78rem;color:var(--text-secondary);">' + (e.email || '') + '</span></td><td>' + (e.employee_id || '-') + '</td><td>' + (e.department_name || '-') + '</td><td>' + (e.job_title || '-') + '</td><td>' + typeLabel + '</td><td>' + (e.start_date || '-') + '</td><td><span class="status-pill status-' + statusClass + '">' + e.status + '</span></td><td class="text-right"><button class="btn btn-outline btn-sm" onclick="viewEmployee(' + e.id + ')">View</button></td></tr>');
    });
}

function filterEmployees(status, btn) {
    currentEmpFilter = status;
    document.querySelectorAll('#employee-tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    if (status) {
        var filtered = allEmployees.filter(function(e) { return e.status === status; });
        renderEmployees(filtered);
    } else {
        renderEmployees(allEmployees);
    }
}
window.filterEmployees = filterEmployees;

function searchEmployees() {
    var q = (document.getElementById('employee-search').value || '').toLowerCase();
    var filtered = allEmployees.filter(function(e) {
        return ((e.first_name + ' ' + e.last_name).toLowerCase().indexOf(q) >= 0 ||
            (e.email || '').toLowerCase().indexOf(q) >= 0 ||
            (e.employee_id || '').toLowerCase().indexOf(q) >= 0 ||
            (e.job_title || '').toLowerCase().indexOf(q) >= 0 ||
            (e.department_name || '').toLowerCase().indexOf(q) >= 0);
    });
    renderEmployees(filtered);
}
window.searchEmployees = searchEmployees;

// --- View Employee ---
async function viewEmployee(empId) {
    currentEmployeeId = empId;
    try {
        var res = await fetch('/api/employees/' + empId);
        if (!res.ok) throw new Error('Failed');
        var emp = await res.json();
        document.getElementById('emp-detail-name').textContent = emp.full_name;
        document.getElementById('emp-detail-status').textContent = emp.status;
        document.getElementById('emp-detail-status').className = 'status-pill status-' + (emp.status || '').toLowerCase().replace(/\s+/g, '-');
        document.getElementById('emp-detail-eid').textContent = emp.employee_id || '-';
        document.getElementById('emp-detail-email').textContent = emp.email || '-';
        document.getElementById('emp-detail-phone').textContent = emp.phone || '-';
        document.getElementById('emp-detail-title').textContent = emp.job_title || '-';
        document.getElementById('emp-detail-dept').textContent = emp.department_name || '-';
        document.getElementById('emp-detail-mgr').textContent = emp.manager_name || '-';
        document.getElementById('emp-detail-type').textContent = (emp.employment_type || '').replace('_', ' ');
        document.getElementById('emp-detail-payfreq').textContent = emp.pay_frequency || '-';
        document.getElementById('emp-detail-salary').textContent = emp.salary ? formatCurrency(emp.salary) : '-';
        document.getElementById('emp-detail-start').textContent = emp.start_date || '-';
        document.getElementById('emp-detail-taxrate').textContent = emp.tax_rate ? emp.tax_rate + '%' : '-';
        document.getElementById('emp-detail-emergency').textContent = emp.emergency_contact ? emp.emergency_contact + (emp.emergency_phone ? ' (' + emp.emergency_phone + ')' : '') : '-';

        var offboardBtn = document.getElementById('emp-offboard-btn');
        if (offboardBtn) offboardBtn.style.display = (emp.status === 'active' || emp.status === 'onboarding') ? 'inline-flex' : 'none';

        // Onboarding
        var items = emp.onboarding_items || [];
        var completed = items.filter(function(i) { return i.is_completed; }).length;
        var progressEl = document.getElementById('onboarding-progress');
        if (progressEl) progressEl.textContent = completed + '/' + items.length;
        var barFill = document.getElementById('onboarding-bar-fill');
        if (barFill) barFill.style.width = items.length ? Math.round((completed / items.length) * 100) + '%' : '0%';
        var listEl = document.getElementById('onboarding-items-list');
        if (listEl) {
            listEl.innerHTML = '';
            items.forEach(function(item) {
                var checkedAttr = item.is_completed ? 'checked' : '';
                var style = item.is_completed ? 'text-decoration:line-through;color:var(--text-secondary);' : '';
                listEl.insertAdjacentHTML('beforeend', '<label style="display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid var(--border-color);cursor:pointer;font-size:0.9rem;' + style + '"><input type="checkbox" ' + checkedAttr + ' onchange="toggleOnbItem(' + item.id + ', this.checked)" style="margin-top:4px;accent-color:var(--primary-color);"><div><div style="font-weight:500;">' + item.title + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + (item.category || '') + ' &bull; ' + (item.assigned_to || '') + '</div></div></label>');
            });
        }

        // Payslips
        var payslips = emp.payslips || [];
        var totalPaid = payslips.filter(function(p) { return p.status === 'Paid'; }).reduce(function(s, p) { return s + (p.net_pay || 0); }, 0);
        var totalPaidEl = document.getElementById('emp-total-paid');
        if (totalPaidEl) totalPaidEl.textContent = formatCurrency(totalPaid);
        var psCountEl = document.getElementById('emp-payslip-count');
        if (psCountEl) psCountEl.textContent = payslips.length;
        var psListEl = document.getElementById('emp-payslips-list');
        if (psListEl) {
            psListEl.innerHTML = '';
            if (payslips.length === 0) {
                psListEl.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary);font-size:0.85rem;">No payslips yet</div>';
            } else {
                payslips.forEach(function(p) {
                    var statusClass = (p.status || '').toLowerCase();
                    psListEl.insertAdjacentHTML('beforeend', '<div style="padding:12px 16px;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center;cursor:pointer;" onclick="viewPayslip(' + p.id + ')"><div><div style="font-weight:500;font-size:0.9rem;">' + p.number + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + p.period_start + ' to ' + p.period_end + '</div></div><div style="text-align:right;"><div style="font-weight:600;font-size:0.9rem;">' + formatCurrency(p.net_pay) + '</div><span class="status-pill status-' + statusClass + '" style="font-size:0.7rem;">' + p.status + '</span></div></div>');
                });
            }
        }

        showView('employee-detail-view');
    } catch (e) {
        showToast('Failed to load employee', 'error');
    }
}
window.viewEmployee = viewEmployee;

// --- Add Employee Modal ---
async function showAddEmployeeModal() {
    document.getElementById('add-employee-modal').style.display = 'flex';
    document.getElementById('add-employee-form').reset();
    var today = new Date().toISOString().split('T')[0];
    var startEl = document.getElementById('emp-start-date');
    if (startEl) startEl.value = today;
    // Load departments and employees for dropdowns
    try {
        var deptRes = await fetch('/api/departments');
        var depts = await deptRes.json();
        var deptSel = document.getElementById('emp-department');
        deptSel.innerHTML = '<option value="">None</option>';
        depts.forEach(function(d) { deptSel.insertAdjacentHTML('beforeend', '<option value="' + d.id + '">' + d.name + '</option>'); });
        var empRes = await fetch('/api/employees');
        var emps = await empRes.json();
        var mgrSel = document.getElementById('emp-reports-to');
        mgrSel.innerHTML = '<option value="">None</option>';
        emps.forEach(function(e) { mgrSel.insertAdjacentHTML('beforeend', '<option value="' + e.id + '">' + e.first_name + ' ' + e.last_name + '</option>'); });
    } catch (e) { console.error(e); }
}
window.showAddEmployeeModal = showAddEmployeeModal;

function closeAddEmployeeModal() {
    document.getElementById('add-employee-modal').style.display = 'none';
}
window.closeAddEmployeeModal = closeAddEmployeeModal;

async function submitNewEmployee() {
    var firstName = document.getElementById('emp-first-name').value.trim();
    var lastName = document.getElementById('emp-last-name').value.trim();
    var email = document.getElementById('emp-email').value.trim();
    if (!firstName || !lastName || !email) { showToast('First name, last name, and email are required', 'error'); return; }
    var password = document.getElementById('emp-password').value.trim();
    if (!password) { showToast('Password is required for employee login', 'error'); return; }
    var deptVal = document.getElementById('emp-department').value;
    var mgrVal = document.getElementById('emp-reports-to').value;
    var payload = {
        first_name: firstName, last_name: lastName, email: email,
        password: password,
        phone: document.getElementById('emp-phone').value,
        job_title: document.getElementById('emp-job-title').value,
        department_id: deptVal ? parseInt(deptVal) : null,
        reports_to: mgrVal ? parseInt(mgrVal) : null,
        employment_type: document.getElementById('emp-type').value,
        pay_frequency: document.getElementById('emp-pay-freq').value,
        salary: parseFloat(document.getElementById('emp-salary').value) || 0,
        tax_rate: parseFloat(document.getElementById('emp-tax-rate').value) || 0,
        start_date: document.getElementById('emp-start-date').value,
        emergency_contact: document.getElementById('emp-emergency-contact').value,
        emergency_phone: document.getElementById('emp-emergency-phone').value,
    };
    try {
        var res = await fetch('/api/employees', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var data = await res.json();
        if (res.ok) {
            showToast(data.message || 'Employee created', 'success');
            closeAddEmployeeModal();
            fetchEmployees(currentEmpFilter);
            loadHRStats();
        } else {
            showToast('Failed: ' + (data.detail || 'Error'), 'error');
        }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.submitNewEmployee = submitNewEmployee;

async function startOffboarding() {
    if (!currentEmployeeId) return;
    if (!confirm('Start offboarding for this employee?')) return;
    try {
        var res = await fetch('/api/employees/' + currentEmployeeId + '/offboard', { method: 'POST' });
        if (res.ok) { showToast('Offboarding started', 'success'); viewEmployee(currentEmployeeId); loadHRStats(); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.startOffboarding = startOffboarding;

async function resetEmpPassword() {
    if (!currentEmployeeId) return;
    var newPass = prompt('Enter new password for this employee:');
    if (!newPass || newPass.length < 4) { showToast('Password must be at least 4 characters', 'error'); return; }
    try {
        var res = await fetch('/api/employees/' + currentEmployeeId + '/reset-password', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: newPass })
        });
        var data = await res.json();
        if (res.ok) { showToast('Password updated', 'success'); }
        else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.resetEmpPassword = resetEmpPassword;

async function deleteCurrentEmployee() {
    if (!currentEmployeeId) return;
    if (!confirm('Delete this employee and all related data?')) return;
    try {
        var res = await fetch('/api/employees/' + currentEmployeeId, { method: 'DELETE' });
        if (res.ok) { showToast('Employee deleted', 'success'); showView('employees-view'); fetchEmployees(currentEmpFilter); loadHRStats(); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.deleteCurrentEmployee = deleteCurrentEmployee;

// --- Departments ---
var deptIcons = [
    { id: 'building', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="9" y1="22" x2="9" y2="17"/><line x1="15" y1="22" x2="15" y2="17"/><line x1="9" y1="12" x2="9" y2="12.01"/><line x1="15" y1="12" x2="15" y2="12.01"/><line x1="9" y1="8" x2="9" y2="8.01"/><line x1="15" y1="8" x2="15" y2="8.01"/><line x1="9" y1="17" x2="9" y2="22"/><line x1="15" y1="17" x2="15" y2="22"/></svg>' },
    { id: 'code', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>' },
    { id: 'users', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>' },
    { id: 'chart', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>' },
    { id: 'star', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>' },
    { id: 'shield', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' },
    { id: 'heart', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>' },
    { id: 'rocket', svg: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/></svg>' },
];
var deptColors = ['#00f0ff','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#f97316','#06b6d4','#84cc16','#6366f1'];
var editingDeptId = null;
var selectedDeptColor = '#00f0ff';
var selectedDeptIcon = 'building';

async function fetchDepartments() {
    try {
        var res = await fetch('/api/departments');
        if (!res.ok) throw new Error('Failed');
        var depts = await res.json();
        var grid = document.getElementById('dept-cards-grid');
        var empty = document.getElementById('dept-empty');
        if (!grid) return;
        grid.innerHTML = '';
        if (depts.length === 0) {
            if (empty) empty.style.display = 'block';
            grid.style.display = 'none';
            return;
        }
        if (empty) empty.style.display = 'none';
        grid.style.display = 'grid';
        depts.forEach(function(d) {
            var iconObj = deptIcons.find(function(i) { return i.id === d.icon; }) || deptIcons[0];
            var color = d.color || '#00f0ff';
            grid.insertAdjacentHTML('beforeend',
                '<div class="dept-card" onclick="openDeptDetail(' + d.id + ')" style="background:var(--surface-color);border:1px solid var(--border-color);border-radius:var(--radius-lg);padding:24px;cursor:pointer;transition:all 0.2s;border-top:3px solid ' + color + ';">' +
                    '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">' +
                        '<div style="width:44px;height:44px;border-radius:12px;background:' + color + '20;color:' + color + ';display:flex;align-items:center;justify-content:center;">' + iconObj.svg + '</div>' +
                        '<div><div style="font-weight:600;font-size:1rem;">' + d.name + '</div>' +
                        '<div style="font-size:0.78rem;color:var(--text-secondary);">' + (d.description || 'No description') + '</div></div>' +
                    '</div>' +
                    '<div style="display:flex;align-items:center;gap:8px;">' +
                        '<div style="width:32px;height:32px;border-radius:8px;background:rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:center;font-size:0.85rem;font-weight:600;">' + (d.employee_count || 0) + '</div>' +
                        '<div style="font-size:0.82rem;color:var(--text-secondary);">' + (d.employee_count === 1 ? 'employee' : 'employees') + '</div>' +
                    '</div>' +
                '</div>'
            );
        });
    } catch (e) { console.error('Depts error:', e); }
}

function openDeptModal(dept) {
    editingDeptId = dept ? dept.id : null;
    document.getElementById('dept-modal-title').textContent = dept ? 'Edit Department' : 'Add Department';
    document.getElementById('dept-name').value = dept ? dept.name : '';
    document.getElementById('dept-desc').value = dept ? (dept.description || '') : '';
    selectedDeptColor = dept ? (dept.color || '#00f0ff') : '#00f0ff';
    selectedDeptIcon = dept ? (dept.icon || 'building') : 'building';
    renderDeptColorPicker();
    renderDeptIconPicker();
    document.getElementById('dept-modal').style.display = 'flex';
}
window.openDeptModal = openDeptModal;

function closeDeptModal() {
    document.getElementById('dept-modal').style.display = 'none';
    editingDeptId = null;
}
window.closeDeptModal = closeDeptModal;

function renderDeptColorPicker() {
    var el = document.getElementById('dept-color-picker');
    el.innerHTML = '';
    deptColors.forEach(function(c) {
        el.insertAdjacentHTML('beforeend',
            '<div onclick="selectDeptColor(\'' + c + '\')" style="width:32px;height:32px;border-radius:8px;background:' + c + ';cursor:pointer;border:3px solid ' + (c === selectedDeptColor ? 'white' : 'transparent') + ';transition:border 0.15s;"></div>'
        );
    });
}
window.renderDeptColorPicker = renderDeptColorPicker;

function selectDeptColor(c) {
    selectedDeptColor = c;
    renderDeptColorPicker();
}
window.selectDeptColor = selectDeptColor;

function renderDeptIconPicker() {
    var el = document.getElementById('dept-icon-picker');
    el.innerHTML = '';
    deptIcons.forEach(function(i) {
        var isSelected = i.id === selectedDeptIcon;
        el.insertAdjacentHTML('beforeend',
            '<div onclick="selectDeptIcon(\'' + i.id + '\')" style="width:36px;height:36px;border-radius:8px;background:' + (isSelected ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)') + ';display:flex;align-items:center;justify-content:center;cursor:pointer;border:2px solid ' + (isSelected ? selectedDeptColor : 'transparent') + ';transition:all 0.15s;">' + i.svg + '</div>'
        );
    });
}
window.renderDeptIconPicker = renderDeptIconPicker;

function selectDeptIcon(id) {
    selectedDeptIcon = id;
    renderDeptIconPicker();
}
window.selectDeptIcon = selectDeptIcon;

async function saveDept() {
    var name = document.getElementById('dept-name').value.trim();
    if (!name) { showToast('Department name is required', 'error'); return; }
    var desc = document.getElementById('dept-desc').value.trim();
    var payload = { name: name, description: desc, color: selectedDeptColor, icon: selectedDeptIcon };
    try {
        var url = editingDeptId ? '/api/departments/' + editingDeptId : '/api/departments';
        var method = editingDeptId ? 'PUT' : 'POST';
        var res = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        var data = await res.json();
        if (res.ok) { showToast(editingDeptId ? 'Department updated' : 'Department created', 'success'); closeDeptModal(); fetchDepartments(); loadHRStats(); }
        else { showToast(data.detail || 'Error', 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.saveDept = saveDept;

async function openDeptDetail(id) {
    try {
        var res = await fetch('/api/departments/' + id);
        if (!res.ok) throw new Error('Failed');
        var d = await res.json();
        var iconObj = deptIcons.find(function(i) { return i.id === d.icon; }) || deptIcons[0];
        document.getElementById('dept-detail-icon').innerHTML = iconObj.svg;
        document.getElementById('dept-detail-icon').style.background = d.color + '20';
        document.getElementById('dept-detail-icon').style.color = d.color;
        document.getElementById('dept-detail-name').textContent = d.name;
        document.getElementById('dept-detail-desc').textContent = d.description || 'No description';
        document.getElementById('dept-detail-edit-btn').onclick = function() { closeDeptDetail(); openDeptModal(d); };
        document.getElementById('dept-detail-stats').innerHTML =
            '<div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:14px;"><div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:4px;">Team Size</div><div style="font-size:1.4rem;font-weight:700;">' + d.employee_count + '</div></div>' +
            '<div style="background:rgba(255,255,255,0.04);border-radius:10px;padding:14px;"><div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:4px;">Created</div><div style="font-size:0.85rem;font-weight:500;">' + (d.created_at || 'Unknown').split(' ')[0] + '</div></div>';
        var empList = document.getElementById('dept-detail-employees');
        empList.innerHTML = '';
        if (d.employees.length === 0) {
            empList.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary);font-size:0.85rem;">No employees in this department</div>';
        } else {
            d.employees.forEach(function(e) {
                var initial = (e.name || '?')[0].toUpperCase();
                empList.insertAdjacentHTML('beforeend',
                    '<div onclick="closeDeptDetail();viewEmployee(' + e.id + ')" style="display:flex;align-items:center;gap:12px;padding:10px;border-radius:8px;cursor:pointer;transition:background 0.15s;border-bottom:1px solid var(--border-color);">' +
                        '<div style="width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,' + d.color + '40,' + d.color + '20);color:' + d.color + ';display:flex;align-items:center;justify-content:center;font-weight:600;font-size:0.85rem;">' + initial + '</div>' +
                        '<div><div style="font-weight:500;font-size:0.9rem;">' + e.name + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + (e.job_title || '') + '</div></div>' +
                    '</div>'
                );
            });
        }
        document.getElementById('dept-detail-panel').style.display = 'flex';
    } catch (e) { showToast('Failed to load department', 'error'); }
}
window.openDeptDetail = openDeptDetail;

function closeDeptDetail() {
    document.getElementById('dept-detail-panel').style.display = 'none';
}
window.closeDeptDetail = closeDeptDetail;

async function deleteDepartment(id, name) {
    if (!confirm('Delete department "' + name + '"? Employees will be unassigned.')) return;
    try {
        var res = await fetch('/api/departments/' + id, { method: 'DELETE' });
        if (res.ok) { showToast('Department deleted', 'success'); fetchDepartments(); loadHRStats(); }
        else { var data = await res.json(); showToast(data.detail || 'Error', 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.deleteDepartment = deleteDepartment;

// --- Onboarding Hub ---
var onboardingHubData = [];
var onboardingHubFilter = 'all';
var onboardingBulkItems = [];

async function loadOnboardingHub() {
    try {
        var res = await fetch('/api/onboarding/hub');
        if (!res.ok) throw new Error('Failed');
        onboardingHubData = await res.json();
        renderOnboardingHub();
    } catch (e) { console.error('Onboarding hub error:', e); }
}

function renderOnboardingHub() {
    var data = onboardingHubData;
    if (onboardingHubFilter === 'onboarding') data = data.filter(function(e) { return e.status === 'onboarding' && e.progress < 100; });
    else if (onboardingHubFilter === 'complete') data = data.filter(function(e) { return e.progress === 100; });
    else if (onboardingHubFilter === 'overdue') data = data.filter(function(e) { return e.overdue > 0; });

    var totalEmps = onboardingHubData.length;
    var inProgress = onboardingHubData.filter(function(e) { return e.status === 'onboarding' && e.progress < 100; }).length;
    var completed = onboardingHubData.filter(function(e) { return e.progress === 100; }).length;
    var overdue = onboardingHubData.filter(function(e) { return e.overdue > 0; }).length;

    document.getElementById('onboarding-hub-stats').innerHTML =
        '<div class="widget" style="padding:20px;"><div style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:8px;">Total</div><div style="font-size:1.5rem;font-weight:700;">' + totalEmps + '</div></div>' +
        '<div class="widget" style="padding:20px;"><div style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:8px;">In Progress</div><div style="font-size:1.5rem;font-weight:700;color:var(--primary-color);">' + inProgress + '</div></div>' +
        '<div class="widget" style="padding:20px;"><div style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:8px;">Completed</div><div style="font-size:1.5rem;font-weight:700;color:var(--success-color);">' + completed + '</div></div>' +
        '<div class="widget" style="padding:20px;"><div style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:8px;">Overdue</div><div style="font-size:1.5rem;font-weight:700;color:var(--danger-color);">' + overdue + '</div></div>';

    var list = document.getElementById('onboarding-hub-list');
    var empty = document.getElementById('onboarding-hub-empty');
    if (!list) return;
    list.innerHTML = '';
    if (data.length === 0) {
        if (empty) empty.style.display = 'block';
        return;
    }
    if (empty) empty.style.display = 'none';

    data.forEach(function(e) {
        var barColor = e.progress === 100 ? 'var(--success-color)' : e.overdue > 0 ? 'var(--danger-color)' : 'var(--primary-color)';
        list.insertAdjacentHTML('beforeend',
            '<div class="widget" style="padding:16px 20px;margin-bottom:12px;cursor:pointer;" onclick="openOnbEmpDetail(' + e.id + ')">' +
                '<div style="display:flex;align-items:center;gap:16px;">' +
                    '<div style="width:42px;height:42px;border-radius:10px;background:rgba(0,240,255,0.1);color:var(--primary-color);display:flex;align-items:center;justify-content:center;font-weight:600;">' + (e.name || '?')[0].toUpperCase() + '</div>' +
                    '<div style="flex:1;min-width:0;">' +
                        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">' +
                            '<span style="font-weight:600;font-size:0.95rem;">' + e.name + '</span>' +
                            '<span style="font-size:0.75rem;padding:2px 8px;border-radius:6px;background:rgba(255,255,255,0.08);color:var(--text-secondary);">' + (e.department || 'No dept') + '</span>' +
                            (e.overdue > 0 ? '<span style="font-size:0.72rem;padding:2px 8px;border-radius:6px;background:rgba(239,68,68,0.15);color:var(--danger-color);">' + e.overdue + ' overdue</span>' : '') +
                        '</div>' +
                        '<div style="display:flex;align-items:center;gap:12px;">' +
                            '<div style="flex:1;height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;">' +
                                '<div style="height:100%;width:' + e.progress + '%;background:' + barColor + ';border-radius:3px;transition:width 0.4s;"></div>' +
                            '</div>' +
                            '<span style="font-size:0.82rem;font-weight:600;color:' + barColor + ';">' + e.completed + '/' + e.total + '</span>' +
                        '</div>' +
                    '</div>' +
                    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>' +
                '</div>' +
            '</div>'
        );
    });
}

function filterOnboardingHub(filter, btn) {
    onboardingHubFilter = filter;
    document.querySelectorAll('#onboarding-hub-view .tab').forEach(function(t) { t.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    renderOnboardingHub();
}
window.filterOnboardingHub = filterOnboardingHub;

async function openOnbEmpDetail(empId) {
    try {
        var [empRes, onbRes] = await Promise.all([
            fetch('/api/employees').then(function(r) { return r.ok ? r.json() : []; }),
            fetch('/api/employees/' + empId + '/onboarding').then(function(r) { return r.ok ? r.json() : { items: [], progress: 0 }; })
        ]);
        var emp = empRes.find(function(e) { return e.id === empId; });
        if (!emp) return;
        document.getElementById('onb-emp-name').textContent = (emp.first_name + ' ' + emp.last_name).trim();
        document.getElementById('onb-emp-meta').textContent = (emp.job_title || '') + (emp.department_name ? ' • ' + emp.department_name : '');
        var items = onbRes.items || [];
        var completed = items.filter(function(i) { return i.is_completed; }).length;
        var pct = items.length ? Math.round((completed / items.length) * 100) : 0;
        var barColor = pct === 100 ? 'var(--success-color)' : 'var(--primary-color)';
        document.getElementById('onb-emp-progress').innerHTML =
            '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">' +
                '<span style="font-size:0.85rem;color:var(--text-secondary);">Progress</span>' +
                '<span style="font-weight:600;color:' + barColor + ';">' + pct + '% (' + completed + '/' + items.length + ')</span>' +
            '</div>' +
            '<div style="height:8px;background:rgba(255,255,255,0.08);border-radius:4px;overflow:hidden;">' +
                '<div style="height:100%;width:' + pct + '%;background:' + barColor + ';border-radius:4px;transition:width 0.4s;"></div>' +
            '</div>';
        var list = document.getElementById('onb-emp-items');
        list.innerHTML = '';
        var categories = {};
        items.forEach(function(i) {
            var cat = i.category || 'General';
            if (!categories[cat]) categories[cat] = [];
            categories[cat].push(i);
        });
        for (var cat in categories) {
            list.insertAdjacentHTML('beforeend', '<div style="font-weight:600;font-size:0.82rem;color:var(--text-secondary);margin:12px 0 6px;text-transform:uppercase;letter-spacing:0.5px;">' + cat + '</div>');
            categories[cat].forEach(function(item) {
                var isOverdue = !item.is_completed && item.due_date && item.due_date < new Date().toISOString().split('T')[0];
                list.insertAdjacentHTML('beforeend',
                    '<div style="display:flex;align-items:center;gap:12px;padding:10px 12px;border:1px solid var(--border-color);border-radius:8px;margin-bottom:6px;background:rgba(255,255,255,0.02);">' +
                        '<input type="checkbox" ' + (item.is_completed ? 'checked' : '') + ' onchange="toggleOnbItem(' + item.id + ', this.checked)" style="accent-color:var(--primary-color);cursor:pointer;">' +
                        '<div style="flex:1;min-width:0;">' +
                            '<div style="font-size:0.9rem;' + (item.is_completed ? 'text-decoration:line-through;color:var(--text-secondary);' : '') + '">' + item.title + '</div>' +
                            '<div style="font-size:0.75rem;color:var(--text-secondary);">' + (item.assigned_to || '') + (item.due_date ? ' • Due ' + item.due_date : '') + (isOverdue ? ' <span style="color:var(--danger-color);">OVERDUE</span>' : '') + '</div>' +
                        '</div>' +
                        '<button onclick="deleteOnbItem(' + item.id + ')" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;padding:4px;" title="Delete">' +
                            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                        '</button>' +
                    '</div>'
                );
            });
        }
        if (items.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text-secondary);">No onboarding items yet. Click "+ Add Item" to get started.</div>';
        }
        document.getElementById('onb-emp-modal').dataset.empId = empId;
        document.getElementById('onb-emp-modal').style.display = 'flex';
    } catch (e) { showToast('Failed to load details', 'error'); }
}
window.openOnbEmpDetail = openOnbEmpDetail;

function closeOnbEmpModal() {
    document.getElementById('onb-emp-modal').style.display = 'none';
}
window.closeOnbEmpModal = closeOnbEmpModal;

async function toggleOnbItem(itemId, isCompleted) {
    try {
        await fetch('/api/onboarding/' + itemId, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_completed: isCompleted }) });
        var empId = document.getElementById('onb-emp-modal').dataset.empId;
        if (empId) openOnbEmpDetail(parseInt(empId));
        loadOnboardingHub();
    } catch (e) { showToast('Failed to update', 'error'); }
}
window.toggleOnbItem = toggleOnbItem;

async function deleteOnbItem(itemId) {
    if (!confirm('Delete this item?')) return;
    try {
        await fetch('/api/onboarding/' + itemId, { method: 'DELETE' });
        var empId = document.getElementById('onb-emp-modal').dataset.empId;
        if (empId) openOnbEmpDetail(parseInt(empId));
        loadOnboardingHub();
    } catch (e) { showToast('Failed to delete', 'error'); }
}
window.deleteOnbItem = deleteOnbItem;

async function addOnbItemToEmp() {
    var empId = document.getElementById('onb-emp-modal').dataset.empId;
    if (!empId) return;
    var title = prompt('Task title:');
    if (!title) return;
    var category = prompt('Category (e.g. Legal, IT, General):') || 'General';
    var assignee = prompt('Assigned to:') || '';
    var dueDate = prompt('Due date (YYYY-MM-DD, optional):') || '';
    try {
        await fetch('/api/employees/' + empId + '/onboarding', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title, category: category, assigned_to: assignee, due_date: dueDate })
        });
        openOnbEmpDetail(parseInt(empId));
        loadOnboardingHub();
    } catch (e) { showToast('Failed to add item', 'error'); }
}
window.addOnbItemToEmp = addOnbItemToEmp;

async function showBulkOnboardModal() {
    try {
        var res = await fetch('/api/employees?status=onboarding');
        var emps = await res.json();
        var select = document.getElementById('bulk-emp-select');
        select.innerHTML = '';
        emps.forEach(function(e) {
            select.insertAdjacentHTML('beforeend',
                '<label style="display:flex;align-items:center;gap:8px;padding:8px;border-radius:6px;cursor:pointer;transition:background 0.15s;">' +
                    '<input type="checkbox" value="' + e.id + '" class="bulk-emp-check" style="accent-color:var(--primary-color);">' +
                    '<span style="font-size:0.9rem;">' + (e.first_name + ' ' + e.last_name).trim() + '</span>' +
                    '<span style="font-size:0.75rem;color:var(--text-secondary);">' + (e.department_name || '') + '</span>' +
                '</label>'
            );
        });
        if (emps.length === 0) {
            select.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);">No onboarding employees found</div>';
        }
        onboardingBulkItems = [];
        document.getElementById('bulk-items-preview').style.display = 'none';
        document.getElementById('bulk-onboard-modal').style.display = 'flex';
    } catch (e) { showToast('Failed to load employees', 'error'); }
}
window.showBulkOnboardModal = showBulkOnboardModal;

function closeBulkOnboardModal() {
    document.getElementById('bulk-onboard-modal').style.display = 'none';
}
window.closeBulkOnboardModal = closeBulkOnboardModal;

function loadBulkDefault() {
    onboardingBulkItems = [
        { title: 'Sign employment contract', category: 'Legal', assigned_to: 'HR' },
        { title: 'Provide government-issued ID', category: 'Legal', assigned_to: 'HR' },
        { title: 'Submit bank details for payroll', category: 'Finance', assigned_to: 'Finance' },
        { title: 'Provide emergency contact information', category: 'General', assigned_to: 'HR' },
        { title: 'Company policy acknowledgment', category: 'Compliance', assigned_to: 'HR' },
        { title: 'IT equipment setup', category: 'Technical', assigned_to: 'IT' },
        { title: 'Email and system access setup', category: 'Technical', assigned_to: 'IT' },
        { title: 'Introduction to team members', category: 'Social', assigned_to: 'Manager' },
        { title: 'Complete tax withholding forms', category: 'Finance', assigned_to: 'Finance' },
        { title: 'Review employee handbook', category: 'Compliance', assigned_to: 'HR' },
    ];
    renderBulkItemsPreview();
}
window.loadBulkDefault = loadBulkDefault;

async function loadBulkFromTemplate() {
    try {
        var res = await fetch('/api/onboarding/templates');
        var templates = await res.json();
        if (templates.length === 0) { showToast('No templates found. Create one first.', 'error'); return; }
        var names = templates.map(function(t, i) { return (i + 1) + '. ' + t.name; }).join('\n');
        var choice = prompt('Choose template:\n' + names + '\nEnter number:');
        if (!choice) return;
        var idx = parseInt(choice) - 1;
        if (idx >= 0 && idx < templates.length) {
            onboardingBulkItems = templates[idx].items || [];
            renderBulkItemsPreview();
        }
    } catch (e) { showToast('Failed to load templates', 'error'); }
}
window.loadBulkFromTemplate = loadBulkFromTemplate;

function renderBulkItemsPreview() {
    var preview = document.getElementById('bulk-items-preview');
    var list = document.getElementById('bulk-items-list');
    preview.style.display = 'block';
    list.innerHTML = '';
    onboardingBulkItems.forEach(function(item) {
        list.insertAdjacentHTML('beforeend',
            '<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;font-size:0.85rem;border-bottom:1px solid var(--border-color);">' +
                '<span style="color:var(--primary-color);">&#10003;</span>' +
                '<span style="flex:1;">' + item.title + '</span>' +
                '<span style="font-size:0.72rem;color:var(--text-secondary);">' + (item.category || '') + '</span>' +
            '</div>'
        );
    });
}
window.renderBulkItemsPreview = renderBulkItemsPreview;

async function applyBulkOnboard() {
    var empIds = [];
    document.querySelectorAll('.bulk-emp-check:checked').forEach(function(cb) { empIds.push(parseInt(cb.value)); });
    if (empIds.length === 0) { showToast('Select at least one employee', 'error'); return; }
    if (onboardingBulkItems.length === 0) { showToast('Load a checklist first', 'error'); return; }
    try {
        var res = await fetch('/api/onboarding/apply-template', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ employee_ids: empIds, items: onboardingBulkItems })
        });
        var data = await res.json();
        if (res.ok) { showToast(data.message, 'success'); closeBulkOnboardModal(); loadOnboardingHub(); }
        else { showToast(data.detail || 'Error', 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.applyBulkOnboard = applyBulkOnboard;

async function showOnboardingTemplates() {
    try {
        var res = await fetch('/api/onboarding/templates');
        var templates = await res.json();
        var list = document.getElementById('onb-templates-list');
        list.innerHTML = '';
        if (templates.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-secondary);">No templates yet. Create one to reuse checklists.</div>';
        } else {
            templates.forEach(function(t) {
                list.insertAdjacentHTML('beforeend',
                    '<div style="display:flex;align-items:center;justify-content:space-between;padding:12px;border:1px solid var(--border-color);border-radius:8px;margin-bottom:8px;">' +
                        '<div><div style="font-weight:600;">' + t.name + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + (t.items ? t.items.length : 0) + ' items</div></div>' +
                        '<button onclick="deleteOnbTemplate(' + t.id + ')" style="background:none;border:none;color:var(--danger-color);cursor:pointer;padding:4px;" title="Delete">' +
                            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>' +
                        '</button>' +
                    '</div>'
                );
            });
        }
        document.getElementById('onb-templates-modal').style.display = 'flex';
    } catch (e) { showToast('Failed to load templates', 'error'); }
}
window.showOnboardingTemplates = showOnboardingTemplates;

function closeOnbTemplatesModal() {
    document.getElementById('onb-templates-modal').style.display = 'none';
}
window.closeOnbTemplatesModal = closeOnbTemplatesModal;

async function createNewTemplate() {
    var name = prompt('Template name:');
    if (!name) return;
    var itemsJson = prompt('Enter items (one per line, format: Title | Category | Assigned To):');
    if (!itemsJson) return;
    var items = itemsJson.split('\n').map(function(line) {
        var parts = line.split('|').map(function(s) { return s.trim(); });
        return { title: parts[0] || '', category: parts[1] || 'General', assigned_to: parts[2] || '' };
    }).filter(function(i) { return i.title; });
    try {
        var res = await fetch('/api/onboarding/templates', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, items: items })
        });
        if (res.ok) { showToast('Template created', 'success'); showOnboardingTemplates(); }
        else { showToast('Failed', 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.createNewTemplate = createNewTemplate;

async function deleteOnbTemplate(id) {
    if (!confirm('Delete this template?')) return;
    try {
        await fetch('/api/onboarding/templates/' + id, { method: 'DELETE' });
        showOnboardingTemplates();
    } catch (e) { showToast('Failed', 'error'); }
}
window.deleteOnbTemplate = deleteOnbTemplate;

// --- Payslips ---
async function fetchPayslips(statusFilter) {
    try {
        var url = '/api/payslips';
        if (statusFilter) url += '?status=' + encodeURIComponent(statusFilter);
        var res = await fetch(url);
        if (!res.ok) throw new Error('Failed');
        allPayslips = await res.json();
        renderPayslips(allPayslips);
        var countEl = document.getElementById('payslip-count');
        if (countEl) countEl.textContent = allPayslips.length + ' item' + (allPayslips.length !== 1 ? 's' : '');
    } catch (e) {
        var tbody = document.getElementById('payslips-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="10" class="loading">Failed to load payslips.</td></tr>';
    }
}

function renderPayslips(payslips) {
    var tbody = document.getElementById('payslips-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (payslips.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-secondary);">No payslips found.</td></tr>';
        return;
    }
    payslips.forEach(function(p) {
        var statusClass = (p.status || '').toLowerCase();
        var opens = p.open_count || 0;
        var openBadge = opens > 0 ? '<span style="color:var(--primary-color);font-weight:600;">' + opens + '</span>' : '<span style="color:var(--text-secondary);">0</span>';
        tbody.insertAdjacentHTML('beforeend', '<tr><td><a href="#" class="link" onclick="event.preventDefault();viewPayslip(' + p.id + ')">' + p.number + '</a></td><td>' + (p.employee_name || '-') + '</td><td>' + (p.period_start || '') + ' to ' + (p.period_end || '') + '</td><td>' + (p.pay_date || '-') + '</td><td class="text-right">' + formatCurrency(p.gross_pay) + '</td><td class="text-right">' + formatCurrency(p.total_deductions) + '</td><td class="text-right">' + formatCurrency(p.net_pay) + '</td><td><span class="status-pill status-' + statusClass + '">' + p.status + '</span></td><td>' + (p.sent || '-') + '</td><td class="text-right">' + openBadge + '</td></tr>');
    });
}

function filterPayslips(status, btn) {
    currentPsFilter = status;
    document.querySelectorAll('#payroll-view .invoices-tabs .tab').forEach(function(t) { t.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    if (status) {
        var filtered = allPayslips.filter(function(p) { return p.status === status; });
        renderPayslips(filtered);
    } else {
        renderPayslips(allPayslips);
    }
}
window.filterPayslips = filterPayslips;

// --- View Payslip ---
async function viewPayslip(psId) {
    currentPayslipId = psId;
    try {
        var res = await fetch('/api/payslips/' + psId);
        if (!res.ok) throw new Error('Failed');
        var ps = await res.json();
        document.getElementById('ps-detail-title').textContent = 'Payslip ' + ps.number;
        document.getElementById('ps-detail-status').textContent = ps.status;
        document.getElementById('ps-detail-status').className = 'status-pill status-' + (ps.status || '').toLowerCase();
        document.getElementById('ps-detail-number').textContent = ps.number;
        document.getElementById('ps-detail-emp-name').textContent = ps.employee ? ps.employee.full_name : '-';
        document.getElementById('ps-detail-period').textContent = ps.period_start + ' to ' + ps.period_end;
        document.getElementById('ps-detail-pay-date').textContent = ps.pay_date || '-';
        document.getElementById('ps-detail-net').textContent = (ps.net_pay || 0).toFixed(2);
        document.getElementById('ps-detail-company').textContent = ps.company ? ps.company.name || '-' : '-';
        document.getElementById('ps-detail-company-addr').textContent = ps.company ? (ps.company.address || '') : '';

        document.getElementById('ps-detail-basic').textContent = (ps.basic_salary || 0).toFixed(2);
        document.getElementById('ps-detail-otpay').textContent = (ps.overtime_pay || 0).toFixed(2);
        document.getElementById('ps-detail-bonus').textContent = (ps.bonus || 0).toFixed(2);
        document.getElementById('ps-detail-allow').textContent = (ps.allowances || 0).toFixed(2);
        document.getElementById('ps-detail-gross').textContent = (ps.gross_pay || 0).toFixed(2);
        document.getElementById('ps-detail-tax').textContent = (ps.tax_amount || 0).toFixed(2);
        document.getElementById('ps-detail-ins').textContent = (ps.insurance || 0).toFixed(2);
        document.getElementById('ps-detail-ret').textContent = (ps.retirement || 0).toFixed(2);
        document.getElementById('ps-detail-other').textContent = (ps.other_deductions || 0).toFixed(2);
        document.getElementById('ps-detail-dedtotal').textContent = (ps.total_deductions || 0).toFixed(2);
        document.getElementById('ps-detail-net-big').textContent = '$' + (ps.net_pay || 0).toFixed(2);

        var notesEl = document.getElementById('ps-detail-notes');
        if (ps.notes) { notesEl.style.display = 'block'; document.getElementById('ps-detail-notes-text').textContent = ps.notes; }
        else { notesEl.style.display = 'none'; }

        var logoEl = document.getElementById('ps-logo');
        if (ps.company && ps.company.logo_url) { logoEl.src = ps.company.logo_url; logoEl.style.display = 'block'; }
        else { logoEl.style.display = 'none'; }

        showView('payslip-detail-view');
    } catch (e) {
        showToast('Failed to load payslip', 'error');
    }
}
window.viewPayslip = viewPayslip;

// --- Generate Payslip ---
async function showGeneratePayslipModal() {
    document.getElementById('generate-payslip-modal').style.display = 'flex';
    document.getElementById('generate-payslip-form').reset();
    document.getElementById('ps-preview').style.display = 'none';
    var empContainer = document.getElementById('ps-employee-id-container');
    if (empContainer) {
        empContainer.innerHTML = '<input type="hidden" id="ps-employee-id" value="' + (currentEmployeeId || '') + '">';
    }
    var today = new Date();
    var firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
    var lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
    document.getElementById('ps-period-start').value = firstDay;
    document.getElementById('ps-period-end').value = lastDay;
    document.getElementById('ps-pay-date').value = today.toISOString().split('T')[0];
    if (currentEmployeeId) setTimeout(function() { autoFetchPayDetails(); }, 200);
}
window.showGeneratePayslipModal = showGeneratePayslipModal;

async function showGeneratePayslipModalForNew() {
    document.getElementById('generate-payslip-modal').style.display = 'flex';
    document.getElementById('generate-payslip-form').reset();
    document.getElementById('ps-preview').style.display = 'none';
    var today = new Date();
    var firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
    var lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split('T')[0];
    document.getElementById('ps-period-start').value = firstDay;
    document.getElementById('ps-period-end').value = lastDay;
    document.getElementById('ps-pay-date').value = today.toISOString().split('T')[0];
    var empContainer = document.getElementById('ps-employee-id-container');
    if (!empContainer) return;
    try {
        var empRes = await fetch('/api/employees');
        var emps = await empRes.json();
        empContainer.innerHTML = '<select id="ps-employee-id" class="form-control" onchange="autoFetchPayDetails()"><option value="">Select employee...</option></select>';
        var sel = document.getElementById('ps-employee-id');
        emps.forEach(function(e) { sel.insertAdjacentHTML('beforeend', '<option value="' + e.id + '">' + e.first_name + ' ' + e.last_name + '</option>'); });
    } catch (e) { console.error(e); empContainer.innerHTML = '<select id="ps-employee-id" class="form-control"><option value="">Failed to load employees</option></select>'; }
}
window.showGeneratePayslipModalForNew = showGeneratePayslipModalForNew;

function closeGeneratePayslipModal() {
    document.getElementById('generate-payslip-modal').style.display = 'none';
}
window.closeGeneratePayslipModal = closeGeneratePayslipModal;

var currentPayDetails = null;
async function autoFetchPayDetails() {
    var empId = document.getElementById('ps-employee-id').value;
    var periodStart = document.getElementById('ps-period-start').value;
    var periodEnd = document.getElementById('ps-period-end').value;
    if (!empId || !periodStart || !periodEnd) return;
    try {
        var url = '/api/employees/' + empId + '/pay-details?period_start=' + periodStart + '&period_end=' + periodEnd;
        var res = await fetch(url);
        if (!res.ok) return;
        currentPayDetails = await res.json();
        document.getElementById('ps-basic').value = currentPayDetails.salary || 0;
        document.getElementById('ps-hours').value = currentPayDetails.hours_worked || 0;
        document.getElementById('ps-ot-hours').value = currentPayDetails.overtime_hours || 0;
        document.getElementById('ps-ot-rate').value = currentPayDetails.overtime_rate || 0;
        document.getElementById('ps-bonus').value = currentPayDetails.bonus || 0;
        document.getElementById('ps-allowances').value = currentPayDetails.allowances || 0;
        recalcPayslip();
    } catch (e) { console.error('Failed to fetch pay details:', e); }
}
window.autoFetchPayDetails = autoFetchPayDetails;

function recalcPayslip() {
    var basic = parseFloat(document.getElementById('ps-basic').value) || 0;
    var otHours = parseFloat(document.getElementById('ps-ot-hours').value) || 0;
    var otRate = parseFloat(document.getElementById('ps-ot-rate').value) || 0;
    var bonus = parseFloat(document.getElementById('ps-bonus').value) || 0;
    var allowances = parseFloat(document.getElementById('ps-allowances').value) || 0;
    var insurance = parseFloat(document.getElementById('ps-insurance').value) || 0;
    var retirement = parseFloat(document.getElementById('ps-retirement').value) || 0;
    var otherDed = parseFloat(document.getElementById('ps-other-ded').value) || 0;
    var hoursWorked = parseFloat(document.getElementById('ps-hours').value) || 0;
    var otPay = otHours * otRate;
    var gross = basic + otPay + bonus + allowances;
    var taxRate = currentPayDetails ? (currentPayDetails.tax_rate || 0) : 0;
    var empDeductions = currentPayDetails ? (currentPayDetails.deductions || 0) : 0;
    var tax = Math.round(gross * (taxRate / 100) * 100) / 100;
    var totalDed = tax + empDeductions + insurance + retirement + otherDed;
    var net = Math.round((gross - totalDed) * 100) / 100;
    document.getElementById('prev-basic').textContent = '$' + basic.toLocaleString();
    document.getElementById('prev-ot').textContent = '$' + otPay.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('prev-bonus').textContent = '$' + bonus.toLocaleString();
    document.getElementById('prev-allow').textContent = '$' + allowances.toLocaleString();
    document.getElementById('prev-gross').textContent = '$' + gross.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('prev-tax').textContent = '$' + tax.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('prev-ded').textContent = '$' + (empDeductions + insurance + retirement + otherDed).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('prev-net').textContent = '$' + net.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2});
    document.getElementById('ps-preview').style.display = 'block';
    var attInfo = document.getElementById('prev-attendance');
    if (currentPayDetails && attInfo) {
        var parts = [];
        if (hoursWorked > 0) parts.push(hoursWorked + 'h worked');
        if (currentPayDetails.overtime_hours > 0) parts.push(currentPayDetails.overtime_hours + 'h overtime');
        attInfo.textContent = parts.length ? 'Attendance: ' + parts.join(', ') : 'No attendance records for this period';
    }
}
window.recalcPayslip = recalcPayslip;

async function submitGeneratePayslip() {
    var empIdVal = document.getElementById('ps-employee-id').value;
    if (!empIdVal) { showToast('Select an employee', 'error'); return; }
    var payload = {
        employee_id: parseInt(empIdVal),
        period_start: document.getElementById('ps-period-start').value,
        period_end: document.getElementById('ps-period-end').value,
        pay_date: document.getElementById('ps-pay-date').value,
        hours_worked: parseFloat(document.getElementById('ps-hours').value) || 0,
        basic_salary: parseFloat(document.getElementById('ps-basic').value) || 0,
        overtime_hours: parseFloat(document.getElementById('ps-ot-hours').value) || 0,
        overtime_rate: parseFloat(document.getElementById('ps-ot-rate').value) || 0,
        bonus: parseFloat(document.getElementById('ps-bonus').value) || 0,
        allowances: parseFloat(document.getElementById('ps-allowances').value) || 0,
        insurance: parseFloat(document.getElementById('ps-insurance').value) || 0,
        retirement: parseFloat(document.getElementById('ps-retirement').value) || 0,
        other_deductions: parseFloat(document.getElementById('ps-other-ded').value) || 0,
        notes: document.getElementById('ps-notes').value,
    };
    try {
        var res = await fetch('/api/payslips', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var data = await res.json();
        if (res.ok) {
            showToast(data.message || 'Payslip created', 'success');
            closeGeneratePayslipModal();
            if (currentEmployeeId) viewEmployee(currentEmployeeId);
            fetchPayslips(currentPsFilter);
        } else {
            showToast('Failed: ' + (data.detail || 'Error'), 'error');
        }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.submitGeneratePayslip = submitGeneratePayslip;

// --- Payslip Actions ---
async function sendPayslipEmail() {
    if (!currentPayslipId) return;
    var logoData = localStorage.getItem('company_logo') || '';
    var pdfB64 = '';
    try {
        var doc = generatePayslipPDF();
        pdfB64 = doc.output('datauristring').split(',')[1];
    } catch (e) { console.error('PDF generation failed:', e); }
    try {
        var res = await fetch('/api/payslips/' + currentPayslipId + '/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ logo_data: logoData, pdf_data: pdfB64 })
        });
        var data = await res.json();
        if (res.ok) { showToast('Payslip email sent with PDF!', 'success'); viewPayslip(currentPayslipId); }
        else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.sendPayslipEmail = sendPayslipEmail;

async function markPayslipPaid() {
    if (!currentPayslipId) return;
    if (!confirm('Mark payslip as paid?')) return;
    try {
        var res = await fetch('/api/payslips/' + currentPayslipId + '/mark-paid', { method: 'POST' });
        if (res.ok) { showToast('Marked as paid', 'success'); viewPayslip(currentPayslipId); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.markPayslipPaid = markPayslipPaid;

async function deletePayslip() {
    if (!currentPayslipId) return;
    if (!confirm('Delete this payslip?')) return;
    try {
        var res = await fetch('/api/payslips/' + currentPayslipId, { method: 'DELETE' });
        if (res.ok) { showToast('Payslip deleted', 'success'); showView('payroll-view'); fetchPayslips(currentPsFilter); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.deletePayslip = deletePayslip;

// --- Payslip PDF ---
function generatePayslipPDF() {
    var jsPDF = window.jspdf.jsPDF;
    var doc = new jsPDF({ unit: 'pt', format: 'letter' });
    var w = 612, h = 792;
    var margin = 48;
    var y = 0;
    var valueColor = [30, 41, 59];
    var subColor = [100, 116, 139];
    var labelColor = [148, 163, 184];

    var company = document.getElementById('ps-detail-company').textContent || '';
    var companyAddr = document.getElementById('ps-detail-company-addr').textContent || '';
    var number = document.getElementById('ps-detail-number').textContent || '';
    var empName = document.getElementById('ps-detail-emp-name').textContent || '';
    var period = document.getElementById('ps-detail-period').textContent || '';
    var payDate = document.getElementById('ps-detail-pay-date').textContent || '';
    var basic = document.getElementById('ps-detail-basic').textContent || '0.00';
    var otpay = document.getElementById('ps-detail-otpay').textContent || '0.00';
    var bonus = document.getElementById('ps-detail-bonus').textContent || '0.00';
    var allow = document.getElementById('ps-detail-allow').textContent || '0.00';
    var gross = document.getElementById('ps-detail-gross').textContent || '0.00';
    var tax = document.getElementById('ps-detail-tax').textContent || '0.00';
    var ins = document.getElementById('ps-detail-ins').textContent || '0.00';
    var ret = document.getElementById('ps-detail-ret').textContent || '0.00';
    var other = document.getElementById('ps-detail-other').textContent || '0.00';
    var dedTotal = document.getElementById('ps-detail-dedtotal').textContent || '0.00';
    var netPay = document.getElementById('ps-detail-net').textContent || '0.00';
    var savedLogo = localStorage.getItem('company_logo') || '';

    // === HEADER BAR ===
    doc.setFillColor(15, 23, 42);
    doc.rect(0, 0, w, 90, 'F');
    doc.setFillColor(16, 185, 129);
    doc.rect(0, 86, w, 4, 'F');

    if (savedLogo) {
        try { doc.addImage(savedLogo, 'PNG', margin, 22, 110, 36); } catch(e) {}
    }

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(30);
    doc.setTextColor(255, 255, 255);
    doc.text('PAYSLIP', w - margin, 38, { align: 'right' });
    doc.setFontSize(11);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(148, 163, 184);
    doc.text(number, w - margin, 56, { align: 'right' });
    doc.setFontSize(9);
    doc.setTextColor(100, 116, 139);
    if (company) doc.text(company, w - margin, 72, { align: 'right' });
    y = 108;

    // === EMPLOYEE INFO ===
    var leftX = margin;
    var rightX = w / 2 + 20;

    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(labelColor[0], labelColor[1], labelColor[2]);
    doc.text('EMPLOYEE', leftX, y);
    doc.text('PAYMENT DETAILS', rightX, y);
    y += 14;

    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(valueColor[0], valueColor[1], valueColor[2]);
    doc.text(empName || '-', leftX, y);
    y += 16;

    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(subColor[0], subColor[1], subColor[2]);
    if (companyAddr) { doc.text(companyAddr.substring(0, 45), leftX, y); y += 13; }
    if (company) { doc.text(company, leftX, y); y += 13; }

    var pdY = 122;
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(subColor[0], subColor[1], subColor[2]);
    doc.text('Period:', rightX, pdY);
    doc.text('Pay Date:', rightX, pdY + 16);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(valueColor[0], valueColor[1], valueColor[2]);
    doc.text(period || '-', rightX + 56, pdY);
    doc.text(payDate || '-', rightX + 56, pdY + 16);

    y = Math.max(y, pdY + 40) + 16;

    // === EARNINGS TABLE ===
    doc.setFillColor(15, 23, 42);
    doc.roundedRect(margin, y, w - margin * 2, 24, 4, 4, 'F');
    y += 16;
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(200, 200, 220);
    doc.text('EARNINGS', margin + 10, y);
    doc.text('AMOUNT', w - margin - 10, y, { align: 'right' });
    y += 12;

    var earnings = [['Basic Salary', basic], ['Overtime Pay', otpay], ['Bonus', bonus], ['Allowances', allow]];
    earnings.forEach(function(r, i) {
        if (i % 2 === 0) {
            doc.setFillColor(248, 250, 252);
            doc.rect(margin, y - 9, w - margin * 2, 22, 'F');
        }
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(51, 51, 51);
        doc.text(r[0], margin + 10, y);
        doc.text(r[1], w - margin - 10, y, { align: 'right' });
        y += 22;
    });

    // Gross Pay row
    doc.setFillColor(236, 253, 245);
    doc.roundedRect(margin, y - 9, w - margin * 2, 26, 4, 4, 'F');
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(5, 150, 105);
    doc.text('Gross Pay', margin + 10, y + 4);
    doc.text(gross, w - margin - 10, y + 4, { align: 'right' });
    y += 34;

    // === DEDUCTIONS TABLE ===
    doc.setFillColor(15, 23, 42);
    doc.roundedRect(margin, y, w - margin * 2, 24, 4, 4, 'F');
    y += 16;
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(200, 200, 220);
    doc.text('DEDUCTIONS', margin + 10, y);
    doc.text('AMOUNT', w - margin - 10, y, { align: 'right' });
    y += 12;

    var deductions = [['Tax', tax], ['Insurance', ins], ['Retirement', ret], ['Other Deductions', other]];
    deductions.forEach(function(r, i) {
        if (i % 2 === 0) {
            doc.setFillColor(248, 250, 252);
            doc.rect(margin, y - 9, w - margin * 2, 22, 'F');
        }
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(51, 51, 51);
        doc.text(r[0], margin + 10, y);
        doc.setTextColor(220, 38, 38);
        doc.text(r[1], w - margin - 10, y, { align: 'right' });
        y += 22;
    });

    // Total Deductions row
    doc.setFillColor(254, 226, 226);
    doc.roundedRect(margin, y - 9, w - margin * 2, 26, 4, 4, 'F');
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(220, 38, 38);
    doc.text('Total Deductions', margin + 10, y + 4);
    doc.text(dedTotal, w - margin - 10, y + 4, { align: 'right' });
    y += 40;

    // === NET PAY BOX ===
    doc.setFillColor(15, 23, 42);
    doc.roundedRect(margin, y, w - margin * 2, 56, 8, 8, 'F');
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(148, 163, 184);
    doc.text('NET PAY', margin + 20, y + 22);
    doc.setFontSize(24);
    doc.setTextColor(16, 185, 129);
    doc.text('$' + netPay, w - margin - 20, y + 30, { align: 'right' });
    y += 70;

    // === FOOTER ===
    var footerY = h - 50;
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(margin, footerY, w - margin, footerY);
    footerY += 16;
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(148, 163, 184);
    doc.text('This is a computer-generated payslip. No signature required.', w / 2, footerY, { align: 'center' });
    footerY += 14;
    doc.setFontSize(8);
    doc.setTextColor(203, 213, 225);
    if (company) doc.text(company + (companyAddr ? '  •  ' + companyAddr : ''), w / 2, footerY, { align: 'center' });

    return doc;
}

function downloadPayslipPDF() {
    var number = document.getElementById('ps-detail-number').textContent || 'payslip';
    var doc = generatePayslipPDF();
    doc.save(number + '.pdf');
}
window.downloadPayslipPDF = downloadPayslipPDF;

// ============================================================
// ATTENDANCE MODULE
// ============================================================

var allAttendance = [];

async function loadAttendanceStats() {
    try {
        var res = await fetch('/api/attendance/stats');
        if (!res.ok) return;
        var s = await res.json();
        var el = function(id) { return document.getElementById(id); };
        if (el('att-total')) el('att-total').textContent = s.total_employees || 0;
        if (el('att-present')) el('att-present').textContent = s.present || 0;
        if (el('att-absent')) el('att-absent').textContent = s.absent || 0;
        if (el('att-avg-hours')) el('att-avg-hours').textContent = (s.avg_hours || 0) + 'h';
    } catch (e) { console.error('Attendance stats error:', e); }
}

async function loadAttendanceButtons() {
    try {
        var res = await fetch('/api/employees');
        if (!res.ok) return;
        var emps = await res.json();
        var container = document.getElementById('att-employee-buttons');
        if (!container) return;
        container.innerHTML = '';
        var activeEmps = emps.filter(function(e) { return e.status === 'active' || e.status === 'onboarding'; });
        if (activeEmps.length === 0) {
            container.innerHTML = '<div style="color:var(--text-secondary);font-size:0.9rem;">No active employees. Add employees first.</div>';
            return;
        }
        activeEmps.forEach(function(e) {
            var initials = (e.first_name[0] || '') + (e.last_name[0] || '');
            container.insertAdjacentHTML('beforeend', '<div style="display:flex;align-items:center;gap:12px;padding:12px 16px;background:rgba(255,255,255,0.03);border:1px solid var(--border-color);border-radius:var(--radius-md);min-width:280px;"><div style="width:40px;height:40px;border-radius:50%;background:var(--primary-color);color:#0b0f19;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85rem;flex-shrink:0;">' + initials + '</div><div style="flex:1;min-width:0;"><div style="font-weight:600;font-size:0.9rem;">' + e.first_name + ' ' + e.last_name + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + (e.job_title || e.email || '') + '</div></div><button class="btn btn-outline btn-sm" onclick="clockInOut(' + e.id + ')" id="att-btn-' + e.id + '" style="flex-shrink:0;">Clock In</button></div>');
        });
    } catch (e) { console.error('Attendance buttons error:', e); }
}

async function clockInOut(empId) {
    var btn = document.getElementById('att-btn-' + empId);
    var now = new Date();
    var timeStr = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
    var todayRecords = allAttendance.filter(function(r) { return r.employee_id === empId; });
    var todayRecord = todayRecords.find(function(r) { return r.date === new Date().toISOString().split('T')[0]; });
    try {
        if (!todayRecord || !todayRecord.clock_in) {
            var res = await fetch('/api/attendance/clock-in', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ employee_id: empId })
            });
            var data = await res.json();
            if (res.ok) { showToast(data.message, 'success'); }
            else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); return; }
        } else if (!todayRecord.clock_out) {
            var res = await fetch('/api/attendance/clock-out', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ employee_id: empId })
            });
            var data = await res.json();
            if (res.ok) { showToast(data.message + ' (' + data.total_hours + 'h)', 'success'); }
            else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); return; }
        } else {
            showToast('Already clocked out today', 'warning');
            return;
        }
        loadAttendanceStats();
        loadAttendance();
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.clockInOut = clockInOut;

async function loadAttendance() {
    var dateFilter = document.getElementById('att-date-filter');
    var date = dateFilter ? dateFilter.value : '';
    try {
        var url = '/api/attendance';
        if (date) url += '?date=' + encodeURIComponent(date);
        var res = await fetch(url);
        if (!res.ok) throw new Error('Failed');
        allAttendance = await res.json();
        renderAttendance(allAttendance);
        var countEl = document.getElementById('att-count');
        if (countEl) countEl.textContent = allAttendance.length + ' record' + (allAttendance.length !== 1 ? 's' : '');
    } catch (e) {
        var tbody = document.getElementById('attendance-table-body');
        if (tbody) tbody.innerHTML = '<tr><td colspan="9" class="loading">Failed to load attendance.</td></tr>';
    }
}
window.loadAttendance = loadAttendance;

function renderAttendance(records) {
    var tbody = document.getElementById('attendance-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:var(--text-secondary);">No attendance records found.</td></tr>';
        return;
    }
    records.forEach(function(r) {
        var statusClass = r.status === 'completed' ? 'paid' : r.status === 'present' ? 'sent' : 'draft';
        var typeBadge = r.check_type ? '<span class="status-pill status-' + (r.check_type === 'office' ? 'sent' : r.check_type === 'remote' ? 'paid' : 'draft') + '">' + r.check_type + '</span>' : '-';
        tbody.insertAdjacentHTML('beforeend', '<tr><td><strong>' + r.employee_name + '</strong><br><span style="font-size:0.78rem;color:var(--text-secondary);">' + (r.employee_email || '') + '</span></td><td>' + r.date + '</td><td>' + (r.clock_in || '-') + '</td><td>' + (r.clock_out || '-') + '</td><td class="text-right">' + (r.total_hours ? r.total_hours + 'h' : '-') + '</td><td>' + typeBadge + '</td><td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + (r.location_label || '') + '">' + (r.location_label ? r.location_label.substring(0, 30) : '-') + '</td><td><span class="status-pill status-' + statusClass + '">' + r.status + '</span></td><td class="text-right">' + (!r.clock_out && r.clock_in ? '<button class="btn btn-outline btn-sm" onclick="clockInOut(' + r.employee_id + ')">Clock Out</button>' : '') + '</td></tr>');
    });
}

// --- View Switcher HR hooks ---
async function loadOrgChart() {
    try {
        var res = await fetch('/api/org-chart');
        if (!res.ok) throw new Error('Failed');
        var data = await res.json();
        var container = document.getElementById('orgchart-container');
        if (!container) return;
        container.innerHTML = '';
        if (data.total_employees === 0) {
            container.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:60px;">No employees to display. Add employees first.</div>';
            return;
        }
        // Render by department groups
        var departments = data.departments || {};
        var roots = data.roots || [];
        // Root nodes first
        if (roots.length > 0) {
            var rootSection = document.createElement('div');
            rootSection.style.textAlign = 'center';
            rootSection.style.marginBottom = '40px';
            rootSection.innerHTML = '<h3 style="font-size:0.85rem;color:var(--text-secondary);text-transform:uppercase;letter-spacing:1px;margin-bottom:20px;">Leadership</h3>';
            var rootNodes = document.createElement('div');
            rootNodes.className = 'org-children';
            rootNodes.style.position = 'relative';
            roots.forEach(function(r) {
                rootNodes.innerHTML += renderOrgNode(r);
            });
            rootSection.appendChild(rootNodes);
            container.appendChild(rootSection);
        }
        // Department groups
        for (var deptName in departments) {
            var deptSection = document.createElement('div');
            deptSection.style.textAlign = 'center';
            deptSection.style.marginBottom = '40px';
            deptSection.innerHTML = '<h3 style="font-size:0.85rem;color:var(--primary-color);text-transform:uppercase;letter-spacing:1px;margin-bottom:20px;">' + deptName + '</h3>';
            var deptNodes = document.createElement('div');
            deptNodes.className = 'org-children';
            deptNodes.style.position = 'relative';
            departments[deptName].forEach(function(e) {
                deptNodes.innerHTML += renderOrgNode(e);
            });
            deptSection.appendChild(deptNodes);
            container.appendChild(deptSection);
        }
    } catch (e) {
        var c = document.getElementById('orgchart-container');
        if (c) c.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:60px;">Failed to load org chart.</div>';
    }
}

function renderOrgNode(emp) {
    return '<div class="org-node" onclick="viewEmployee(' + emp.id + ')">' +
        '<div class="org-name">' + emp.name + '</div>' +
        '<div class="org-title">' + (emp.job_title || '-') + '</div>' +
        (emp.department ? '<div class="org-dept">' + emp.department + '</div>' : '') +
        '</div>';
}

// --- View Switcher HR hooks ---
var origShowView = showView;
showView = function(viewId) {
    origShowView(viewId);
    if (viewId === 'employees-view') { fetchEmployees(currentEmpFilter); loadHRStats(); }
    if (viewId === 'departments-view') fetchDepartments();
    if (viewId === 'onboarding-hub-view') loadOnboardingHub();
    if (viewId === 'payroll-view') fetchPayslips(currentPsFilter);
    if (viewId === 'attendance-view') { loadAttendanceStats(); loadAttendanceButtons(); loadAttendance(); loadLiveAttendance(); loadAttendanceSettings(); switchAttTab('live'); }
    if (viewId === 'orgchart-view') loadOrgChart();
    if (viewId === 'recruitment-view') loadRecruitmentForms();
};
window.showView = showView;

// --- Attendance Sub-Tabs ---
function switchAttTab(tab) {
    ['live','history','analytics','overtime','settings'].forEach(t => {
        var el = document.getElementById('att-sub-' + t);
        if (el) el.classList.add('d-none');
        var btn = document.getElementById('att-tab-' + t);
        if (btn) { btn.classList.remove('btn-primary'); btn.classList.add('btn-outline'); btn.style.fontWeight = '400'; }
    });
    var active = document.getElementById('att-sub-' + tab);
    if (active) active.classList.remove('d-none');
    var activeBtn = document.getElementById('att-tab-' + tab);
    if (activeBtn) { activeBtn.classList.remove('btn-outline'); activeBtn.classList.add('btn-primary'); activeBtn.style.fontWeight = '600'; }
    if (tab === 'analytics') loadAttendanceAnalytics();
    if (tab === 'settings') loadAttendanceSettings();
    if (tab === 'overtime') loadOvertimeTab();
}
window.switchAttTab = switchAttTab;

// --- Live Attendance Board ---
async function loadLiveAttendance() {
    try {
        var res = await fetch('/api/attendance/live');
        if (!res.ok) return;
        var data = await res.json();
        var grid = document.getElementById('live-attendance-grid');
        if (!grid) return;
        var colors = { present: '#10b981', absent: '#ef4444', completed: '#3b82f6' };
        var icons = { office: 'bi-building', remote: 'bi-house', field: 'bi-geo', manual: 'bi-clock' };
        var working = 0;
        grid.innerHTML = data.map(function(emp) {
            var isWorking = emp.clock_in && !emp.clock_out;
            if (isWorking) working++;
            var borderColor = isWorking ? '#10b981' : (emp.clock_out ? '#3b82f6' : '#e2e8f0');
            var statusColor = isWorking ? '#10b981' : (emp.clock_out ? '#3b82f6' : '#94a3b8');
            return '<div style="background:#fff;border:2px solid ' + borderColor + ';border-radius:12px;padding:16px;position:relative;">' +
                '<div style="position:absolute;top:12px;right:12px;width:10px;height:10px;border-radius:50%;background:' + statusColor + ';"></div>' +
                '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">' +
                    '<div style="width:40px;height:40px;border-radius:50%;background:' + (isWorking ? '#d1fae5' : '#f1f5f9') + ';display:flex;align-items:center;justify-content:center;font-weight:700;color:' + statusColor + ';">' + emp.full_name.charAt(0) + '</div>' +
                    '<div><div style="font-weight:600;font-size:0.95rem;">' + emp.full_name + '</div>' +
                    '<div style="font-size:0.78rem;color:#64748b;">' + (emp.job_title || emp.department || 'Employee') + '</div></div>' +
                '</div>' +
                '<div style="display:flex;justify-content:space-between;font-size:0.82rem;color:#64748b;">' +
                    '<span><i class="bi bi-clock"></i> ' + (emp.clock_in || '--:--') + '</span>' +
                    '<span><i class="bi bi-clock-history"></i> ' + (emp.clock_out || '--:--') + '</span>' +
                    '<span><i class="bi bi-hourglass-split"></i> ' + (emp.total_hours || 0) + 'h</span>' +
                '</div>' +
                '<div style="margin-top:8px;display:flex;gap:8px;font-size:0.75rem;color:#64748b;">' +
                    (emp.check_type ? '<span><i class="bi ' + (icons[emp.check_type] || 'bi-geo') + '"></i> ' + emp.check_type + '</span>' : '') +
                    (emp.location_label ? '<span title="' + emp.location_label + '"><i class="bi bi-geo-alt"></i></span>' : '') +
                    (emp.ip_address ? '<span title="IP: ' + emp.ip_address + '"><i class="bi bi-wifi"></i></span>' : '') +
                '</div>' +
            '</div>';
        }).join('');
        var el = document.getElementById('att-working');
        if (el) el.textContent = working;
    } catch (e) {}
}
window.loadLiveAttendance = loadLiveAttendance;

// --- Attendance Analytics ---
async function loadAttendanceAnalytics() {
    try {
        var res = await fetch('/api/attendance/analytics?days=30');
        if (!res.ok) return;
        var data = await res.json();
        document.getElementById('ana-avg-hours').textContent = data.avg_daily_hours + 'h';
        document.getElementById('ana-late').textContent = data.late_arrivals;
        document.getElementById('ana-overtime').textContent = data.overtime_sessions;
        document.getElementById('ana-rate').textContent = data.avg_attendance_rate + '%';
        var chart = document.getElementById('analytics-chart');
        if (chart && data.daily) {
            var days = Object.entries(data.daily).slice(-14);
            var maxPresent = Math.max(...days.map(function(d) { return d[1].present; }), 1);
            chart.innerHTML = '<div style="display:flex;align-items:end;gap:4px;height:180px;padding:10px 0;">' +
                days.map(function(d) {
                    var pct = (d[1].present / maxPresent) * 100;
                    return '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;">' +
                        '<div style="font-size:0.7rem;font-weight:600;color:#334155;">' + d[1].present + '</div>' +
                        '<div style="width:100%;height:' + pct + '%;background:linear-gradient(180deg,#4361ee,#3a56d4);border-radius:4px 4px 0 0;min-height:4px;"></div>' +
                        '<div style="font-size:0.65rem;color:#64748b;text-align:center;">' + d[0].slice(5) + '</div>' +
                    '</div>';
                }).join('') +
            '</div>';
        }
    } catch (e) {}
}

// --- Attendance Settings ---
async function loadAttendanceSettings() {
    try {
        var res = await fetch('/api/attendance/settings');
        if (!res.ok) return;
        var data = await res.json();
        document.getElementById('set-office-name').value = data.office_name || 'Head Office';
        document.getElementById('set-radius').value = data.geofence_radius || 200;
        document.getElementById('set-lat').value = data.office_lat || '';
        document.getElementById('set-lng').value = data.office_lng || '';
        document.getElementById('set-start').value = data.work_start || '09:00';
        document.getElementById('set-end').value = data.work_end || '17:30';
        document.getElementById('set-grace').value = data.grace_minutes || 15;
        document.getElementById('set-auto-co').value = data.auto_clockout_hours || 10;
        document.getElementById('set-max-ot').value = data.max_overtime_hours || 4;
        document.getElementById('set-allow-remote').checked = data.allow_remote !== false;
        document.getElementById('set-require-loc').checked = data.require_location !== false;
    } catch (e) {}
}

async function saveAttendanceSettings() {
    try {
        var body = {
            office_name: document.getElementById('set-office-name').value,
            geofence_radius: parseFloat(document.getElementById('set-radius').value) || 200,
            office_lat: parseFloat(document.getElementById('set-lat').value) || 0,
            office_lng: parseFloat(document.getElementById('set-lng').value) || 0,
            work_start: document.getElementById('set-start').value,
            work_end: document.getElementById('set-end').value,
            grace_minutes: parseFloat(document.getElementById('set-grace').value) || 15,
            auto_clockout_hours: parseFloat(document.getElementById('set-auto-co').value) || 10,
            max_overtime_hours: parseFloat(document.getElementById('set-max-ot').value) || 4,
            allow_remote: document.getElementById('set-allow-remote').checked,
            require_location: document.getElementById('set-require-loc').checked,
        };
        var res = await fetch('/api/attendance/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (res.ok) showToast('Settings saved successfully', 'success');
        else showToast('Failed to save settings', 'error');
    } catch (e) { showToast('Error saving settings', 'error'); }
}
window.saveAttendanceSettings = saveAttendanceSettings;

// --- Overtime Management ---
async function loadOvertimeTab() {
    try {
        var empRes = await fetch('/api/employees');
        var emps = await empRes.json();
        var sel = document.getElementById('ot-employee');
        if (sel) {
            sel.innerHTML = '<option value="">Select employee...</option>';
            emps.forEach(function(e) { sel.insertAdjacentHTML('beforeend', '<option value="' + e.id + '">' + e.first_name + ' ' + e.last_name + '</option>'); });
        }
        var otDate = document.getElementById('ot-date');
        if (otDate && !otDate.value) otDate.value = new Date().toISOString().split('T')[0];
        loadOvertimeLogs();
    } catch (e) { console.error(e); }
}

async function announceOvertime() {
    var empId = document.getElementById('ot-employee').value;
    var date = document.getElementById('ot-date').value;
    var hours = parseFloat(document.getElementById('ot-hours').value);
    var reason = document.getElementById('ot-reason').value;
    if (!empId) { showToast('Select an employee', 'error'); return; }
    if (!hours || hours <= 0) { showToast('Enter valid hours', 'error'); return; }
    try {
        var res = await fetch('/api/attendance/overtime/announce', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ employee_id: parseInt(empId), date: date, hours: hours, reason: reason }),
        });
        var data = await res.json();
        if (res.ok) { showToast(data.message, 'success'); loadOvertimeLogs(); }
        else showToast(data.detail || 'Failed', 'error');
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}

async function loadOvertimeLogs() {
    try {
        var res = await fetch('/api/attendance/overtime/logs');
        var logs = await res.json();
        var tbody = document.getElementById('overtime-log-body');
        if (!tbody) return;
        if (logs.length === 0) { tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="padding:30px;color:var(--text-secondary);">No overtime logs</td></tr>'; return; }
        tbody.innerHTML = logs.map(function(l) {
            return '<tr><td><strong>' + l.employee_name + '</strong></td><td>' + l.date + '</td><td><strong>' + l.hours + 'h</strong></td><td>' + (l.reason || '-') + '</td><td>' + (l.announced_by || '-') + '</td><td><span class="status-pill status-sent">' + l.status + '</span></td></tr>';
        }).join('');
    } catch (e) {}
}
window.announceOvertime = announceOvertime;

// --- Export Attendance ---
async function exportAttendance() {
    try {
        var dateFilter = document.getElementById('att-date-filter').value;
        var url = '/api/attendance/export' + (dateFilter ? '?start_date=' + dateFilter + '&end_date=' + dateFilter : '');
        var res = await fetch(url);
        if (!res.ok) return;
        var data = await res.json();
        if (!data.length) { showToast('No records to export', 'warning'); return; }
        var csv = Object.keys(data[0]).join(',') + '\n' + data.map(function(r) {
            return Object.values(r).map(function(v) { return '"' + String(v).replace(/"/g, '""') + '"'; }).join(',');
        }).join('\n');
        var blob = new Blob([csv], { type: 'text/csv' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'attendance-' + (dateFilter || 'all') + '.csv';
        a.click();
        showToast('Exported ' + data.length + ' records', 'success');
    } catch (e) { showToast('Export failed', 'error'); }
}
window.exportAttendance = exportAttendance;

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
    fetchDashboardData();
    fetchInvoices();
    preloadSearchData();
    loadSavedLogo();
    setupLogoUpload();
    if (document.querySelectorAll('.line-item-row').length === 0 && document.getElementById('line-items-body')) {
        addLineItemRow();
    }
    var lineItemsBody = document.getElementById('line-items-body');
    if (lineItemsBody) {
        lineItemsBody.addEventListener('input', function(e) {
            if (e.target.classList.contains('item-qty') || e.target.classList.contains('item-price') || e.target.classList.contains('item-disc')) {
                calculateTotals();
            }
        });
        lineItemsBody.addEventListener('click', function(e) {
            if (e.target.closest('.delete-row')) {
                var row = e.target.closest('.line-item-row');
                if (document.querySelectorAll('.line-item-row').length > 1) {
                    row.remove();
                    calculateTotals();
                }
            }
        });
    }
    // Set default dates
    var today = new Date().toISOString().split('T')[0];
    var dueDate = new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0];
    var issueEl = document.getElementById('inv-issue-date');
    var dueEl = document.getElementById('inv-due-date');
    if (issueEl) issueEl.value = today;
    if (dueEl) dueEl.value = dueDate;

    // Auto-refresh live attendance every 30 seconds when on attendance view
    var attRefreshInterval = null;
    function startAttRefresh() {
        if (attRefreshInterval) return;
        attRefreshInterval = setInterval(function() {
            var attView = document.getElementById('attendance-view');
            if (attView && attView.style.display !== 'none') {
                var liveSub = document.getElementById('att-sub-live');
                if (liveSub && !liveSub.classList.contains('d-none')) {
                    loadLiveAttendance();
                    loadAttendanceStats();
                }
            } else {
                clearInterval(attRefreshInterval);
                attRefreshInterval = null;
            }
        }, 30000);
    }
    startAttRefresh();
});

// ============ RECRUITMENT ============
var recFormFields = [];
var recFormStages = [];
var recEditingFormId = null;
var recCurrentSubId = null;
var recFormsSubId = null;
var recFormsLookup = {};
var recCurrentPipelineStages = [];

async function loadRecruitmentForms() {
    try {
        var res = await fetch('/api/recruitment/forms');
        if (!res.ok) {
            var tbody = document.getElementById('rec-forms-tbody');
            if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="loading" style="padding:24px;"><a href="/api/auth/login" style="color:var(--accent-cyan);">Sign in with Google</a> to manage recruitment forms.</td></tr>';
            return;
        }
        var forms = await res.json();
        recFormsLookup = {};
        forms.forEach(function(f) { recFormsLookup[f.id] = f; });
        var tbody = document.getElementById('rec-forms-tbody');
        if (!forms.length) { tbody.innerHTML = '<tr><td colspan="6" class="loading">No forms yet</td></tr>'; return; }
        tbody.innerHTML = forms.map(function(f) {
            var fields = f.fields ? JSON.parse(f.fields) : [];
            var d = new Date(f.created_at);
            return '<tr>' +
                '<td><strong>' + esc(f.title) + '</strong>' + (f.description ? '<br><span style="font-size:0.8rem;color:var(--text-secondary)">' + esc(f.description) + '</span>' : '') + '</td>' +
                '<td>' + fields.length + '</td>' +
                '<td>' + f.submission_count + '</td>' +
                '<td>' + (f.is_active ? '<span style="color:var(--accent-success);font-weight:600;">Active</span>' : '<span style="color:var(--text-secondary);">Draft</span>') + '</td>' +
                '<td>' + d.toLocaleDateString() + '</td>' +
                '<td style="text-align:right;white-space:nowrap;">' +
                    '<button class="btn btn-outline btn-sm" onclick="showRecFormSubmissions(' + f.id + ')" style="margin-right:6px;">Submissions</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="copyRecFormLink(\'' + f.form_token + '\')" style="margin-right:6px;" title="Copy link">Link</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="editRecForm(' + f.id + ')" style="margin-right:6px;">Edit</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="toggleRecForm(' + f.id + ',' + f.is_active + ')">' + (f.is_active ? 'Deactivate' : 'Activate') + '</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="deleteRecForm(' + f.id + ')" style="color:var(--accent-danger);border-color:var(--accent-danger);">Delete</button>' +
                '</td></tr>';
        }).join('');
    } catch(e) { console.error('loadRecruitmentForms error:', e); }
}

function copyRecFormLink(token) {
    var url = window.location.origin + '/recruitment.html?token=' + token;
    navigator.clipboard.writeText(url).then(function() {
        showToast('Link copied! Share it with candidates.', 'success');
    }).catch(function() {
        prompt('Copy this link:', url);
    });
}

function showAddFormModal() {
    recEditingFormId = null;
    recFormFields = [];
    recFormStages = ['Applied', 'Screening', 'Interview', 'Offer', 'Hired'];
    document.getElementById('rec-form-modal-title').textContent = 'New Application Form';
    document.getElementById('rec-form-title').value = '';
    document.getElementById('rec-form-desc').value = '';
    renderRecFields();
    renderRecStages();
    document.getElementById('add-rec-form-modal').style.display = 'flex';
}

function editRecForm(id) {
    var f = recFormsLookup[id];
    if (!f) { showToast('Form not found', 'error'); return; }
    recEditingFormId = id;
    recFormFields = f.fields ? JSON.parse(f.fields) : [];
    recFormStages = f.pipeline_stages ? JSON.parse(f.pipeline_stages) : ['Applied', 'Screening', 'Interview', 'Offer', 'Hired'];
    document.getElementById('rec-form-modal-title').textContent = 'Edit Application Form';
    document.getElementById('rec-form-title').value = f.title || '';
    document.getElementById('rec-form-desc').value = f.description || '';
    renderRecFields();
    renderRecStages();
    document.getElementById('add-rec-form-modal').style.display = 'flex';
}

function closeRecFormModal() {
    document.getElementById('add-rec-form-modal').style.display = 'none';
}

function addRecStage() {
    recFormStages.push('New Stage');
    renderRecStages();
}

function removeRecStage(idx) {
    if (recFormStages.length <= 2) { showToast('Need at least 2 stages', 'error'); return; }
    recFormStages.splice(idx, 1);
    renderRecStages();
}

function renderRecStages() {
    var container = document.getElementById('rec-stages-list');
    if (!recFormStages.length) { container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;">No stages defined.</p>'; return; }
    var stageColors = ['#6366f1', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#ef4444', '#ec4899', '#06b6d4'];
    container.innerHTML = recFormStages.map(function(s, i) {
        var color = stageColors[i % stageColors.length];
        return '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:6px 10px;">' +
            '<span style="width:12px;height:12px;border-radius:50%;background:' + color + ';flex-shrink:0;"></span>' +
            '<input type="text" value="' + esc(s) + '" class="form-control" style="flex:1;padding:4px 8px;font-size:0.85rem;" onchange="recFormStages[' + i + ']=this.value">' +
            (i > 0 ? '<button class="btn-icon" onclick="moveRecStageUp(' + i + ')" style="color:var(--text-secondary);font-size:0.9rem;" title="Move up">&#9650;</button>' : '<span style="width:24px;"></span>') +
            (i < recFormStages.length - 1 ? '<button class="btn-icon" onclick="moveRecStageDown(' + i + ')" style="color:var(--text-secondary);font-size:0.9rem;" title="Move down">&#9660;</button>' : '<span style="width:24px;"></span>') +
            '<button class="btn-icon" onclick="removeRecStage(' + i + ')" style="color:var(--accent-danger);font-size:1.1rem;">&times;</button>' +
            '</div>';
    }).join('');
}

function moveRecStageUp(idx) {
    if (idx <= 0) return;
    var temp = recFormStages[idx];
    recFormStages[idx] = recFormStages[idx - 1];
    recFormStages[idx - 1] = temp;
    renderRecStages();
}

function moveRecStageDown(idx) {
    if (idx >= recFormStages.length - 1) return;
    var temp = recFormStages[idx];
    recFormStages[idx] = recFormStages[idx + 1];
    recFormStages[idx + 1] = temp;
    renderRecStages();
}

function addRecField() {
    recFormFields.push({ label: '', type: 'text', required: true, options: '' });
    renderRecFields();
}

function removeRecField(idx) {
    recFormFields.splice(idx, 1);
    renderRecFields();
}

function renderRecFields() {
    var container = document.getElementById('rec-fields-list');
    if (!recFormFields.length) { container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.85rem;">No fields added. Click "+ Add Field" to build your form.</p>'; return; }
    container.innerHTML = recFormFields.map(function(f, i) {
        return '<div style="display:grid;grid-template-columns:1fr 120px 80px 32px;gap:8px;margin-bottom:8px;align-items:center;">' +
            '<input type="text" value="' + esc(f.label) + '" placeholder="Field label" class="form-control" onchange="recFormFields[' + i + '].label=this.value">' +
            '<select class="form-control" onchange="recFormFields[' + i + '].type=this.value;renderRecFields();">' +
                '<option value="text"' + (f.type==='text'?' selected':'') + '>Text</option>' +
                '<option value="email"' + (f.type==='email'?' selected':'') + '>Email</option>' +
                '<option value="phone"' + (f.type==='phone'?' selected':'') + '>Phone</option>' +
                '<option value="textarea"' + (f.type==='textarea'?' selected':'') + '>Textarea</option>' +
                '<option value="select"' + (f.type==='select'?' selected':'') + '>Dropdown</option>' +
                '<option value="file"' + (f.type==='file'?' selected':'') + '>File Upload</option>' +
            '</select>' +
            '<label style="font-size:0.8rem;display:flex;align-items:center;gap:4px;">' +
                '<input type="checkbox"' + (f.required?' checked':'') + ' onchange="recFormFields[' + i + '].required=this.checked"> Req' +
            '</label>' +
            '<button class="btn-icon" onclick="removeRecField(' + i + ')" style="color:var(--accent-danger);font-size:1.2rem;">&times;</button>' +
            (f.type === 'select' ? '<div style="grid-column:1/-1;"><input type="text" value="' + esc(f.options||'') + '" placeholder="Options (comma separated)" class="form-control" onchange="recFormFields[' + i + '].options=this.value"></div>' : '') +
            '</div>';
    }).join('');
}

async function saveRecForm() {
    var title = document.getElementById('rec-form-title').value.trim();
    if (!title) { showToast('Form title is required', 'error'); return; }
    if (recFormStages.length < 2) { showToast('Need at least 2 pipeline stages', 'error'); return; }
    var body = {
        title: title,
        description: document.getElementById('rec-form-desc').value.trim(),
        fields: JSON.stringify(recFormFields),
        pipeline_stages: JSON.stringify(recFormStages),
    };
    try {
        var url = recEditingFormId ? '/api/recruitment/forms/' + recEditingFormId : '/api/recruitment/forms';
        var method = recEditingFormId ? 'PUT' : 'POST';
        var res = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        if (!res.ok) {
            var err = await res.json().catch(function() { return {}; });
            showToast(err.detail || 'Failed to save form', 'error');
            return;
        }
        showToast(recEditingFormId ? 'Form updated!' : 'Form created!', 'success');
        closeRecFormModal();
        loadRecruitmentForms();
    } catch(e) { showToast('Error saving form: ' + e.message, 'error'); }
}

async function toggleRecForm(id, isActive) {
    try {
        var res = await fetch('/api/recruitment/forms/' + id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: !isActive })
        });
        if (!res.ok) { showToast('Failed to update', 'error'); return; }
        showToast(isActive ? 'Form deactivated' : 'Form activated', 'success');
        loadRecruitmentForms();
    } catch(e) { showToast('Error', 'error'); }
}

async function deleteRecForm(id) {
    if (!confirm('Delete this form and all its submissions?')) return;
    try {
        var res = await fetch('/api/recruitment/forms/' + id, { method: 'DELETE' });
        if (!res.ok) { showToast('Failed to delete', 'error'); return; }
        showToast('Form deleted', 'success');
        loadRecruitmentForms();
    } catch(e) { showToast('Error', 'error'); }
}

async function showRecFormSubmissions(formId) {
    recFormsSubId = formId;
    var f = recFormsLookup[formId];
    document.getElementById('rec-sub-form-title').textContent = f ? f.title : 'Form';
    recCurrentPipelineStages = (f && f.pipeline_stages) ? JSON.parse(f.pipeline_stages) : ['Applied', 'Screening', 'Interview', 'Offer', 'Hired'];
    document.getElementById('rec-forms-list').style.display = 'none';
    document.getElementById('rec-submissions-list').style.display = 'block';
    document.getElementById('rec-sub-detail').style.display = 'none';
    switchRecView('table');
    loadRecSubmissions();
}

function switchRecView(view) {
    document.getElementById('rec-table-view').style.display = view === 'table' ? 'block' : 'none';
    document.getElementById('rec-pipeline-view').style.display = view === 'pipeline' ? 'block' : 'none';
    var tb = document.getElementById('rec-view-table-btn');
    var pb = document.getElementById('rec-view-pipeline-btn');
    if (view === 'table') { tb.className = 'btn btn-primary btn-sm'; pb.className = 'btn btn-outline btn-sm'; }
    else { tb.className = 'btn btn-outline btn-sm'; pb.className = 'btn btn-primary btn-sm'; loadRecPipeline(); }
}

async function loadRecSubmissions() {
    try {
        var res = await fetch('/api/recruitment/forms/' + recFormsSubId + '/submissions');
        if (!res.ok) { showToast('Failed to load', 'error'); return; }
        var subs = await res.json();
        var tbody = document.getElementById('rec-subs-tbody');
        if (!subs.length) { tbody.innerHTML = '<tr><td colspan="6" class="loading">No submissions yet</td></tr>'; return; }
        tbody.innerHTML = subs.map(function(s) {
            var d = new Date(s.created_at);
            var stage = s.current_stage || 'Applied';
            var stageIdx = recCurrentPipelineStages.indexOf(stage);
            var stageColors = ['#6366f1', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#ef4444', '#ec4899', '#06b6d4'];
            var stageColor = stageColors[stageIdx >= 0 ? stageIdx % stageColors.length : 0];
            return '<tr>' +
                '<td>' + esc(s.candidate_name || '-') + '</td>' +
                '<td>' + esc(s.candidate_email || '-') + '</td>' +
                '<td>' + (s.file_name ? '<span style="font-size:0.85rem;">' + esc(s.file_name) + '</span>' : '<span style="color:var(--text-secondary)">—</span>') + '</td>' +
                '<td><span style="padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;background:' + stageColor + '20;color:' + stageColor + ';">' + esc(stage) + '</span></td>' +
                '<td>' + d.toLocaleDateString() + '</td>' +
                '<td style="text-align:right;white-space:nowrap;">' +
                    '<button class="btn btn-outline btn-sm" onclick="showRecSubmissionDetail(' + s.id + ')" style="margin-right:4px;">View</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="showMoveStageMenu(' + s.id + ',\'' + esc(stage) + '\')" title="Move to next stage">&#8594;</button>' +
                '</td></tr>';
        }).join('');
    } catch(e) { console.error(e); }
}

async function loadRecPipeline() {
    try {
        var res = await fetch('/api/recruitment/forms/' + recFormsSubId + '/pipeline');
        if (!res.ok) { showToast('Failed to load pipeline', 'error'); return; }
        var data = await res.json();
        var stages = data.stages || recCurrentPipelineStages;
        var pipeline = data.pipeline || {};
        var board = document.getElementById('rec-pipeline-board');
        var stageColors = ['#6366f1', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#ef4444', '#ec4899', '#06b6d4'];
        board.innerHTML = stages.map(function(stage, i) {
            var color = stageColors[i % stageColors.length];
            var cards = pipeline[stage] || [];
            var stagesJson = JSON.stringify(stages).replace(/"/g, '&quot;');
            return '<div style="min-width:260px;max-width:280px;flex-shrink:0;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;overflow:hidden;">' +
                '<div style="padding:12px 16px;border-bottom:2px solid ' + color + ';display:flex;align-items:center;justify-content:space-between;">' +
                    '<div style="display:flex;align-items:center;gap:8px;">' +
                        '<span style="width:10px;height:10px;border-radius:50%;background:' + color + ';"></span>' +
                        '<strong style="font-size:0.85rem;">' + esc(stage) + '</strong>' +
                    '</div>' +
                    '<span style="background:rgba(255,255,255,0.1);padding:2px 8px;border-radius:10px;font-size:0.75rem;font-weight:600;">' + cards.length + '</span>' +
                '</div>' +
                '<div style="padding:8px;display:flex;flex-direction:column;gap:8px;min-height:100px;">' +
                    cards.map(function(c) {
                        var email = c.candidate_email || '';
                        return '<div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:12px;cursor:pointer;" onclick="showRecSubmissionDetail(' + c.id + ')">' +
                            '<div style="font-weight:600;font-size:0.9rem;margin-bottom:4px;">' + esc(c.candidate_name || email || 'Unknown') + '</div>' +
                            (email ? '<div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:6px;">' + esc(email) + '</div>' : '') +
                            (c.file_name ? '<div style="font-size:0.72rem;color:var(--text-secondary);"><i class="bi bi-paperclip"></i> ' + esc(c.file_name) + '</div>' : '') +
                            '<div style="display:flex;gap:4px;margin-top:8px;">' +
                                (i > 0 ? '<button class="btn btn-outline btn-sm" onclick="event.stopPropagation();moveCandidateStage(' + c.id + ',' + JSON.stringify(stages[i-1]).replace(/"/g, '&quot;') + ',' + (i-1) + ')" style="font-size:0.7rem;padding:2px 6px;">&#9664; Prev</button>' : '') +
                                (i < stages.length - 1 ? '<button class="btn btn-outline btn-sm" onclick="event.stopPropagation();moveCandidateStage(' + c.id + ',' + JSON.stringify(stages[i+1]).replace(/"/g, '&quot;') + ',' + (i+1) + ')" style="font-size:0.7rem;padding:2px 6px;">Next &#9654;</button>' : '') +
                            '</div>' +
                        '</div>';
                    }).join('') +
                    (cards.length === 0 ? '<div style="text-align:center;color:var(--text-secondary);font-size:0.8rem;padding:24px 0;">No candidates</div>' : '') +
                '</div>' +
            '</div>';
        }).join('');
    } catch(e) { console.error(e); }
}

async function moveCandidateStage(subId, newStage, stageOrder) {
    try {
        var res = await fetch('/api/recruitment/submissions/' + subId + '/stage', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stage: newStage, stage_order: stageOrder })
        });
        if (!res.ok) { showToast('Failed to move candidate', 'error'); return; }
        showToast('Moved to ' + newStage, 'success');
        loadRecPipeline();
        loadRecSubmissions();
    } catch(e) { showToast('Error', 'error'); }
}

function showMoveStageMenu(subId, currentStage) {
    var idx = recCurrentPipelineStages.indexOf(currentStage);
    if (idx < recCurrentPipelineStages.length - 1) {
        var nextStage = recCurrentPipelineStages[idx + 1];
        moveCandidateStage(subId, nextStage, idx + 1);
    } else {
        showToast('Already at final stage', 'info');
    }
}

function showRecFormsList() {
    document.getElementById('rec-forms-list').style.display = 'block';
    document.getElementById('rec-submissions-list').style.display = 'none';
    document.getElementById('rec-sub-detail').style.display = 'none';
}

function showRecSubmissions() {
    document.getElementById('rec-submissions-list').style.display = 'block';
    document.getElementById('rec-sub-detail').style.display = 'none';
}

var _recSubmissionResume = null;
async function showRecSubmissionDetail(subId) {
    recCurrentSubId = subId;
    document.getElementById('rec-submissions-list').style.display = 'none';
    document.getElementById('rec-sub-detail').style.display = 'block';
    try {
        var res = await fetch('/api/recruitment/forms/' + recFormsSubId + '/submissions');
        if (!res.ok) return;
        var subs = await res.json();
        var sub = subs.find(function(s) { return s.id === subId; });
        if (!sub) return;
        document.getElementById('rec-detail-status').value = sub.status || 'new';
        document.getElementById('rec-detail-notes').value = sub.notes || '';
        _recSubmissionResume = sub;
        var answers = {};
        try { answers = JSON.parse(sub.answers || '{}'); } catch(e) {}
        var answersHtml = Object.entries(answers).map(function(entry) {
            return '<div style="margin-bottom:12px;"><strong style="font-size:0.85rem;">' + esc(entry[0]) + '</strong><div style="color:var(--text-primary);margin-top:2px;">' + esc(String(entry[1])) + '</div></div>';
        }).join('');
        document.getElementById('rec-detail-answers').innerHTML = answersHtml || '<p style="color:var(--text-secondary);">No answers provided</p>';
        var stage = sub.current_stage || 'Applied';
        document.getElementById('rec-detail-stage').innerHTML = buildStageMoveHtml(sub.id, stage);
        var resumeDiv = document.getElementById('rec-detail-resume');
        var previewDiv = document.getElementById('rec-detail-preview');
        if (sub.file_name) {
            resumeDiv.style.display = 'block';
            document.getElementById('rec-detail-filename').textContent = sub.file_name;
            previewDiv.innerHTML = '';
            if (sub.file_data) {
                var mime = sub.file_type || 'application/octet-stream';
                var dataUrl = 'data:' + mime + ';base64,' + sub.file_data;
                if (mime === 'application/pdf') {
                    previewDiv.innerHTML = '<iframe src="' + dataUrl + '" style="width:100%;height:500px;border:1px solid var(--border-color);border-radius:8px;"></iframe>';
                } else if (mime.startsWith('image/')) {
                    previewDiv.innerHTML = '<img src="' + dataUrl + '" style="max-width:100%;border-radius:8px;">';
                } else if (mime === 'application/msword' || mime === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
                    previewDiv.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-secondary);border:1px dashed var(--border-color);border-radius:8px;"><i class="bi bi-file-earmark-word" style="font-size:2rem;display:block;margin-bottom:8px;"></i>Word document — use Download to view</div>';
                } else {
                    previewDiv.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-secondary);border:1px dashed var(--border-color);border-radius:8px;"><i class="bi bi-file-earmark" style="font-size:2rem;display:block;margin-bottom:8px;"></i>Preview not available — use Download</div>';
                }
            } else {
                previewDiv.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-secondary);border:1px dashed var(--border-color);border-radius:8px;">No file uploaded</div>';
            }
        } else {
            resumeDiv.style.display = 'none';
        }
    } catch(e) { console.error(e); }
}

function buildStageMoveHtml(subId, currentStage) {
    var stages = recCurrentPipelineStages;
    var stageColors = ['#6366f1', '#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#ef4444', '#ec4899', '#06b6d4'];
    var html = '<div style="display:flex;gap:6px;flex-wrap:wrap;">';
    stages.forEach(function(s, i) {
        var color = stageColors[i % stageColors.length];
        var isCurrent = s === currentStage;
        if (isCurrent) {
            html += '<span style="padding:5px 14px;border-radius:16px;font-size:0.8rem;font-weight:600;background:' + color + ';color:white;">' + esc(s) + '</span>';
        } else {
            html += '<button class="btn btn-outline btn-sm" onclick="moveCandidateStage(' + subId + ',' + JSON.stringify(s).replace(/"/g, '&quot;') + ',' + i + ')" style="font-size:0.75rem;padding:3px 10px;border-color:' + color + '40;color:' + color + ';">' + esc(s) + '</button>';
        }
    });
    html += '</div>';
    return html;
}

async function updateRecSubmission() {
    if (!recCurrentSubId) return;
    try {
        var res = await fetch('/api/recruitment/submissions/' + recCurrentSubId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: document.getElementById('rec-detail-status').value,
                notes: document.getElementById('rec-detail-notes').value,
            })
        });
        if (!res.ok) { showToast('Failed to update', 'error'); return; }
        showToast('Submission updated', 'success');
    } catch(e) { showToast('Error', 'error'); }
}

function downloadRecResume() {
    var sub = _recSubmissionResume;
    if (!sub || !sub.file_data) { showToast('No resume file available', 'error'); return; }
    var byteStr = atob(sub.file_data);
    var arr = new Uint8Array(byteStr.length);
    for (var i = 0; i < byteStr.length; i++) arr[i] = byteStr.charCodeAt(i);
    var blob = new Blob([arr], { type: sub.file_type || 'application/octet-stream' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = sub.file_name || 'resume'; a.click();
    URL.revokeObjectURL(url);
}

function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

window.showAddFormModal = showAddFormModal;
window.closeRecFormModal = closeRecFormModal;
window.addRecField = addRecField;
window.removeRecField = removeRecField;
window.saveRecForm = saveRecForm;
window.editRecForm = editRecForm;
window.toggleRecForm = toggleRecForm;
window.deleteRecForm = deleteRecForm;
window.copyRecFormLink = copyRecFormLink;
window.showRecFormSubmissions = showRecFormSubmissions;
window.showRecFormsList = showRecFormsList;
window.showRecSubmissions = showRecSubmissions;
window.showRecSubmissionDetail = showRecSubmissionDetail;
window.updateRecSubmission = updateRecSubmission;
window.downloadRecResume = downloadRecResume;
window.switchRecView = switchRecView;
window.addRecStage = addRecStage;
window.removeRecStage = removeRecStage;
window.moveRecStageUp = moveRecStageUp;
window.moveRecStageDown = moveRecStageDown;
window.moveCandidateStage = moveCandidateStage;
window.showMoveStageMenu = showMoveStageMenu;
