/**
 * Module upload page - file validation, progress indicator, error display, success confirmation.
 */

(function () {
    'use strict';

    const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB
    const SEMVER_RE = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([\w.-]+))?(?:\+([\w.-]+))?$/;

    // DOM elements
    const form = document.getElementById('upload-form');
    const namespaceSelect = document.getElementById('namespace');
    const moduleNameInput = document.getElementById('module-name');
    const providerInput = document.getElementById('provider');
    const versionInput = document.getElementById('version');
    const fileInput = document.getElementById('module-file');
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileUploadContent = fileUploadArea ? fileUploadArea.querySelector('.file-upload-content') : null;
    const fileSelected = document.getElementById('file-selected');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    const fileClear = document.getElementById('file-clear');
    const uploadBtn = document.getElementById('upload-btn');
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const resultContainer = document.getElementById('upload-result');
    const navAuth = document.getElementById('nav-auth');

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(text || ''));
        return div.innerHTML;
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }

    // --- Auth check ---

    async function checkAuth() {
        try {
            const res = await fetch('/auth/me', { credentials: 'same-origin' });
            if (res.ok) {
                const data = await res.json();
                if (navAuth && data.user) {
                    navAuth.innerHTML =
                        '<span class="nav-user">' + escapeHtml(data.user.name || data.user.email) + '</span>' +
                        ' <button class="btn btn-sm" onclick="fetch(\'/auth/logout\',{method:\'POST\',credentials:\'same-origin\'}).then(()=>location.reload())">Sign Out</button>';
                }
                return data;
            }
        } catch (_) { /* not authenticated */ }
        return null;
    }

    // --- Namespace loading ---

    async function loadNamespaces() {
        try {
            const res = await fetch('/api/modules?per_page=1', { credentials: 'same-origin' });
            if (!res.ok) return;
            // We don't have a dedicated namespace list endpoint yet,
            // so extract unique namespaces from the modules list
            const allRes = await fetch('/api/modules?per_page=100', { credentials: 'same-origin' });
            if (!allRes.ok) return;
            const data = await allRes.json();
            const namespaces = [...new Set((data.modules || []).map(function (m) { return m.namespace; }))].sort();
            namespaces.forEach(function (ns) {
                const option = document.createElement('option');
                option.value = ns;
                option.textContent = ns;
                namespaceSelect.appendChild(option);
            });
        } catch (_) { /* ignore */ }
    }

    // --- File validation ---

    function validateFile(file) {
        if (!file) return 'Please select a file.';
        if (file.size > MAX_FILE_SIZE) {
            return 'File size (' + formatBytes(file.size) + ') exceeds the 100 MB limit.';
        }
        if (!file.name.endsWith('.tar.gz') && !file.name.endsWith('.tgz')) {
            return 'File must be a .tar.gz or .tgz archive.';
        }
        return null;
    }

    function showFileInfo(file) {
        if (!file) {
            fileSelected.hidden = true;
            if (fileUploadContent) fileUploadContent.hidden = false;
            return;
        }
        fileName.textContent = file.name;
        fileSize.textContent = '(' + formatBytes(file.size) + ')';
        fileSelected.hidden = false;
        if (fileUploadContent) fileUploadContent.hidden = true;
    }

    function clearFile() {
        fileInput.value = '';
        showFileInfo(null);
    }

    // --- Progress & results ---

    function showProgress() {
        progressContainer.hidden = false;
        resultContainer.hidden = true;
        progressFill.style.width = '0%';
        progressText.textContent = 'Uploading...';
        uploadBtn.disabled = true;
    }

    function updateProgress(pct) {
        progressFill.style.width = pct + '%';
        progressText.textContent = 'Uploading... ' + Math.round(pct) + '%';
    }

    function hideProgress() {
        progressContainer.hidden = true;
        uploadBtn.disabled = false;
    }

    function showResult(success, message) {
        resultContainer.hidden = false;
        resultContainer.className = 'upload-result ' + (success ? 'success' : 'error');
        resultContainer.innerHTML = message;
    }

    // --- Upload ---

    async function uploadModule(e) {
        e.preventDefault();

        // Validate file
        var file = fileInput.files[0];
        var fileError = validateFile(file);
        if (fileError) {
            showResult(false, escapeHtml(fileError));
            return;
        }

        // Validate version
        var version = versionInput.value.trim();
        if (!SEMVER_RE.test(version)) {
            showResult(false, 'Invalid semantic version. Use MAJOR.MINOR.PATCH (e.g., 1.0.0).');
            return;
        }

        var ns = namespaceSelect.value;
        var name = moduleNameInput.value.trim();
        var provider = providerInput.value.trim();

        if (!ns || !name || !provider) {
            showResult(false, 'Please fill in all required fields.');
            return;
        }

        showProgress();

        var formData = new FormData();
        formData.append('file', file);

        var url = '/v1/modules/' + encodeURIComponent(ns) + '/' +
            encodeURIComponent(name) + '/' +
            encodeURIComponent(provider) + '/' +
            encodeURIComponent(version);

        try {
            var xhr = new XMLHttpRequest();

            var uploadPromise = new Promise(function (resolve, reject) {
                xhr.upload.addEventListener('progress', function (evt) {
                    if (evt.lengthComputable) {
                        updateProgress((evt.loaded / evt.total) * 100);
                    }
                });

                xhr.addEventListener('load', function () {
                    resolve({ status: xhr.status, response: xhr.responseText });
                });

                xhr.addEventListener('error', function () {
                    reject(new Error('Network error'));
                });
            });

            xhr.open('POST', url);
            // Include credentials for session auth
            xhr.withCredentials = true;
            // Add CSRF token if available
            var csrfToken = getCsrfToken();
            if (csrfToken) {
                xhr.setRequestHeader('X-CSRF-Token', csrfToken);
            }

            xhr.send(formData);

            var result = await uploadPromise;
            hideProgress();

            if (result.status === 201) {
                var data = JSON.parse(result.response);
                var moduleUrl = '/modules/' + escapeHtml(ns) + '/' + escapeHtml(name) + '/' + escapeHtml(provider);
                showResult(true,
                    '<strong>Module uploaded successfully!</strong><br>' +
                    '<code>' + escapeHtml(ns) + '/' + escapeHtml(name) + '/' + escapeHtml(provider) +
                    ' v' + escapeHtml(data.version) + '</code><br>' +
                    '<a href="' + moduleUrl + '">View module &rarr;</a>'
                );
                form.reset();
                clearFile();
            } else {
                var errMsg = 'Upload failed.';
                try {
                    var errData = JSON.parse(result.response);
                    if (errData.errors && errData.errors[0]) {
                        errMsg = errData.errors[0].detail || errMsg;
                    } else if (errData.detail) {
                        errMsg = errData.detail;
                    }
                } catch (_) { /* ignore parse error */ }
                showResult(false, escapeHtml(errMsg));
            }
        } catch (err) {
            hideProgress();
            showResult(false, 'Upload failed: ' + escapeHtml(err.message));
        }
    }

    // --- Drag & drop ---

    function setupDragDrop() {
        if (!fileUploadArea) return;

        fileUploadArea.addEventListener('dragover', function (e) {
            e.preventDefault();
            fileUploadArea.classList.add('drag-over');
        });

        fileUploadArea.addEventListener('dragleave', function () {
            fileUploadArea.classList.remove('drag-over');
        });

        fileUploadArea.addEventListener('drop', function (e) {
            e.preventDefault();
            fileUploadArea.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                showFileInfo(e.dataTransfer.files[0]);
            }
        });
    }

    // --- Init ---

    function init() {
        checkAuth();
        loadNamespaces();
        setupDragDrop();

        if (fileInput) {
            fileInput.addEventListener('change', function () {
                showFileInfo(fileInput.files[0] || null);
            });
        }

        if (fileClear) {
            fileClear.addEventListener('click', clearFile);
        }

        if (form) {
            form.addEventListener('submit', uploadModule);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
