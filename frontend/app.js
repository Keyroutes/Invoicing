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
        'employees-view': 'nav-people',
        'employee-detail-view': 'nav-people',
        'departments-view': 'nav-people',
        'attendance-view': 'nav-people',
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

// ============================================================
// HR MODULE
// ============================================================

var allEmployees = [];
var allPayslips = [];
var currentEmpFilter = '';
var currentPsFilter = '';
var currentEmployeeId = null;
var currentPayslipId = null;

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
                listEl.insertAdjacentHTML('beforeend', '<label style="display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid var(--border-color);cursor:pointer;font-size:0.9rem;' + style + '"><input type="checkbox" ' + checkedAttr + ' onchange="toggleOnboardingItem(' + item.id + ', this.checked)" style="margin-top:4px;accent-color:var(--primary-color);"><div><div style="font-weight:500;">' + item.title + '</div><div style="font-size:0.78rem;color:var(--text-secondary);">' + (item.category || '') + ' &bull; ' + (item.assigned_to || '') + '</div></div></label>');
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

async function toggleOnboardingItem(itemId, isCompleted) {
    try {
        await fetch('/api/onboarding/' + itemId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_completed: isCompleted })
        });
        if (currentEmployeeId) viewEmployee(currentEmployeeId);
    } catch (e) { showToast('Failed to update item', 'error'); }
}
window.toggleOnboardingItem = toggleOnboardingItem;

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
    var deptVal = document.getElementById('emp-department').value;
    var mgrVal = document.getElementById('emp-reports-to').value;
    var payload = {
        first_name: firstName, last_name: lastName, email: email,
        phone: document.getElementById('emp-phone').value,
        job_title: document.getElementById('emp-job-title').value,
        department_id: deptVal ? parseInt(deptVal) : null,
        reports_to: mgrVal ? parseInt(mgrVal) : null,
        employment_type: document.getElementById('emp-type').value,
        pay_frequency: document.getElementById('emp-pay-freq').value,
        salary: parseFloat(document.getElementById('emp-salary').value) || 0,
        tax_rate: parseFloat(document.getElementById('emp-tax-rate').value) || 0,
        start_date: document.getElementById('emp-start-date').value,
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
async function fetchDepartments() {
    try {
        var res = await fetch('/api/departments');
        if (!res.ok) throw new Error('Failed');
        var depts = await res.json();
        var tbody = document.getElementById('departments-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (depts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-secondary);">No departments yet.</td></tr>';
            return;
        }
        depts.forEach(function(d) {
            tbody.insertAdjacentHTML('beforeend', '<tr><td style="font-weight:500;">' + d.name + '</td><td style="color:var(--text-secondary);">' + (d.description || '-') + '</td><td>' + (d.employee_count || 0) + '</td><td class="text-right"><button class="btn btn-outline btn-sm" onclick="deleteDepartment(' + d.id + ', \'' + d.name.replace(/'/g, "\\'") + '\')" style="color:var(--danger-color);border-color:var(--danger-color);">Delete</button></td></tr>');
        });
    } catch (e) { console.error('Depts error:', e); }
}

function showAddDeptModal() {
    var name = prompt('Department name:');
    if (!name) return;
    var desc = prompt('Description (optional):') || '';
    createDepartment(name, desc);
}
window.showAddDeptModal = showAddDeptModal;

async function createDepartment(name, description) {
    try {
        var res = await fetch('/api/departments', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, description: description })
        });
        var data = await res.json();
        if (res.ok) { showToast('Department created', 'success'); fetchDepartments(); loadHRStats(); }
        else { showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}

async function deleteDepartment(id, name) {
    if (!confirm('Delete department "' + name + '"? Employees will be unassigned.')) return;
    try {
        var res = await fetch('/api/departments/' + id, { method: 'DELETE' });
        if (res.ok) { showToast('Department deleted', 'success'); fetchDepartments(); loadHRStats(); }
        else { var data = await res.json(); showToast('Failed: ' + (data.detail || 'Error'), 'error'); }
    } catch (e) { showToast('Failed: ' + e, 'error'); }
}
window.deleteDepartment = deleteDepartment;

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
}
window.showGeneratePayslipModal = showGeneratePayslipModal;

async function showGeneratePayslipModalForNew() {
    document.getElementById('generate-payslip-modal').style.display = 'flex';
    document.getElementById('generate-payslip-form').reset();
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
        empContainer.innerHTML = '<select id="ps-employee-id" class="form-control"><option value="">Select employee...</option></select>';
        var sel = document.getElementById('ps-employee-id');
        emps.forEach(function(e) { sel.insertAdjacentHTML('beforeend', '<option value="' + e.id + '">' + e.first_name + ' ' + e.last_name + '</option>'); });
    } catch (e) { console.error(e); empContainer.innerHTML = '<select id="ps-employee-id" class="form-control"><option value="">Failed to load employees</option></select>'; }
}
window.showGeneratePayslipModalForNew = showGeneratePayslipModalForNew;

function closeGeneratePayslipModal() {
    document.getElementById('generate-payslip-modal').style.display = 'none';
}
window.closeGeneratePayslipModal = closeGeneratePayslipModal;

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
    var w = 612, margin = 50, y = margin;

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

    // Title
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(28);
    doc.setTextColor(26, 26, 46);
    doc.text('PAYSLIP', margin, y + 10);
    doc.setFontSize(12);
    doc.setTextColor(100, 116, 139);
    doc.text(number, margin, y + 28);
    y += 50;

    // Company + employee
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text(company, w - margin, y, { align: 'right' });
    if (companyAddr) { doc.setFontSize(9); doc.setFont('helvetica', 'normal'); doc.setTextColor(100, 116, 139); doc.text(companyAddr, w - margin, y + 14, { align: 'right' }); }
    y += 30;

    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.5);
    doc.line(margin, y, w - margin, y);
    y += 20;

    doc.setFontSize(10);
    doc.setTextColor(100, 116, 139);
    doc.setFont('helvetica', 'normal');
    doc.text('Employee:', margin, y);
    doc.text('Period:', margin, y + 16);
    doc.text('Pay Date:', margin, y + 32);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text(empName, margin + 70, y);
    doc.text(period, margin + 70, y + 16);
    doc.text(payDate, margin + 70, y + 32);
    y += 60;

    // Earnings table
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(148, 163, 184);
    doc.text('EARNINGS', margin, y);
    doc.text('AMOUNT', w - margin - 6, y, { align: 'right' });
    y += 14;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(51, 51, 51);
    var earnings = [['Basic Salary', basic], ['Overtime Pay', otpay], ['Bonus', bonus], ['Allowances', allow]];
    earnings.forEach(function(r) {
        doc.text(r[0], margin, y);
        doc.text(r[1], w - margin - 6, y, { align: 'right' });
        y += 16;
    });
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(22, 163, 74);
    doc.text('Gross Pay', margin, y);
    doc.text(gross, w - margin - 6, y, { align: 'right' });
    y += 24;

    // Deductions table
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(148, 163, 184);
    doc.text('DEDUCTIONS', margin, y);
    doc.text('AMOUNT', w - margin - 6, y, { align: 'right' });
    y += 14;
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(51, 51, 51);
    var deductions = [['Tax', tax], ['Insurance', ins], ['Retirement', ret], ['Other', other]];
    deductions.forEach(function(r) {
        doc.text(r[0], margin, y);
        doc.text(r[1], w - margin - 6, y, { align: 'right' });
        y += 16;
    });
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(220, 38, 38);
    doc.text('Total Deductions', margin, y);
    doc.text(dedTotal, w - margin - 6, y, { align: 'right' });
    y += 24;

    doc.setDrawColor(226, 232, 240);
    doc.line(margin, y, w - margin, y);
    y += 18;

    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(26, 26, 46);
    doc.text('Net Pay', margin, y);
    doc.setTextColor(14, 165, 233);
    doc.text('$' + netPay, w - margin - 6, y, { align: 'right' });

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
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading">Failed to load attendance.</td></tr>';
    }
}

function renderAttendance(records) {
    var tbody = document.getElementById('attendance-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (records.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-secondary);">No attendance records found.</td></tr>';
        return;
    }
    records.forEach(function(r) {
        var statusClass = r.status === 'completed' ? 'paid' : r.status === 'present' ? 'sent' : 'draft';
        tbody.insertAdjacentHTML('beforeend', '<tr><td><strong>' + r.employee_name + '</strong><br><span style="font-size:0.78rem;color:var(--text-secondary);">' + (r.employee_email || '') + '</span></td><td>' + r.date + '</td><td>' + (r.clock_in || '-') + '</td><td>' + (r.clock_out || '-') + '</td><td class="text-right">' + (r.total_hours ? r.total_hours + 'h' : '-') + '</td><td><span class="status-pill status-' + statusClass + '">' + r.status + '</span></td><td class="text-right">' + (!r.clock_out && r.clock_in ? '<button class="btn btn-outline btn-sm" onclick="clockInOut(' + r.employee_id + ')">Clock Out</button>' : '') + '</td></tr>');
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
    if (viewId === 'payroll-view') fetchPayslips(currentPsFilter);
    if (viewId === 'attendance-view') { loadAttendanceStats(); loadAttendanceButtons(); loadAttendance(); }
    if (viewId === 'orgchart-view') loadOrgChart();
};
window.showView = showView;

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
