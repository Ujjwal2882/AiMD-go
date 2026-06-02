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
