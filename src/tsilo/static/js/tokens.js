/* API token management UI - list, create, revoke tokens. */

(function () {
    'use strict';

    let csrfToken = '';

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : csrfToken;
    }

    function showError(message) {
        const el = document.getElementById('error-message');
        if (el) {
            el.textContent = message;
            el.hidden = false;
            setTimeout(function () { el.hidden = true; }, 8000);
        }
    }

    async function apiRequest(url, options) {
        const defaults = {
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
        };
        const token = getCsrfToken();
        if (token) {
            defaults.headers['X-CSRF-Token'] = token;
        }
        const opts = Object.assign({}, defaults, options);
        if (options && options.headers) {
            opts.headers = Object.assign({}, defaults.headers, options.headers);
        }
        const resp = await fetch(url, opts);

        const newToken = resp.headers.get('X-CSRF-Token');
        if (newToken) {
            csrfToken = newToken;
        }

        return resp;
    }

    async function checkAuth() {
        try {
            const resp = await apiRequest('/auth/me');
            if (resp.ok) {
                const data = await resp.json();
                const authEl = document.getElementById('nav-auth');
                if (authEl && data.user) {
                    authEl.innerHTML =
                        '<span class="nav-user">' +
                        (data.user.name || data.user.email) +
                        '</span> <a href="#" class="btn btn-secondary btn-sm" id="logout-btn">Sign Out</a>';
                    const logoutBtn = document.getElementById('logout-btn');
                    if (logoutBtn) {
                        logoutBtn.addEventListener('click', function (e) {
                            e.preventDefault();
                            apiRequest('/auth/logout', { method: 'POST' }).then(function () {
                                window.location.reload();
                            });
                        });
                    }
                }
                return data;
            }
        } catch (e) {
            // Not authenticated
        }
        return null;
    }

    function formatDate(dateStr) {
        if (!dateStr) return 'Never';
        const d = new Date(dateStr);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function renderTokensTable(tokens) {
        const container = document.getElementById('tokens-list');
        if (!tokens || tokens.length === 0) {
            container.innerHTML =
                '<div class="empty-state">' +
                '<p>No API tokens yet.</p>' +
                '<p class="empty-state-hint">Create a token to authenticate CI/CD pipelines or use <code>terraform login</code>.</p>' +
                '</div>';
            return;
        }

        let html = '<table class="data-table">' +
            '<thead><tr>' +
            '<th>Name</th>' +
            '<th>Scopes</th>' +
            '<th>Last Used</th>' +
            '<th>Expires</th>' +
            '<th>Created</th>' +
            '<th></th>' +
            '</tr></thead><tbody>';

        for (const token of tokens) {
            const scopes = (token.scopes || [])
                .map(function (s) { return s.namespace + ' (' + s.permission + ')'; })
                .join(', ') || 'No scopes';

            html += '<tr>' +
                '<td><strong>' + escapeHtml(token.name) + '</strong></td>' +
                '<td class="text-muted">' + escapeHtml(scopes) + '</td>' +
                '<td>' + formatDate(token.last_used_at) + '</td>' +
                '<td>' + formatDate(token.expires_at) + '</td>' +
                '<td>' + formatDate(token.created_at) + '</td>' +
                '<td><button class="btn btn-danger btn-sm revoke-btn" data-id="' + token.id + '">Revoke</button></td>' +
                '</tr>';
        }

        html += '</tbody></table>';
        container.innerHTML = html;

        container.querySelectorAll('.revoke-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                revokeToken(btn.getAttribute('data-id'));
            });
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async function loadTokens() {
        try {
            const resp = await apiRequest('/api/tokens');
            if (resp.ok) {
                const data = await resp.json();
                renderTokensTable(data.tokens);
            } else if (resp.status === 401) {
                document.getElementById('tokens-list').innerHTML =
                    '<div class="empty-state"><p>Please <a href="/auth/login">sign in</a> to manage tokens.</p></div>';
            } else {
                showError('Failed to load tokens.');
            }
        } catch (e) {
            showError('Error loading tokens: ' + e.message);
        }
    }

    async function loadNamespaceScopes() {
        const scopeList = document.getElementById('scope-list');
        try {
            const resp = await apiRequest('/api/namespaces');
            if (resp.ok) {
                const data = await resp.json();
                if (!data.namespaces || data.namespaces.length === 0) {
                    scopeList.innerHTML = '<p class="form-help">No namespaces available.</p>';
                    return;
                }

                let html = '';
                for (const ns of data.namespaces) {
                    html += '<div class="scope-entry">' +
                        '<label class="checkbox-label">' +
                        '<input type="checkbox" class="scope-checkbox" data-namespace="' + escapeHtml(ns.name) + '" value="read"> ' +
                        '<strong>' + escapeHtml(ns.name) + '</strong> (read)' +
                        '</label>' +
                        '</div>';
                }
                scopeList.innerHTML = html;
            }
        } catch (e) {
            scopeList.innerHTML = '<p class="form-help text-error">Failed to load namespaces.</p>';
        }
    }

    async function createToken(name, expiresInDays, scopes) {
        const body = { name: name, scopes: scopes };
        if (expiresInDays) {
            body.expires_in_days = parseInt(expiresInDays, 10);
        }

        try {
            const resp = await apiRequest('/api/tokens', {
                method: 'POST',
                body: JSON.stringify(body),
            });

            if (resp.ok || resp.status === 201) {
                const data = await resp.json();

                // Show the token value banner
                const banner = document.getElementById('token-created-banner');
                const valueEl = document.getElementById('new-token-value');
                valueEl.textContent = data.token.token_value;
                banner.hidden = false;

                // Reload list
                await loadTokens();
                return true;
            } else {
                const errData = await resp.json().catch(function () { return {}; });
                showError(errData.detail || 'Failed to create token.');
                return false;
            }
        } catch (e) {
            showError('Error creating token: ' + e.message);
            return false;
        }
    }

    async function revokeToken(tokenId) {
        if (!confirm('Are you sure you want to revoke this token? This cannot be undone.')) {
            return;
        }

        try {
            const resp = await apiRequest('/api/tokens/' + tokenId, {
                method: 'DELETE',
            });

            if (resp.ok || resp.status === 204) {
                await loadTokens();
            } else {
                showError('Failed to revoke token.');
            }
        } catch (e) {
            showError('Error revoking token: ' + e.message);
        }
    }

    function setupModal() {
        const modal = document.getElementById('create-token-modal');
        const openBtn = document.getElementById('create-token-btn');
        const closeBtn = modal.querySelector('.modal-close');
        const cancelBtn = modal.querySelector('.modal-cancel');
        const backdrop = modal.querySelector('.modal-backdrop');
        const form = document.getElementById('create-token-form');

        function openModal() {
            modal.hidden = false;
            loadNamespaceScopes();
            document.getElementById('token-name').focus();
        }

        function closeModal() {
            modal.hidden = true;
            form.reset();
        }

        openBtn.addEventListener('click', openModal);
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        backdrop.addEventListener('click', closeModal);

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            const name = document.getElementById('token-name').value.trim();
            const expiryInput = document.getElementById('token-expiry').value;

            const scopes = [];
            document.querySelectorAll('.scope-checkbox:checked').forEach(function (cb) {
                scopes.push({
                    namespace: cb.getAttribute('data-namespace'),
                    permission: cb.value,
                });
            });

            const success = await createToken(name, expiryInput, scopes);
            if (success) {
                closeModal();
            }
        });
    }

    function setupCopyButton() {
        const copyBtn = document.getElementById('copy-token-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', function () {
                const value = document.getElementById('new-token-value').textContent;
                navigator.clipboard.writeText(value).then(function () {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function () { copyBtn.textContent = 'Copy'; }, 2000);
                }).catch(function () {
                    showError('Failed to copy to clipboard.');
                });
            });
        }
    }

    async function init() {
        await checkAuth();
        setupModal();
        setupCopyButton();
        await loadTokens();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
