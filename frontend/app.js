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
    try {
        var res = await fetch('/api/auth/me');
        var data = await res.json();
        if (data.user) {
            var loginBtn = document.getElementById('login-btn');
            var userInfo = document.getElementById('user-info');
            if (loginBtn) loginBtn.style.display = 'none';
            if (userInfo) {
                userInfo.style.display = 'flex';
                var name = data.user.name || data.user.email;
                document.getElementById('user-name-display').textContent = name;
                document.getElementById('user-avatar').textContent = name[0].toUpperCase();
            }
        } else {
            var loginBtn2 = document.getElementById('login-btn');
            var userInfo2 = document.getElementById('user-info');
            if (loginBtn2) loginBtn2.style.display = 'inline-block';
            if (userInfo2) userInfo2.style.display = 'none';
        }
    } catch (e) {
        console.error("Auth check failed", e);
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
        if (!response.ok) throw new Error('Failed');
        renderDashboard(await response.json());
    } catch (error) {
        console.error('Dashboard load failed:', error);
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

function handleGlobalSearch(e) {
    if (e.key === 'Enter') {
        var q = e.target.value.trim().toLowerCase();
        if (!q) return;
        showView('invoices-view');
        setTimeout(function() {
            document.getElementById('invoice-search').value = q;
            searchInvoices();
        }, 100);
    }
}
window.handleGlobalSearch = handleGlobalSearch;

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
                tbody.insertAdjacentHTML('beforeend', '<tr><td style="padding:12px 16px;">' + (item.name || '') + '</td><td style="padding:12px 16px;">' + item.description + '</td><td style="padding:12px 16px;text-align:right;">' + item.qty + '</td><td style="padding:12px 16px;text-align:right;">' + item.price.toFixed(2) + '</td><td style="padding:12px 16px;text-align:right;">' + (item.disc || 0) + '%</td><td style="padding:12px 16px;">20% VAT</td><td style="padding:12px 16px;text-align:right;">' + amount.toFixed(2) + '</td></tr>');
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
    var w = 612;
    var margin = 50;
    var y = margin;

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

    // Company details from view
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

    // Logo (left)
    if (savedLogo) {
        try { doc.addImage(savedLogo, 'PNG', margin, y, 120, 40); } catch(e) {}
    }

    // INVOICE title + number (right)
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(28);
    doc.setTextColor(26, 26, 46);
    doc.text('INVOICE', w - margin, y + 10, { align: 'right' });
    doc.setFontSize(12);
    doc.setTextColor(100, 116, 139);
    doc.text(number, w - margin, y + 28, { align: 'right' });
    y += 50;

    // Company details (right side under invoice number)
    if (company) {
        var cy = y - 30;
        doc.setFontSize(11);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(26, 26, 46);
        doc.text(company, w - margin, cy, { align: 'right' });
        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        if (compAddr) { cy += 13; doc.text(compAddr.substring(0, 40), w - margin, cy, { align: 'right' }); }
        if (compEmail) { cy += 13; doc.text(compEmail, w - margin, cy, { align: 'right' }); }
        if (compPhone) { cy += 13; doc.text(compPhone, w - margin, cy, { align: 'right' }); }
        if (compAbn) { cy += 13; doc.text('ABN: ' + compAbn, w - margin, cy, { align: 'right' }); }
    }

    // Divider
    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(margin, y, w - margin, y);
    y += 20;

    // Bill To
    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(148, 163, 184);
    doc.text('BILL TO', margin, y);
    doc.text('INVOICE DETAILS', w / 2 + 20, y);
    y += 16;

    doc.setFontSize(13);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text(contact, margin, y);
    y += 16;

    if (email && email !== 'No email') {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        doc.text(email, margin, y);
        y += 14;
    }
    if (phone && phone !== 'No phone') {
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(100, 116, 139);
        doc.text(phone, margin, y);
        y += 14;
    }

    // Invoice details (right side)
    var dx = w / 2 + 20;
    var dy = y - 16 - 16;
    if (email && email !== 'No email') dy += 16;
    if (phone && phone !== 'No phone') dy += 14;

    doc.setFontSize(10);
    doc.setTextColor(100, 116, 139);
    doc.setFont('helvetica', 'normal');
    doc.text('Issue Date:', dx, dy);
    doc.text('Due Date:', dx, dy + 16);
    doc.text('Invoice #:', dx, dy + 32);

    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text(issueDate, dx + 70, dy);
    doc.text(dueDate, dx + 70, dy + 16);
    doc.text(number, dx + 70, dy + 32);

    y = Math.max(y, dy + 50);
    y += 10;

    // Table header background
    doc.setFillColor(241, 245, 249);
    doc.rect(margin, y, w - margin * 2, 22, 'F');
    y += 15;

    // Table header text
    doc.setFontSize(8);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(100, 116, 139);
    doc.text('NAME', margin + 6, y);
    doc.text('DESCRIPTION', margin + 120, y);
    doc.text('QTY', margin + 280, y, { align: 'right' });
    doc.text('PRICE', margin + 330, y, { align: 'right' });
    doc.text('DISC', margin + 380, y, { align: 'right' });
    doc.text('AMOUNT', w - margin - 6, y, { align: 'right' });
    y += 10;

    doc.setDrawColor(226, 232, 240);
    doc.line(margin, y, w - margin, y);
    y += 5;

    // Line items
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    document.querySelectorAll('#view-line-items-body tr').forEach(function(tr) {
        var cells = tr.querySelectorAll('td');
        if (cells.length < 7) return;
        var name = cells[0].textContent;
        var desc = cells[1].textContent;
        var qty = cells[2].textContent;
        var price = cells[3].textContent;
        var disc = cells[4].textContent;
        var amount = cells[6].textContent;

        doc.setTextColor(51, 51, 51);
        doc.text(name.substring(0, 25), margin + 6, y);
        doc.text(desc.substring(0, 35), margin + 120, y);
        doc.text(qty, margin + 280, y, { align: 'right' });
        doc.text(price, margin + 330, y, { align: 'right' });
        doc.text(disc, margin + 380, y, { align: 'right' });
        doc.setFont('helvetica', 'bold');
        doc.text(amount, w - margin - 6, y, { align: 'right' });
        doc.setFont('helvetica', 'normal');
        y += 14;

        doc.setDrawColor(232, 236, 241);
        doc.line(margin + 6, y - 4, w - margin - 6, y - 4);
    });

    y += 15;

    // Totals
    var tx = w - margin - 200;
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100, 116, 139);
    doc.text('Subtotal', tx, y);
    doc.setTextColor(51, 51, 51);
    doc.text(subtotal, w - margin - 6, y, { align: 'right' });
    y += 18;

    doc.setTextColor(100, 116, 139);
    doc.text('VAT (20%)', tx, y);
    doc.setTextColor(51, 51, 51);
    doc.text(vat, w - margin - 6, y, { align: 'right' });
    y += 5;

    doc.setDrawColor(226, 232, 240);
    doc.line(tx, y, w - margin - 6, y);
    y += 15;

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text('Total Due', tx, y);
    doc.setTextColor(14, 165, 233);
    doc.text(total, w - margin - 6, y, { align: 'right' });
    y += 30;

    // Footer
    doc.setDrawColor(226, 232, 240);
    doc.line(margin, y, w - margin, y);
    y += 18;
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(148, 163, 184);
    doc.text('Thank you for your business', w / 2, y, { align: 'center' });
    y += 12;
    doc.setFontSize(8);
    doc.setTextColor(203, 213, 225);
    doc.text('Payment terms: Due within 14 days of issue', w / 2, y, { align: 'center' });

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
    tbody.insertAdjacentHTML('beforeend', '<tr class="line-item-row" style="border-bottom:1px solid var(--border-color);background:var(--surface-color);"><td style="padding:8px;text-align:center;color:var(--text-secondary);cursor:grab;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/></svg></td><td style="padding:0;"><input type="text" class="table-input item-name" style="width:100%;" placeholder="Item name"></td><td style="padding:0;"><input type="text" class="table-input item-desc" style="width:100%;"></td><td style="padding:0;"><input type="number" class="table-input item-qty" style="width:100%;text-align:right;" value="0" step="1" min="0"></td><td style="padding:0;"><input type="number" class="table-input item-price" style="width:100%;text-align:right;" value="0" step="0.01" min="0"></td><td style="padding:0;"><input type="number" class="table-input item-disc" style="width:100%;text-align:right;" placeholder="0" step="1" min="0" max="100"></td><td style="padding:0;"><select class="table-input" style="width:100%;"><option>200 - Sales</option></select></td><td style="padding:0;"><select class="table-input" style="width:100%;"><option>20% VAT</option><option>No Tax</option></select></td><td style="padding:12px 8px;text-align:right;" class="item-tax-amount">0.00</td><td style="padding:12px 8px;text-align:right;font-weight:500;" class="item-amount">0.00</td><td style="padding:8px;text-align:center;"><button type="button" class="btn-icon delete-row" style="color:var(--danger-color);cursor:pointer;background:none;border:none;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button></td></tr>');
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
            tbody.insertAdjacentHTML('beforeend', '<tr><td style="padding:12px 16px;">' + name + '</td><td style="padding:12px 16px;">' + desc + '</td><td style="padding:12px 16px;text-align:right;">' + qty + '</td><td style="padding:12px 16px;text-align:right;">' + price.toFixed(2) + '</td><td style="padding:12px 16px;text-align:right;">' + disc + '%</td><td style="padding:12px 16px;">20% VAT</td><td style="padding:12px 16px;text-align:right;">' + amount.toFixed(2) + '</td></tr>');
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

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
    fetchDashboardData();
    fetchInvoices();
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
});
