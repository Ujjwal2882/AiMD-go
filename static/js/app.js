/**
 * AiMD-go Main Application Controller
 * Initializes all modules, handles navigation, and global UI state.
 */

const App = {
    currentPanel: null,

    /**
     * Initialize the application
     */
    init() {
        console.log('🌍 AiMD-go starting...');

        // Initialize map
        MapController.init();

        // Initialize modules
        UploadHandler.init();
        LayerManager.init();
        DetectionHandler.init();
        ChangeDetectionHandler.init();
        Dashboard.init();

        // Setup navigation
        this._setupNavigation();

        // Setup search
        this._setupSearch();

        // Setup export
        this._setupExport();

        // Load existing layers onto map
        this._loadExistingLayers();

        console.log('🌍 AiMD-go ready!');
    },

    /**
     * Setup sidebar navigation
     */
    _setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const panel = item.dataset.panel;

                // Update active nav
                document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
                item.classList.add('active');

                // Handle panel
                if (panel === 'map') {
                    this.closeAllPanels();
                } else {
                    this.openPanel(panel);
                }
            });
        });
    },

    /**
     * Open a panel
     */
    openPanel(name) {
        this.closeAllPanels();

        const panel = document.getElementById(`panel-${name}`);
        if (panel) {
            panel.classList.remove('hidden');
            this.currentPanel = name;

            // Refresh data when panel opens
            if (name === 'dashboard') Dashboard.refresh();
            if (name === 'layers') LayerManager.refreshLayersList();
            if (name === 'detection') DetectionHandler._loadDetectionHistory();
        }
    },

    /**
     * Close all panels
     */
    closeAllPanels() {
        document.querySelectorAll('.panel').forEach(p => p.classList.add('hidden'));
        this.currentPanel = null;
    },

    /**
     * Setup spatial search
     */
    _setupSearch() {
        document.getElementById('btn-search')?.addEventListener('click', async () => {
            const lat = parseFloat(document.getElementById('search-lat')?.value);
            const lon = parseFloat(document.getElementById('search-lon')?.value);
            const radius = parseFloat(document.getElementById('search-radius')?.value) || 500;

            if (isNaN(lat) || isNaN(lon)) {
                this.showToast('Please enter valid coordinates', 'warning');
                return;
            }

            try {
                const results = await API.get(
                    `/api/features/nearby?lat=${lat}&lon=${lon}&radius=${radius}`
                );

                // Show search radius on map
                MapController.addSearchRadius(lat, lon, radius);

                // Display results
                const container = document.getElementById('search-results');
                const list = document.getElementById('search-results-list');
                const count = document.getElementById('search-count');
                container.classList.remove('hidden');
                count.textContent = results.count;

                if (results.count === 0) {
                    list.innerHTML = '<p style="color: var(--text-muted); padding: 12px;">No features found in this area</p>';
                } else {
                    list.innerHTML = results.results.slice(0, 20).map(r => `
                        <div class="layer-card" style="margin-bottom: 6px;">
                            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px;">
                                ${r.layer_name}
                            </div>
                            <div style="font-size: 11px; color: var(--text-muted);">
                                <i class="fas fa-ruler"></i> ${r.distance_m}m away
                            </div>
                        </div>
                    `).join('');
                }

                this.showToast(`Found ${results.count} features within ${radius}m`, 'success');
            } catch (error) {
                this.showToast(`Search failed: ${error.message}`, 'error');
            }
        });

        // Click-on-map search mode
        document.getElementById('btn-search-click')?.addEventListener('click', () => {
            MapController.enableSearchClickMode();
        });
    },

    /**
     * Setup export buttons
     */
    _setupExport() {
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const format = btn.dataset.format;
                const layerId = document.getElementById('export-layer')?.value;

                if (!layerId) {
                    this.showToast('Please select a layer to export', 'warning');
                    return;
                }

                // Trigger download
                API.download(`/api/layers/${layerId}/export?format=${format}`);
                this.showToast(`Downloading ${format.toUpperCase()} export...`, 'info');
            });
        });
    },

    /**
     * Load existing layers onto the map on startup
     */
    async _loadExistingLayers() {
        try {
            const data = await API.get('/api/layers');
            for (const layer of (data.layers || [])) {
                if (layer.visible !== false) {
                    await LayerManager.loadAndDisplayLayer(layer.id);
                }
            }
            LayerManager._updateBadge();
        } catch (e) {
            // First run — no layers yet
        }
    },

    /**
     * Show a toast notification
     */
    showToast(message, type = 'info', duration = 4000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle',
        };

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas ${icons[type] || icons.info} toast-icon"></i>
            <span class="toast-message">${message}</span>
        `;

        container.appendChild(toast);

        // Auto-remove
        setTimeout(() => {
            toast.classList.add('removing');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
};

// ──────────────────── Global Functions ────────────────────

function closePanel(name) {
    document.getElementById(`panel-${name}`)?.classList.add('hidden');
    App.currentPanel = null;

    // Reset nav active to map
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector('.nav-item[data-panel="map"]')?.classList.add('active');
}

// ──────────────────── Initialize on DOM Ready ────────────────────
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
