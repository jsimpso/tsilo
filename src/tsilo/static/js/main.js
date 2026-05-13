/**
 * Module list page - fetches modules, renders cards, search filtering, pagination.
 */

(function () {
    'use strict';

    const API_BASE = '/api/modules';
    const searchInput = document.getElementById('module-search');
    const namespaceFilter = document.getElementById('namespace-filter');
    const modulesList = document.getElementById('modules-list');
    const modulesCount = document.getElementById('modules-count');
    const paginationNav = document.getElementById('pagination');
    const loadingEl = document.getElementById('loading');

    let currentPage = 1;
    let debounceTimer = null;

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(text || ''));
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    }

    function formatNumber(num) {
        if (num >= 1000) {
            return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
        }
        return String(num);
    }

    function showLoading() {
        if (loadingEl) loadingEl.style.display = '';
    }

    function hideLoading() {
        if (loadingEl) loadingEl.style.display = 'none';
    }

    function showError(message) {
        modulesList.innerHTML =
            '<div class="empty-state"><p class="error-text">' +
            escapeHtml(message) +
            '</p></div>';
    }

    function renderModuleCard(mod) {
        const href = '/modules/' +
            encodeURIComponent(mod.namespace) + '/' +
            encodeURIComponent(mod.name) + '/' +
            encodeURIComponent(mod.system);

        return (
            '<a href="' + href + '" class="module-card">' +
            '  <div class="module-card-header">' +
            '    <span class="module-namespace">' + escapeHtml(mod.namespace) + '</span>' +
            '    <span class="module-system badge">' + escapeHtml(mod.system) + '</span>' +
            '  </div>' +
            '  <h3 class="module-name">' + escapeHtml(mod.name) + '</h3>' +
            '  <p class="module-description">' + escapeHtml(mod.description || 'No description') + '</p>' +
            '  <div class="module-card-footer">' +
            '    <span class="module-version" title="Latest version">' +
            '      v' + escapeHtml(mod.latest_version || '—') +
            '    </span>' +
            '    <span class="module-downloads" title="Total downloads">' +
            '      ' + formatNumber(mod.total_downloads) + ' downloads' +
            '    </span>' +
            '    <span class="module-updated" title="Last updated">' +
            '      ' + formatDate(mod.last_updated) +
            '    </span>' +
            '  </div>' +
            '</a>'
        );
    }

    function renderPagination(pagination) {
        if (!pagination || pagination.total_pages <= 1) {
            paginationNav.innerHTML = '';
            return;
        }

        var html = '';
        var page = pagination.page;
        var total = pagination.total_pages;

        // Previous button
        if (page > 1) {
            html += '<button class="pagination-btn" data-page="' + (page - 1) + '">&laquo; Prev</button>';
        }

        // Page numbers (show max 7 pages with ellipsis)
        var start = Math.max(1, page - 3);
        var end = Math.min(total, page + 3);

        if (start > 1) {
            html += '<button class="pagination-btn" data-page="1">1</button>';
            if (start > 2) html += '<span class="pagination-ellipsis">&hellip;</span>';
        }

        for (var i = start; i <= end; i++) {
            var activeClass = i === page ? ' pagination-btn-active' : '';
            html += '<button class="pagination-btn' + activeClass + '" data-page="' + i + '">' + i + '</button>';
        }

        if (end < total) {
            if (end < total - 1) html += '<span class="pagination-ellipsis">&hellip;</span>';
            html += '<button class="pagination-btn" data-page="' + total + '">' + total + '</button>';
        }

        // Next button
        if (page < total) {
            html += '<button class="pagination-btn" data-page="' + (page + 1) + '">Next &raquo;</button>';
        }

        paginationNav.innerHTML = html;
    }

    async function fetchModules(page, search, namespace) {
        showLoading();
        var params = new URLSearchParams();
        params.set('page', String(page || 1));
        params.set('per_page', '20');
        if (search) params.set('search', search);
        if (namespace) params.set('namespace', namespace);

        try {
            var resp = await fetch(API_BASE + '?' + params.toString());
            if (resp.status === 401) {
                hideLoading();
                modulesList.innerHTML =
                    '<div class="empty-state">' +
                    '  <h3>Sign in to browse modules</h3>' +
                    '  <p>Authentication is required to view modules.</p>' +
                    '  <a href="/auth/login" class="btn btn-primary">Sign In</a>' +
                    '</div>';
                return;
            }
            if (!resp.ok) {
                throw new Error('Failed to load modules (HTTP ' + resp.status + ')');
            }
            var data = await resp.json();
            hideLoading();

            if (!data.modules || data.modules.length === 0) {
                modulesList.innerHTML =
                    '<div class="empty-state">' +
                    '  <h3>No modules found</h3>' +
                    '  <p>Try adjusting your search or filter criteria.</p>' +
                    '</div>';
                modulesCount.textContent = '0 modules';
                paginationNav.innerHTML = '';
                return;
            }

            modulesList.innerHTML = data.modules.map(renderModuleCard).join('');
            modulesCount.textContent = data.pagination.total_count + ' module' +
                (data.pagination.total_count !== 1 ? 's' : '');
            renderPagination(data.pagination);
            currentPage = data.pagination.page;
        } catch (err) {
            hideLoading();
            showError(err.message);
        }
    }

    function onSearch() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            currentPage = 1;
            fetchModules(1, searchInput.value.trim(), namespaceFilter.value);
        }, 300);
    }

    function onNamespaceChange() {
        currentPage = 1;
        fetchModules(1, searchInput.value.trim(), namespaceFilter.value);
    }

    // Event listeners
    if (searchInput) {
        searchInput.addEventListener('input', onSearch);
    }

    if (namespaceFilter) {
        namespaceFilter.addEventListener('change', onNamespaceChange);
    }

    if (paginationNav) {
        paginationNav.addEventListener('click', function (e) {
            var btn = e.target.closest('[data-page]');
            if (btn) {
                var page = parseInt(btn.getAttribute('data-page'), 10);
                fetchModules(page, searchInput.value.trim(), namespaceFilter.value);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        });
    }

    // Auth nav update
    var csrfToken = '';

    async function updateNav() {
        try {
            var resp = await fetch('/auth/me');
            if (resp.ok) {
                var data = await resp.json();
                // Capture CSRF token from response header
                csrfToken = resp.headers.get('X-CSRF-Token') || '';
                var authDiv = document.getElementById('nav-auth');
                if (authDiv && data.user) {
                    authDiv.innerHTML =
                        '<span class="nav-user">' + escapeHtml(data.user.name || data.user.email) + '</span>' +
                        '<button class="btn btn-sm btn-outline" id="logout-btn">Sign Out</button>';
                    var logoutBtn = document.getElementById('logout-btn');
                    if (logoutBtn) {
                        logoutBtn.addEventListener('click', function () {
                            fetch('/auth/logout', {
                                method: 'POST',
                                headers: { 'X-CSRF-Token': csrfToken },
                            }).then(function () {
                                window.location.href = '/';
                            }).catch(function () {
                                window.location.href = '/';
                            });
                        });
                    }
                }
            }
        } catch (e) {
            // Not authenticated
        }
    }

    // Initialize
    updateNav();
    fetchModules(1, '', '');
})();
