/**
 * AiMD-go Upload Handler
 * Manages file upload UI: drag-drop, CSV preview, column mapping, and upload to API.
 */

const UploadHandler = {
    currentFile: null,
    currentFormat: 'csv',
    csvData: null,

    /**
     * Initialize upload UI
     */
    init() {
        this._setupDropZone();
        this._setupTabs();
        this._setupColumnMapping();
        this._setupUploadButton();
    },

    /**
     * Setup drag-and-drop zone
     */
    _setupDropZone() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');

        if (!dropZone || !fileInput) return;

        // Drag events
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
            const file = e.dataTransfer.files[0];
            if (file) this._handleFileSelect(file);
        });

        // Click to browse
        fileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) this._handleFileSelect(file);
        });

        // Remove file button
        document.getElementById('btn-remove-file')?.addEventListener('click', () => {
            this._clearFile();
        });
    },

    /**
     * Setup format tabs
     */
    _setupTabs() {
        document.querySelectorAll('.upload-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                // Update active tab
                document.querySelectorAll('.upload-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                this.currentFormat = tab.dataset.format;
                this._updateAcceptedFileTypes();
                this._clearFile();
            });
        });
    },

    /**
     * Update file input accepted types
     */
    _updateAcceptedFileTypes() {
        const fileInput = document.getElementById('file-input');
        const accepts = {
            csv: '.csv',
            shapefile: '.zip',
            geojson: '.json,.geojson',
        };
        fileInput.accept = accepts[this.currentFormat] || '*';
    },

    /**
     * Handle file selection
     */
    _handleFileSelect(file) {
        this.currentFile = file;

        // Show file info
        document.getElementById('file-info').classList.remove('hidden');
        document.getElementById('file-name').textContent = file.name;
        document.getElementById('file-size').textContent = this._formatFileSize(file.size);

        // Enable upload button
        document.getElementById('btn-upload').disabled = false;

        // If CSV, parse and show preview
        if (this.currentFormat === 'csv' && file.name.toLowerCase().endsWith('.csv')) {
            this._parseCSVPreview(file);
        } else {
            document.getElementById('csv-mapping')?.classList.add('hidden');
        }

        App.showToast(`File selected: ${file.name}`, 'info');
    },

    /**
     * Parse CSV and show preview with column mapping
     */
    _parseCSVPreview(file) {
        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            preview: 10,
            complete: (results) => {
                this.csvData = results;
                const headers = results.meta.fields || [];
                const data = results.data;

                // Show column mapping
                const csvMapping = document.getElementById('csv-mapping');
                csvMapping.classList.remove('hidden');

                // Populate selects
                const latSelect = document.getElementById('lat-column');
                const lonSelect = document.getElementById('lon-column');

                latSelect.innerHTML = '<option value="">— Auto-detect —</option>';
                lonSelect.innerHTML = '<option value="">— Auto-detect —</option>';

                headers.forEach(h => {
                    latSelect.innerHTML += `<option value="${h}">${h}</option>`;
                    lonSelect.innerHTML += `<option value="${h}">${h}</option>`;
                });

                // Auto-detect columns
                const latPatterns = ['lat', 'latitude', 'y', 'north'];
                const lonPatterns = ['lon', 'lng', 'longitude', 'x', 'east', 'long'];

                const detectedLat = headers.find(h =>
                    latPatterns.some(p => h.toLowerCase().includes(p))
                );
                const detectedLon = headers.find(h =>
                    lonPatterns.some(p => h.toLowerCase().includes(p))
                );

                if (detectedLat) latSelect.value = detectedLat;
                if (detectedLon) lonSelect.value = detectedLon;

                // Preview table
                this._renderPreviewTable(headers, data);
            },
            error: (error) => {
                App.showToast(`CSV parse error: ${error.message}`, 'error');
            },
        });
    },

    /**
     * Render preview table
     */
    _renderPreviewTable(headers, data) {
        const thead = document.getElementById('preview-thead');
        const tbody = document.getElementById('preview-tbody');

        thead.innerHTML = '<tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr>';
        tbody.innerHTML = data.slice(0, 5).map(row =>
            '<tr>' + headers.map(h => `<td>${row[h] ?? ''}</td>`).join('') + '</tr>'
        ).join('');

        document.getElementById('preview-count').textContent =
            `(${Math.min(data.length, 5)} of ${data.length} rows)`;
    },

    /**
     * Setup column mapping change handlers
     */
    _setupColumnMapping() {
        // Column selects auto-update the upload parameters
    },

    /**
     * Setup upload button click
     */
    _setupUploadButton() {
        document.getElementById('btn-upload')?.addEventListener('click', () => {
            this._uploadFile();
        });
    },

    /**
     * Upload the selected file to the API
     */
    async _uploadFile() {
        if (!this.currentFile) {
            App.showToast('No file selected', 'warning');
            return;
        }

        const btn = document.getElementById('btn-upload');
        const progress = document.getElementById('upload-progress');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');

        // Disable button and show progress
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Uploading...</span>';
        progress.classList.remove('hidden');
        progressFill.style.width = '10%';
        progressText.textContent = 'Uploading file...';

        try {
            const formData = new FormData();
            formData.append('file', this.currentFile);

            // Add column mapping for CSV
            if (this.currentFormat === 'csv') {
                const latCol = document.getElementById('lat-column')?.value;
                const lonCol = document.getElementById('lon-column')?.value;
                if (latCol) formData.append('lat_column', latCol);
                if (lonCol) formData.append('lon_column', lonCol);
            }

            // Determine endpoint
            const endpoints = {
                csv: '/api/upload-csv',
                shapefile: '/api/upload-shapefile',
                geojson: '/api/upload-geojson',
            };

            const endpoint = endpoints[this.currentFormat];

            // Upload with progress
            const result = await API.upload(endpoint, formData, (pct) => {
                progressFill.style.width = `${Math.min(pct, 90)}%`;
                progressText.textContent = `Uploading... ${pct}%`;
            });

            progressFill.style.width = '95%';
            progressText.textContent = 'Processing...';

            // Success!
            progressFill.style.width = '100%';
            progressText.textContent = 'Complete!';

            App.showToast(
                `✅ ${result.feature_count} features loaded from ${result.layer_name}`,
                'success'
            );

            // Add layer to map
            if (result.layer_id) {
                await LayerManager.loadAndDisplayLayer(result.layer_id);

                // Zoom to bounds
                if (result.bounds) {
                    MapController.zoomToBounds(result.bounds);
                }
            }

            // Refresh layers panel
            LayerManager.refreshLayersList();

            // Clear upload state after delay
            setTimeout(() => {
                this._clearFile();
                progress.classList.add('hidden');
                progressFill.style.width = '0%';
            }, 2000);

        } catch (error) {
            App.showToast(`Upload failed: ${error.message}`, 'error');
            progressFill.style.width = '0%';
            progress.classList.add('hidden');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-upload"></i> <span>Upload & Visualize</span>';
        }
    },

    /**
     * Clear current file selection
     */
    _clearFile() {
        this.currentFile = null;
        this.csvData = null;
        document.getElementById('file-input').value = '';
        document.getElementById('file-info')?.classList.add('hidden');
        document.getElementById('csv-mapping')?.classList.add('hidden');
        document.getElementById('btn-upload').disabled = true;
    },

    /**
     * Format file size for display
     */
    _formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    },
};
