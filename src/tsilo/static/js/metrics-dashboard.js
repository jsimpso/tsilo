/**
 * Metrics dashboard - system overview, top modules, namespace usage (admin only).
 */

(function () {
    'use strict';

    var API_URL = '/api/metrics/overview';
    var loadingEl = document.getElementById('metrics-loading');
    var errorEl = document.getElementById('metrics-error');
    var errorMsg = document.getElementById('error-message');
    var contentEl = document.getElementById('metrics-content');

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text || ''));
        return div.innerHTML;
    }

    function formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
        }
        return String(num);
    }

    function showError(message) {
        loadingEl.style.display = 'none';
        contentEl.hidden = true;
        errorEl.hidden = false;
        if (message) {
            errorMsg.textContent = message;
        }
    }

    function showContent() {
        loadingEl.style.display = 'none';
        errorEl.hidden = true;
        contentEl.hidden = false;
    }

    function renderOverview(metrics) {
        document.getElementById('total-modules').textContent = formatNumber(metrics.total_modules);
        document.getElementById('total-versions').textContent = formatNumber(metrics.total_versions);
        document.getElementById('total-namespaces').textContent = formatNumber(metrics.total_namespaces);
        document.getElementById('total-downloads').textContent = formatNumber(metrics.total_downloads);
        document.getElementById('downloads-30d').textContent = formatNumber(metrics.downloads_last_30_days);
        document.getElementById('active-users').textContent = formatNumber(metrics.active_users_last_30_days);
    }

    function renderTopModules(modules) {
        var tbody = document.getElementById('top-modules-body');
        if (!modules || modules.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="empty-cell">No module data available</td></tr>';
            return;
        }

        var html = '';
        for (var i = 0; i < modules.length; i++) {
            var mod = modules[i];
            var href = '/modules/' +
                encodeURIComponent(mod.namespace) + '/' +
                encodeURIComponent(mod.name) + '/' +
                encodeURIComponent(mod.system);
            html +=
                '<tr>' +
                '<td><a href="' + href + '">' +
                escapeHtml(mod.namespace) + '/' + escapeHtml(mod.name) +
                '</a></td>' +
                '<td>' + escapeHtml(mod.system) + '</td>' +
                '<td>' + formatNumber(mod.downloads) + '</td>' +
                '</tr>';
        }
        tbody.innerHTML = html;
    }

    function renderNamespaceUsage(namespaces) {
        var tbody = document.getElementById('namespace-usage-body');
        if (!namespaces || namespaces.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-cell">No namespace data available</td></tr>';
            return;
        }

        var html = '';
        for (var i = 0; i < namespaces.length; i++) {
            var ns = namespaces[i];
            html +=
                '<tr>' +
                '<td>' + escapeHtml(ns.namespace) + '</td>' +
                '<td>' + ns.module_count + '</td>' +
                '<td>' + ns.version_count + '</td>' +
                '<td>' + formatNumber(ns.total_downloads) + '</td>' +
                '</tr>';
        }
        tbody.innerHTML = html;
    }

    function loadMetrics() {
        fetch(API_URL, { credentials: 'same-origin' })
            .then(function (response) {
                if (response.status === 401) {
                    showError('You must be signed in to view metrics.');
                    return null;
                }
                if (response.status === 403) {
                    showError('You need admin access to view system metrics.');
                    return null;
                }
                if (!response.ok) {
                    showError('Failed to load metrics (HTTP ' + response.status + ').');
                    return null;
                }
                return response.json();
            })
            .then(function (data) {
                if (!data) return;
                var metrics = data.metrics;
                renderOverview(metrics);
                renderTopModules(metrics.top_modules);
                renderNamespaceUsage(metrics.namespace_usage);
                showContent();
            })
            .catch(function (err) {
                showError('Failed to load metrics: ' + err.message);
            });
    }

    // Check auth state and update nav
    fetch('/auth/me', { credentials: 'same-origin' })
        .then(function (r) {
            var csrfToken = r.headers.get('X-CSRF-Token') || '';
            return r.ok ? r.json().then(function (data) { return { data: data, csrf: csrfToken }; }) : null;
        })
        .then(function (result) {
            var nav = document.getElementById('nav-auth');
            if (result && result.data && result.data.user) {
                var data = result.data;
                nav.innerHTML =
                    '<span class="nav-user">' + escapeHtml(data.user.name || data.user.email) + '</span>' +
                    ' <a href="/tokens" class="nav-link">Tokens</a>' +
                    ' <button class="btn btn-sm" id="logout-btn">Sign Out</button>';
                var logoutBtn = document.getElementById('logout-btn');
                if (logoutBtn) {
                    logoutBtn.addEventListener('click', function () {
                        fetch('/auth/logout', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: { 'X-CSRF-Token': result.csrf }
                        })
                            .then(function () { location.reload(); })
                            .catch(function () { location.reload(); });
                    });
                }
            }
        })
        .catch(function () { });

    loadMetrics();
})();
