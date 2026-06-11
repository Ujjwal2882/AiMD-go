/**
 * AiMD-go AI Detection Handler
 * Upload images for infrastructure detection and display results.
 */

const DetectionHandler = {
    currentFile: null,
    pollingIntervals: {},

    /**
     * Initialize detection UI
     */
    init() {
        this._setupDropZone();
        this._setupConfidenceSlider();
        this._setupDetectButton();
        this._loadDetectionHistory();
    },

    /**
     * Setup image drop zone
     */
    _setupDropZone() {
        const dropZone = document.getElementById('detection-drop-zone');
        const fileInput = document.getElementById('detection-file-input');
        if (!dropZone || !fileInput) return;

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files[0]) this._handleImageSelect(e.dataTransfer.files[0]);
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files[0]) this._handleImageSelect(e.target.files[0]);
        });
    },

    /**
     * Handle image selection
     */
    _handleImageSelect(file) {
        this.currentFile = file;
        document.getElementById('btn-detect').disabled = false;

        // Update drop zone text
        const dropZone = document.getElementById('detection-drop-zone');
        const content = dropZone.querySelector('.drop-zone-content');
        content.innerHTML = `
            <i class="fas fa-image drop-icon" style="color: var(--success);"></i>
            <p class="drop-text">${file.name}</p>
            <p class="drop-subtext">${(file.size / 1024 / 1024).toFixed(1)} MB</p>
        `;

        App.showToast(`Image selected: ${file.name}`, 'info');
    },

    /**
     * Setup confidence threshold slider
     */
    _setupConfidenceSlider() {
        const slider = document.getElementById('confidence-slider');
        const value = document.getElementById('confidence-value');
        if (!slider || !value) return;

        slider.addEventListener('input', () => {
            value.textContent = parseFloat(slider.value).toFixed(2);
        });
    },

    /**
     * Setup detect button
     */
    _setupDetectButton() {
        document.getElementById('btn-detect')?.addEventListener('click', () => {
            this._runDetection();
        });
    },

    /**
     * Run AI detection
     */
    async _runDetection() {
        if (!this.currentFile) {
            App.showToast('No image selected', 'warning');
            return;
        }

        const btn = document.getElementById('btn-detect');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Detecting...</span>';

        try {
            const formData = new FormData();
            formData.append('file', this.currentFile);
            formData.append('confidence_threshold', document.getElementById('confidence-slider')?.value || '0.5');

            const result = await API.upload('/api/detect-infrastructure', formData);

            App.showToast(`Detection started! Job: ${result.job_id}`, 'info');

            // Start polling for results
            this._pollForResults(result.job_id);

        } catch (error) {
            App.showToast(`Detection failed: ${error.message}`, 'error');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search"></i> <span>Run Detection</span>';
        }
    },

    /**
     * Poll for detection results
     */
    _pollForResults(jobId) {
        let attempts = 0;
        const maxAttempts = 60;

        const interval = setInterval(async () => {
            attempts++;
            try {
                const result = await API.get(`/api/detections/${jobId}`);

                if (result.status === 'completed') {
                    clearInterval(interval);
                    this._handleDetectionComplete(result);
                } else if (result.status === 'failed') {
                    clearInterval(interval);
                    App.showToast(`Detection failed: ${result.error}`, 'error');
                    this._resetDetectButton();
                }

                if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    App.showToast('Detection timed out', 'warning');
                    this._resetDetectButton();
                }
            } catch (e) {
                // Continue polling
            }
        }, 2000);
    },

    /**
     * Handle completed detection
     */
    async _handleDetectionComplete(result) {
        this._resetDetectButton();

        App.showToast(
            `✅ Detection complete! ${result.detections_count} objects found in ${result.processing_time_sec}s`,
            'success'
        );

        // Show results stats
        this._showDetectionStats(result);

        // Load detection layer on map
        if (result.layer_id) {
            await LayerManager.loadAndDisplayLayer(result.layer_id);
            LayerManager.refreshLayersList();
        }

        // Refresh history
        this._loadDetectionHistory();
    },

    /**
     * Show detection statistics
     */
    _showDetectionStats(result) {
        const container = document.getElementById('detection-results');
        const statsGrid = document.getElementById('detection-stats');
        if (!container || !statsGrid) return;

        container.classList.remove('hidden');

        let html = `
            <div class="stat-item">
                <div class="stat-value">${result.detections_count}</div>
                <div class="stat-label">Objects Found</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${result.processing_time_sec}s</div>
                <div class="stat-label">Processing Time</div>
            </div>
        `;

        // Add per-class stats
        if (result.statistics) {
            for (const [cls, count] of Object.entries(result.statistics)) {
                html += `
                    <div class="stat-item">
                        <div class="stat-value">${count}</div>
                        <div class="stat-label">${cls.replace(/_/g, ' ')}</div>
                    </div>
                `;
            }
        }

        statsGrid.innerHTML = html;
    },

    /**
     * Load detection history
     */
    async _loadDetectionHistory() {
        try {
            const data = await API.get('/api/detections');
            const list = document.getElementById('detection-list');
            if (!list) return;

            if (!data.detections || data.detections.length === 0) {
                list.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 16px;">No detections yet</p>';
                return;
            }

            list.innerHTML = data.detections.map(det => `
                <div class="detection-item">
                    <div class="detection-item-header">
                        <span style="font-weight: 600; font-size: 12px;">${det.image_name || det.job_id}</span>
                        <span class="detection-status ${det.status}">${det.status}</span>
                    </div>
                    <div style="font-size: 11px; color: var(--text-muted);">
                        ${det.detections_count || 0} detections • ${det.processing_time_sec || 0}s
                        ${det.demo_mode ? ' • <span style="color: var(--warning);">Demo</span>' : ''}
                    </div>
                </div>
            `).join('');
        } catch (e) {
            // Ignore
        }
    },

    /**
     * Reset detect button state
     */
    _resetDetectButton() {
        const btn = document.getElementById('btn-detect');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search"></i> <span>Run Detection</span>';
        }
    },
};


/**
 * ═══════════════════════════════════════════════════════
 * AiMD-go Change Detection Handler
 * Upload two bitemporal images and detect pixel-level changes.
 * ═══════════════════════════════════════════════════════
 */

const ChangeDetectionHandler = {
    t1File: null,
    t2File: null,
    currentMaskB64: null,
    currentOverlayB64: null,

    /**
     * Initialize change detection UI
     */
    init() {
        this._setupDropZones();
        this._setupConfidenceSlider();
        this._setupButtons();
        this._setupViewToggle();
    },

    /**
     * Setup drag-drop zones for T1 and T2
     */
    _setupDropZones() {
        this._setupSingleDropZone('t1');
        this._setupSingleDropZone('t2');
    },

    /**
     * Setup a single drop zone (t1 or t2)
     */
    _setupSingleDropZone(id) {
        const dropZone = document.getElementById(`change-drop-${id}`);
        const fileInput = document.getElementById(`change-file-${id}`);
        if (!dropZone || !fileInput) return;

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files[0]) {
                this._handleFileSelect(id, e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files[0]) {
                this._handleFileSelect(id, e.target.files[0]);
            }
        });
    },

    /**
     * Handle file selection for T1 or T2
     */
    _handleFileSelect(id, file) {
        if (id === 't1') {
            this.t1File = file;
        } else {
            this.t2File = file;
        }

        // Show image preview
        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.getElementById(`change-preview-${id}`);
            const content = document.getElementById(`change-drop-content-${id}`);
            const dropZone = document.getElementById(`change-drop-${id}`);
            const box = document.getElementById(`change-box-${id}`);

            if (preview) {
                preview.src = e.target.result;
                preview.classList.remove('hidden');
            }
            if (content) content.classList.add('hidden');
            if (dropZone) dropZone.classList.add('has-image');
            if (box) box.classList.add('loaded');
        };
        reader.readAsDataURL(file);

        App.showToast(`${id.toUpperCase()} image loaded: ${file.name}`, 'info');
        this._updateButtonStates();
    },

    /**
     * Update button enabled/disabled states
     */
    _updateButtonStates() {
        const bothLoaded = this.t1File && this.t2File;
        const anyLoaded = this.t1File || this.t2File || this.currentMaskB64;
        const btnServer = document.getElementById('btn-change-detect');
        const btnClient = document.getElementById('btn-change-client');
        const btnClear = document.getElementById('btn-change-clear');

        if (btnServer) btnServer.disabled = !bothLoaded;
        if (btnClient) btnClient.disabled = !bothLoaded;
        if (btnClear) btnClear.disabled = !anyLoaded;
    },

    /**
     * Setup confidence slider for change detection
     */
    _setupConfidenceSlider() {
        const slider = document.getElementById('change-confidence-slider');
        const value = document.getElementById('change-confidence-value');
        if (!slider || !value) return;

        slider.addEventListener('input', () => {
            value.textContent = parseInt(slider.value);
        });
    },

    /**
     * Setup action buttons
     */
    _setupButtons() {
        // Server-side change detection
        document.getElementById('btn-change-detect')?.addEventListener('click', () => {
            this._runServerDetection();
        });

        // Client-side quick diff
        document.getElementById('btn-change-client')?.addEventListener('click', () => {
            this._runClientDiff();
        });

        // Clear images
        document.getElementById('btn-change-clear')?.addEventListener('click', () => {
            this.clearImages();
        });
    },

    /**
     * Clear loaded images and results
     */
    clearImages() {
        this.t1File = null;
        this.t2File = null;
        this.currentMaskB64 = null;
        this.currentOverlayB64 = null;

        // Reset T1 UI
        const previewT1 = document.getElementById('change-preview-t1');
        const contentT1 = document.getElementById('change-drop-content-t1');
        const dropZoneT1 = document.getElementById('change-drop-t1');
        const boxT1 = document.getElementById('change-box-t1');
        if (previewT1) { previewT1.src = ''; previewT1.classList.add('hidden'); }
        if (contentT1) contentT1.classList.remove('hidden');
        if (dropZoneT1) dropZoneT1.classList.remove('has-image');
        if (boxT1) boxT1.classList.remove('loaded');
        const fileInputT1 = document.getElementById('change-file-t1');
        if (fileInputT1) fileInputT1.value = '';

        // Reset T2 UI
        const previewT2 = document.getElementById('change-preview-t2');
        const contentT2 = document.getElementById('change-drop-content-t2');
        const dropZoneT2 = document.getElementById('change-drop-t2');
        const boxT2 = document.getElementById('change-box-t2');
        if (previewT2) { previewT2.src = ''; previewT2.classList.add('hidden'); }
        if (contentT2) contentT2.classList.remove('hidden');
        if (dropZoneT2) dropZoneT2.classList.remove('has-image');
        if (boxT2) boxT2.classList.remove('loaded');
        const fileInputT2 = document.getElementById('change-file-t2');
        if (fileInputT2) fileInputT2.value = '';

        // Reset Result UI
        const imgResult = document.getElementById('change-result-img');
        const displayResult = document.getElementById('change-result-display');
        const placeholderResult = document.getElementById('change-result-placeholder');
        if (imgResult) imgResult.src = '';
        if (displayResult) displayResult.classList.add('hidden');
        if (placeholderResult) placeholderResult.classList.remove('hidden');
        
        // Hide Stats and Toggle
        document.getElementById('change-stats')?.classList.add('hidden');
        document.getElementById('change-view-toggle')?.classList.add('hidden');
        
        this._updateButtonStates();
        App.showToast('Images cleared', 'info');
    },

    /**
     * Setup view toggle (overlay vs mask)
     */
    _setupViewToggle() {
        document.querySelectorAll('.change-view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.change-view-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const view = btn.dataset.view;
                const img = document.getElementById('change-result-img');
                if (!img) return;

                if (view === 'overlay' && this.currentOverlayB64) {
                    img.src = `data:image/png;base64,${this.currentOverlayB64}`;
                } else if (view === 'mask' && this.currentMaskB64) {
                    img.src = `data:image/png;base64,${this.currentMaskB64}`;
                }
            });
        });
    },

    /**
     * Show processing state in result box
     */
    _showProcessing() {
        document.getElementById('change-result-placeholder')?.classList.add('hidden');
        document.getElementById('change-result-display')?.classList.add('hidden');
        document.getElementById('change-processing')?.classList.remove('hidden');
    },

    /**
     * Hide processing state
     */
    _hideProcessing() {
        document.getElementById('change-processing')?.classList.add('hidden');
    },

    /**
     * Run server-side change detection (via backend API)
     */
    async _runServerDetection() {
        if (!this.t1File || !this.t2File) {
            App.showToast('Please upload both T1 and T2 images', 'warning');
            return;
        }

        const btn = document.getElementById('btn-change-detect');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Analyzing...</span>';
        this._showProcessing();

        try {
            const formData = new FormData();
            formData.append('t1_file', this.t1File);
            formData.append('t2_file', this.t2File);
            formData.append('confidence_threshold',
                document.getElementById('change-confidence-slider')?.value || '145');

            const result = await API.upload('/api/detect-change', formData);
            App.showToast(`Change detection started! Job: ${result.job_id}`, 'info');

            // Poll for results
            this._pollForResults(result.job_id);

        } catch (error) {
            App.showToast(`Change detection failed: ${error.message}`, 'error');
            this._hideProcessing();
            this._resetChangeButton();
        }
    },

    /**
     * Poll for server-side results
     */
    _pollForResults(jobId) {
        let attempts = 0;
        const maxAttempts = 120; // 4 minutes max

        const interval = setInterval(async () => {
            attempts++;
            try {
                const result = await API.get(`/api/change-detections/${jobId}`);

                if (result.status === 'completed') {
                    clearInterval(interval);
                    this._hideProcessing();
                    this._showResult(result);
                    this._resetChangeButton();
                } else if (result.status === 'failed') {
                    clearInterval(interval);
                    this._hideProcessing();
                    App.showToast(`Change detection failed: ${result.error}`, 'error');
                    this._resetChangeButton();
                }

                if (attempts >= maxAttempts) {
                    clearInterval(interval);
                    this._hideProcessing();
                    App.showToast('Change detection timed out', 'warning');
                    this._resetChangeButton();
                }
            } catch (e) {
                // Continue polling
            }
        }, 2000);
    },

    /**
     * Show change detection result
     */
    _showResult(result) {
        // Store base64 data for view toggle
        this.currentMaskB64 = result.change_mask_b64;
        this.currentOverlayB64 = result.overlay_b64;

        // Show overlay by default
        const img = document.getElementById('change-result-img');
        const display = document.getElementById('change-result-display');
        const placeholder = document.getElementById('change-result-placeholder');

        if (img) {
            img.src = `data:image/png;base64,${result.overlay_b64 || result.change_mask_b64}`;
        }
        if (display) display.classList.remove('hidden');
        if (placeholder) placeholder.classList.add('hidden');

        // Show stats
        this._showStats(result);

        // Show view toggle
        document.getElementById('change-view-toggle')?.classList.remove('hidden');

        App.showToast(
            `✅ Change detection complete! ${result.change_percentage}% area changed (${result.processing_time_sec}s)`,
            'success'
        );
    },

    /**
     * Show change detection statistics
     */
    _showStats(result) {
        const container = document.getElementById('change-stats');
        const grid = document.getElementById('change-stats-grid');
        if (!container || !grid) return;

        container.classList.remove('hidden');

        grid.innerHTML = `
            <div class="stat-item">
                <div class="stat-value">${result.change_percentage}%</div>
                <div class="stat-label">Area Changed</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${result.n_change_regions}</div>
                <div class="stat-label">Change Regions</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${(result.changed_pixels / 1000).toFixed(1)}k</div>
                <div class="stat-label">Changed Pixels</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${result.processing_time_sec}s</div>
                <div class="stat-label">Processing Time</div>
            </div>
        `;
    },

    /**
     * Run client-side pixel difference (no server needed)
     */
    async _runClientDiff() {
        if (!this.t1File || !this.t2File) {
            App.showToast('Please upload both T1 and T2 images', 'warning');
            return;
        }

        const btn = document.getElementById('btn-change-client');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Computing...</span>';
        this._showProcessing();

        try {
            const startTime = performance.now();

            // Load both images into canvas
            const [img1, img2] = await Promise.all([
                this._loadImageFromFile(this.t1File),
                this._loadImageFromFile(this.t2File),
            ]);

            // Use T1 dimensions as reference
            const w = img1.width;
            const h = img1.height;

            // Create canvases
            const canvas1 = document.createElement('canvas');
            canvas1.width = w;
            canvas1.height = h;
            const ctx1 = canvas1.getContext('2d');
            ctx1.drawImage(img1, 0, 0, w, h);

            const canvas2 = document.createElement('canvas');
            canvas2.width = w;
            canvas2.height = h;
            const ctx2 = canvas2.getContext('2d');
            ctx2.drawImage(img2, 0, 0, w, h);

            // Get pixel data
            const data1 = ctx1.getImageData(0, 0, w, h);
            const data2 = ctx2.getImageData(0, 0, w, h);
            const pixels1 = data1.data;
            const pixels2 = data2.data;

            // Compute diff
            const threshold = parseInt(
                document.getElementById('change-confidence-slider')?.value || '145'
            );
            // Map 80-200 → pixel threshold 15-80
            const pixelThresh = Math.max(15, Math.min(80, threshold * 0.3));

            // Create overlay output
            const outputCanvas = document.createElement('canvas');
            outputCanvas.width = w;
            outputCanvas.height = h;
            const ctxOut = outputCanvas.getContext('2d');
            // Draw T2 as base
            ctxOut.drawImage(img2, 0, 0, w, h);
            const outputData = ctxOut.getImageData(0, 0, w, h);
            const outPixels = outputData.data;

            // Create mask output
            const maskCanvas = document.createElement('canvas');
            maskCanvas.width = w;
            maskCanvas.height = h;
            const ctxMask = maskCanvas.getContext('2d');
            const maskData = ctxMask.createImageData(w, h);
            const maskPixels = maskData.data;

            let changedPixels = 0;
            const totalPixels = w * h;

            for (let i = 0; i < pixels1.length; i += 4) {
                const dr = Math.abs(pixels1[i] - pixels2[i]);
                const dg = Math.abs(pixels1[i + 1] - pixels2[i + 1]);
                const db = Math.abs(pixels1[i + 2] - pixels2[i + 2]);
                const diff = (dr + dg + db) / 3;

                if (diff > pixelThresh) {
                    changedPixels++;

                    // Overlay: magenta tint on changed areas
                    outPixels[i] = Math.min(255, outPixels[i] + 120);     // R
                    outPixels[i + 1] = Math.floor(outPixels[i + 1] * 0.4); // G
                    outPixels[i + 2] = Math.min(255, outPixels[i + 2] + 60); // B

                    // Mask: white on black
                    maskPixels[i] = 255;
                    maskPixels[i + 1] = 255;
                    maskPixels[i + 2] = 255;
                    maskPixels[i + 3] = 255;
                } else {
                    // Mask: black
                    maskPixels[i] = 0;
                    maskPixels[i + 1] = 0;
                    maskPixels[i + 2] = 0;
                    maskPixels[i + 3] = 255;
                }
            }

            ctxOut.putImageData(outputData, 0, 0);
            ctxMask.putImageData(maskData, 0, 0);

            const changePercentage = ((changedPixels / totalPixels) * 100).toFixed(2);
            const processingTime = ((performance.now() - startTime) / 1000).toFixed(2);

            // Convert canvases to base64
            const overlayB64 = outputCanvas.toDataURL('image/png').split(',')[1];
            const maskB64 = maskCanvas.toDataURL('image/png').split(',')[1];

            this._hideProcessing();
            this._showResult({
                overlay_b64: overlayB64,
                change_mask_b64: maskB64,
                change_percentage: changePercentage,
                n_change_regions: '—',
                changed_pixels: changedPixels,
                processing_time_sec: processingTime,
                method: 'client_diff',
            });

            this._resetClientButton();

        } catch (error) {
            this._hideProcessing();
            App.showToast(`Client diff failed: ${error.message}`, 'error');
            this._resetClientButton();
        }
    },

    /**
     * Load an image file into an HTMLImageElement
     */
    _loadImageFromFile(file) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = URL.createObjectURL(file);
        });
    },

    /**
     * Reset change detection button
     */
    _resetChangeButton() {
        const btn = document.getElementById('btn-change-detect');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-search-plus"></i> <span>Run Change Detection</span>';
        }
    },

    /**
     * Reset client diff button
     */
    _resetClientButton() {
        const btn = document.getElementById('btn-change-client');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-bolt"></i> <span>Quick Diff (Client-side)</span>';
        }
    },
};
