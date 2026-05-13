/* Namespace management UI - list, create, manage permissions (admin only). */

(function () {
    'use strict';

    let csrfToken = '';
    let isAdmin = false;
    let currentNamespace = '';

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : csrfToken;
    }

    function showError(message) {
        const el = document.getElementById('error-message');
        if (el) {
            el.textContent = message;
            el.hidden = false;
            setTimeout(function () { el.hidden = true; }, 5000);
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

        // Update CSRF token from response header
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
                // Check if user is admin (has write permissions on any namespace or is in admin group)
                if (data.permissions) {
                    for (var ns in data.permissions) {
                        if (data.permissions[ns].indexOf('write') !== -1) {
                            isAdmin = true;
                            break;
                        }
                    }
                }
                return data;
            }
        } catch (e) {
            // Not authenticated
        }
        return null;
    }

    function renderNamespaceCard(ns) {
        var permBadges = (ns.permissions || []).map(function (p) {
            return '<span class="badge badge-' + p + '">' + p + '</span>';
        }).join(' ');

        return (
            '<div class="namespace-card">' +
            '  <div class="namespace-card-header">' +
            '    <h3 class="namespace-name">' + escapeHtml(ns.name) + '</h3>' +
            '    <span class="namespace-module-count">' + ns.module_count + ' module' + (ns.module_count !== 1 ? 's' : '') + '</span>' +
            '  </div>' +
            (ns.display_name ? '  <p class="namespace-display-name">' + escapeHtml(ns.display_name) + '</p>' : '') +
            (ns.description ? '  <p class="namespace-description">' + escapeHtml(ns.description) + '</p>' : '') +
            '  <div class="namespace-card-footer">' +
            '    <div class="namespace-permissions">' + permBadges + '</div>' +
            '    <button class="btn btn-secondary btn-sm manage-perms-btn" data-namespace="' + escapeHtml(ns.name) + '">Permissions</button>' +
            '  </div>' +
            '</div>'
        );
    }

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    async function loadNamespaces() {
        var container = document.getElementById('namespaces-list');
        try {
            var resp = await apiRequest('/api/namespaces');
            if (!resp.ok) {
                container.innerHTML = '<p class="empty-state">Unable to load namespaces.</p>';
                return;
            }
            var data = await resp.json();
            var namespaces = data.namespaces || [];

            if (namespaces.length === 0) {
                container.innerHTML = '<p class="empty-state">No namespaces found. Contact an administrator to create one.</p>';
                return;
            }

            container.innerHTML = namespaces.map(renderNamespaceCard).join('');

            // Attach permission buttons
            var btns = container.querySelectorAll('.manage-perms-btn');
            btns.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    openPermissionsModal(btn.getAttribute('data-namespace'));
                });
            });
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Error loading namespaces.</p>';
        }
    }

    async function openPermissionsModal(namespace) {
        currentNamespace = namespace;
        var modal = document.getElementById('permissions-modal');
        var nameEl = document.getElementById('perm-ns-name');
        nameEl.textContent = namespace;
        modal.hidden = false;

        // Show add form only for admins
        var addForm = document.getElementById('add-perm-form');
        addForm.hidden = !isAdmin;

        await loadPermissions(namespace);
    }

    async function loadPermissions(namespace) {
        var container = document.getElementById('permissions-list');
        container.innerHTML = '<div class="loading-indicator"><div class="spinner"></div></div>';

        try {
            var resp = await apiRequest('/api/namespaces/' + encodeURIComponent(namespace) + '/permissions');
            if (!resp.ok) {
                container.innerHTML = '<p class="empty-state">Unable to load permissions.</p>';
                return;
            }
            var data = await resp.json();
            var permissions = data.permissions || [];

            if (permissions.length === 0) {
                container.innerHTML = '<p class="empty-state">No permissions configured.</p>';
                return;
            }

            var rows = permissions.map(function (p) {
                var deleteBtn = isAdmin
                    ? '<button class="btn btn-danger btn-sm delete-perm-btn" data-id="' + p.id + '">Remove</button>'
                    : '';
                return (
                    '<tr>' +
                    '  <td>' + escapeHtml(p.group_name) + '</td>' +
                    '  <td><span class="badge badge-' + p.permission_level + '">' + p.permission_level + '</span></td>' +
                    '  <td>' + deleteBtn + '</td>' +
                    '</tr>'
                );
            }).join('');

            container.innerHTML =
                '<table class="permissions-table">' +
                '<thead><tr><th>Group</th><th>Level</th><th></th></tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '</table>';

            // Attach delete buttons
            var delBtns = container.querySelectorAll('.delete-perm-btn');
            delBtns.forEach(function (btn) {
                btn.addEventListener('click', function () {
                    deletePermission(currentNamespace, btn.getAttribute('data-id'));
                });
            });
        } catch (e) {
            container.innerHTML = '<p class="empty-state">Error loading permissions.</p>';
        }
    }

    async function deletePermission(namespace, permId) {
        if (!confirm('Are you sure you want to remove this permission?')) return;

        try {
            var resp = await apiRequest(
                '/api/namespaces/' + encodeURIComponent(namespace) + '/permissions/' + permId,
                { method: 'DELETE' }
            );
            if (resp.ok || resp.status === 204) {
                await loadPermissions(namespace);
                await loadNamespaces();
            } else {
                var data = await resp.json();
                showError(data.detail || 'Failed to delete permission.');
            }
        } catch (e) {
            showError('Error deleting permission.');
        }
    }

    function closeModal(modal) {
        modal.hidden = true;
    }

    function initModals() {
        document.querySelectorAll('.modal-close, .modal-cancel, .modal-backdrop').forEach(function (el) {
            el.addEventListener('click', function () {
                var modal = el.closest('.modal');
                if (modal) closeModal(modal);
            });
        });
    }

    function initCreateNamespace() {
        var btn = document.getElementById('create-ns-btn');
        var modal = document.getElementById('create-ns-modal');
        var form = document.getElementById('create-ns-form');

        if (btn) {
            btn.addEventListener('click', function () {
                modal.hidden = false;
            });
        }

        if (form) {
            form.addEventListener('submit', async function (e) {
                e.preventDefault();
                var name = document.getElementById('ns-name').value.trim();
                var displayName = document.getElementById('ns-display-name').value.trim();
                var description = document.getElementById('ns-description').value.trim();

                try {
                    var resp = await apiRequest('/api/namespaces', {
                        method: 'POST',
                        body: JSON.stringify({
                            name: name,
                            display_name: displayName || null,
                            description: description || null,
                        }),
                    });

                    if (resp.ok || resp.status === 201) {
                        closeModal(modal);
                        form.reset();
                        await loadNamespaces();
                    } else {
                        var data = await resp.json();
                        showError(data.detail || 'Failed to create namespace.');
                    }
                } catch (err) {
                    showError('Error creating namespace.');
                }
            });
        }
    }

    function initAddPermission() {
        var form = document.getElementById('add-perm-form');
        if (form) {
            form.addEventListener('submit', async function (e) {
                e.preventDefault();
                var group = document.getElementById('perm-group').value.trim();
                var level = document.getElementById('perm-level').value;

                if (!currentNamespace || !group) return;

                try {
                    var resp = await apiRequest(
                        '/api/namespaces/' + encodeURIComponent(currentNamespace) + '/permissions',
                        {
                            method: 'POST',
                            body: JSON.stringify({
                                group_name: group,
                                permission_level: level,
                            }),
                        }
                    );

                    if (resp.ok || resp.status === 201) {
                        document.getElementById('perm-group').value = '';
                        await loadPermissions(currentNamespace);
                        await loadNamespaces();
                    } else {
                        var data = await resp.json();
                        showError(data.detail || 'Failed to add permission.');
                    }
                } catch (err) {
                    showError('Error adding permission.');
                }
            });
        }
    }

    async function init() {
        var authData = await checkAuth();

        // Show create button for admins
        if (isAdmin) {
            var btn = document.getElementById('create-ns-btn');
            if (btn) btn.hidden = false;
        }

        initModals();
        initCreateNamespace();
        initAddPermission();
        await loadNamespaces();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
