/**
 * Module detail page - fetch version details, render README, display inputs/outputs, version switcher.
 */

(function () {
    'use strict';

    var API_BASE = '/api/modules';
    var detailContainer = document.getElementById('module-detail');
    var errorContainer = document.getElementById('error-container');
    var errorMessage = document.getElementById('error-message');
    var loadingEl = document.getElementById('loading');

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(text || ''));
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '';
        var d = new Date(dateStr);
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

    function parsePathSegments() {
        // URL format: /modules/:namespace/:name/:provider[/:version]
        var parts = window.location.pathname.split('/').filter(Boolean);
        // parts[0] = 'modules', parts[1] = ns, parts[2] = name, parts[3] = provider, parts[4]? = version
        if (parts.length < 4) return null;
        return {
            namespace: decodeURIComponent(parts[1]),
            name: decodeURIComponent(parts[2]),
            provider: decodeURIComponent(parts[3]),
            version: parts[4] ? decodeURIComponent(parts[4]) : null,
        };
    }

    function showError(message) {
        if (loadingEl) loadingEl.style.display = 'none';
        detailContainer.style.display = 'none';
        errorContainer.hidden = false;
        errorMessage.textContent = message;
    }

    function renderInputsTable(inputs) {
        if (!inputs || inputs.length === 0) {
            return '<p class="muted">No inputs defined.</p>';
        }

        var html = '<table class="data-table">' +
            '<thead><tr><th>Name</th><th>Type</th><th>Description</th><th>Default</th><th>Required</th></tr></thead>' +
            '<tbody>';

        for (var i = 0; i < inputs.length; i++) {
            var inp = inputs[i];
            html += '<tr>' +
                '<td><code>' + escapeHtml(inp.name) + '</code></td>' +
                '<td><code>' + escapeHtml(inp.type || 'string') + '</code></td>' +
                '<td>' + escapeHtml(inp.description || '') + '</td>' +
                '<td>' + (inp.default != null ? '<code>' + escapeHtml(String(inp.default)) + '</code>' : '—') + '</td>' +
                '<td>' + (inp.required ? '<span class="badge badge-required">yes</span>' : 'no') + '</td>' +
                '</tr>';
        }

        html += '</tbody></table>';
        return html;
    }

    function renderOutputsTable(outputs) {
        if (!outputs || outputs.length === 0) {
            return '<p class="muted">No outputs defined.</p>';
        }

        var html = '<table class="data-table">' +
            '<thead><tr><th>Name</th><th>Description</th></tr></thead>' +
            '<tbody>';

        for (var i = 0; i < outputs.length; i++) {
            var out = outputs[i];
            html += '<tr>' +
                '<td><code>' + escapeHtml(out.name) + '</code></td>' +
                '<td>' + escapeHtml(out.description || '') + '</td>' +
                '</tr>';
        }

        html += '</tbody></table>';
        return html;
    }

    function renderUsageExample(example) {
        if (!example) return '';
        return '<div class="usage-example">' +
            '<h3>Usage</h3>' +
            '<pre><code>' + escapeHtml(example) + '</code></pre>' +
            '</div>';
    }

    function renderReadme(readme) {
        if (!readme) return '<p class="muted">No README available.</p>';
        // Simple markdown-like rendering for README
        // Convert headings, code blocks, bold, links
        var html = escapeHtml(readme);

        // Code blocks (```...```)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_m, _lang, code) {
            return '<pre><code>' + code + '</code></pre>';
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Headings
        html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Line breaks
        html = html.replace(/\n\n/g, '</p><p>');
        html = '<p>' + html + '</p>';

        return '<div class="readme-content">' + html + '</div>';
    }

    function renderVersionSwitcher(versions, currentVersion, segments) {
        if (!versions || versions.length === 0) return '';

        var html = '<div class="version-switcher">' +
            '<label for="version-select">Version:</label>' +
            '<select id="version-select" class="select-input">';

        for (var i = 0; i < versions.length; i++) {
            var v = versions[i];
            var selected = v.version === currentVersion ? ' selected' : '';
            var deprecated = v.deprecated ? ' (deprecated)' : '';
            html += '<option value="' + escapeHtml(v.version) + '"' + selected + '>' +
                escapeHtml(v.version) + deprecated +
                '</option>';
        }

        html += '</select></div>';
        return html;
    }

    function renderModuleHeader(mod, segments) {
        return '<div class="module-header">' +
            '  <nav class="breadcrumb" aria-label="Breadcrumb">' +
            '    <a href="/">Modules</a>' +
            '    <span class="breadcrumb-sep">/</span>' +
            '    <a href="/?namespace=' + encodeURIComponent(segments.namespace) + '">' +
            escapeHtml(segments.namespace) + '</a>' +
            '    <span class="breadcrumb-sep">/</span>' +
            '    <span>' + escapeHtml(segments.name) + '</span>' +
            '    <span class="breadcrumb-sep">/</span>' +
            '    <span>' + escapeHtml(segments.provider) + '</span>' +
            '  </nav>' +
            '  <h1>' + escapeHtml(segments.namespace) + ' / ' + escapeHtml(segments.name) +
            '    <span class="badge">' + escapeHtml(segments.provider) + '</span>' +
            '  </h1>' +
            (mod.description ? '<p class="module-header-desc">' + escapeHtml(mod.description) + '</p>' : '') +
            '  <div class="module-stats">' +
            '    <span class="stat">' + formatNumber(mod.total_downloads) + ' downloads</span>' +
            '    <span class="stat">' + (mod.versions ? mod.versions.length : 0) + ' versions</span>' +
            (mod.source_url ? '    <a href="' + escapeHtml(mod.source_url) + '" class="stat stat-link" target="_blank" rel="noopener">Source</a>' : '') +
            '  </div>' +
            '</div>';
    }

    async function loadModuleDetail(segments) {
        try {
            var modResp = await fetch(
                API_BASE + '/' + encodeURIComponent(segments.namespace) +
                '/' + encodeURIComponent(segments.name) +
                '/' + encodeURIComponent(segments.provider)
            );

            if (modResp.status === 401) {
                showError('Authentication required. Please sign in.');
                return;
            }
            if (modResp.status === 403) {
                showError('You do not have access to this module.');
                return;
            }
            if (modResp.status === 404) {
                showError('Module not found.');
                return;
            }
            if (!modResp.ok) {
                throw new Error('Failed to load module (HTTP ' + modResp.status + ')');
            }

            var modData = await modResp.json();
            var mod = modData.module;

            // Determine which version to show
            var targetVersion = segments.version || mod.latest_version;
            if (!targetVersion && mod.versions && mod.versions.length > 0) {
                targetVersion = mod.versions[0].version;
            }

            // Fetch version detail
            var versionDetail = null;
            if (targetVersion) {
                var verResp = await fetch(
                    API_BASE + '/' + encodeURIComponent(segments.namespace) +
                    '/' + encodeURIComponent(segments.name) +
                    '/' + encodeURIComponent(segments.provider) +
                    '/' + encodeURIComponent(targetVersion)
                );
                if (verResp.ok) {
                    var verData = await verResp.json();
                    versionDetail = verData.version;
                }
            }

            // Render the page
            if (loadingEl) loadingEl.style.display = 'none';

            var html = renderModuleHeader(mod, segments);
            html += renderVersionSwitcher(mod.versions, targetVersion, segments);

            if (versionDetail) {
                html += '<div class="version-tabs">' +
                    '  <button class="tab-btn tab-btn-active" data-tab="readme">README</button>' +
                    '  <button class="tab-btn" data-tab="inputs">Inputs (' + (versionDetail.inputs ? versionDetail.inputs.length : 0) + ')</button>' +
                    '  <button class="tab-btn" data-tab="outputs">Outputs (' + (versionDetail.outputs ? versionDetail.outputs.length : 0) + ')</button>' +
                    '</div>';

                html += '<div class="tab-content" id="tab-readme">' +
                    renderUsageExample(versionDetail.usage_example) +
                    renderReadme(versionDetail.readme) +
                    '</div>';

                html += '<div class="tab-content" id="tab-inputs" hidden>' +
                    '<h3>Input Variables</h3>' +
                    renderInputsTable(versionDetail.inputs) +
                    '</div>';

                html += '<div class="tab-content" id="tab-outputs" hidden>' +
                    '<h3>Output Values</h3>' +
                    renderOutputsTable(versionDetail.outputs) +
                    '</div>';

                // Version info sidebar
                html += '<div class="version-info">' +
                    '  <h4>Version ' + escapeHtml(targetVersion) + '</h4>' +
                    '  <dl class="info-list">' +
                    '    <dt>Published</dt><dd>' + formatDate(versionDetail.published_at) + '</dd>' +
                    '    <dt>Downloads</dt><dd>' + formatNumber(versionDetail.download_count) + '</dd>';

                if (versionDetail.published_by) {
                    html += '    <dt>Author</dt><dd>' +
                        escapeHtml(versionDetail.published_by.name || versionDetail.published_by.email) +
                        '</dd>';
                }

                html += '    <dt>SHA256</dt><dd><code class="checksum">' +
                    escapeHtml(versionDetail.checksum_sha256 || '') +
                    '</code></dd>' +
                    '  </dl>' +
                    '</div>';
            } else {
                html += '<div class="empty-state"><p>No version details available.</p></div>';
            }

            detailContainer.innerHTML = html;
            setupTabHandlers();
            setupVersionSwitcher(segments);
            document.title = segments.namespace + '/' + segments.name + ' - Tsilo';

        } catch (err) {
            showError(err.message);
        }
    }

    function setupTabHandlers() {
        var tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var tab = btn.getAttribute('data-tab');

                // Deactivate all tabs
                tabBtns.forEach(function (b) { b.classList.remove('tab-btn-active'); });
                document.querySelectorAll('.tab-content').forEach(function (c) { c.hidden = true; });

                // Activate selected tab
                btn.classList.add('tab-btn-active');
                var content = document.getElementById('tab-' + tab);
                if (content) content.hidden = false;
            });
        });
    }

    function setupVersionSwitcher(segments) {
        var select = document.getElementById('version-select');
        if (!select) return;

        select.addEventListener('change', function () {
            var newVersion = select.value;
            var newPath = '/modules/' +
                encodeURIComponent(segments.namespace) + '/' +
                encodeURIComponent(segments.name) + '/' +
                encodeURIComponent(segments.provider) + '/' +
                encodeURIComponent(newVersion);
            window.location.href = newPath;
        });
    }

    // Auth nav update
    var csrfToken = '';

    async function updateNav() {
        try {
            var resp = await fetch('/auth/me');
            if (resp.ok) {
                var data = await resp.json();
                csrfToken = resp.headers.get('X-CSRF-Token') || '';
                var authDiv = document.getElementById('nav-auth');
                if (authDiv && data.user) {
                    authDiv.innerHTML =
                        '<span class="nav-user">' + escapeHtml(data.user.name || data.user.email) + '</span>' +
                        '<button class="btn btn-sm btn-outline" onclick="handleLogout()">Sign Out</button>';
                }
            }
        } catch (e) {
            // Not authenticated
        }
    }

    window.handleLogout = async function () {
        try {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: { 'X-CSRF-Token': csrfToken },
            });
        } catch (e) {
            // ignore
        }
        window.location.href = '/';
    };

    // Initialize
    var segments = parsePathSegments();
    if (!segments) {
        showError('Invalid module URL.');
    } else {
        updateNav();
        loadModuleDetail(segments);
    }
})();
