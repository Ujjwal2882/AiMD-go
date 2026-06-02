/**
 * AiMD-go Layer Manager
 * Manages layer listing, display, toggle, and deletion.
 */

const LayerManager = {
    layers: [],

    /**
     * Initialize the layer manager
     */
    init() {
        this.refreshLayersList();
    },

    /**
     * Fetch all layers from API and update the UI
     */
    async refreshLayersList() {
        try {
            const data = await API.get('/api/layers');
            this.layers = data.layers || [];

            this._renderLayersList();
            this._updateBadge();
            this._updateExportDropdown();
        } catch (error) {
            console.error('[Layers] Failed to load:', error);
        }
    },

    /**
     * Load a layer's GeoJSON and display it on the map
     */
    async loadAndDisplayLayer(layerId) {
        try {
            // Get metadata
            const meta = await API.get(`/api/layers/${layerId}`);
            
            // Get GeoJSON
            const geojson = await API.get(`/api/layers/${layerId}/geojson`);

            // Add to map
            MapController.addGeoJSONLayer(layerId, geojson, meta.style, meta.name);

            return meta;
        } catch (error) {
            console.error(`[Layers] Failed to load layer ${layerId}:`, error);
            App.showToast(`Failed to load layer: ${error.message}`, 'error');
        }
    },

    /**
     * Render the layers list in the panel
     */
    _renderLayersList() {
        const container = document.getElementById('layers-list');
        if (!container) return;

        if (this.layers.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-layer-group"></i>
                    <p>No layers yet</p>
                    <span>Upload data to add layers to the map</span>
                </div>
            `;
            return;
        }

        container.innerHTML = this.layers.map(layer => `
            <div class="layer-card" data-layer-id="${layer.id}">
                <div class="layer-card-header">
                    <div class="layer-color-dot" style="color: ${layer.style?.color || '#6366f1'}; background: ${layer.style?.color || '#6366f1'};"></div>
                    <span title="${layer.name}">${layer.name}</span>
                </div>
                <div class="layer-card-meta">
                    <span><i class="fas fa-map-marker-alt"></i> ${layer.feature_count} features</span>
                    <span><i class="fas fa-tag"></i> ${layer.source_type}</span>
                </div>
                <div class="layer-card-actions">
                    <button class="layer-action-btn" onclick="LayerManager.toggleVisibility('${layer.id}', this)" title="Toggle">
                        <i class="fas fa-${layer.visible !== false ? 'eye' : 'eye-slash'}"></i>
                    </button>
                    <button class="layer-action-btn" onclick="LayerManager.zoomTo('${layer.id}')" title="Zoom to">
                        <i class="fas fa-search-plus"></i>
                    </button>
                    <button class="layer-action-btn" onclick="LayerManager.loadAndDisplayLayer('${layer.id}')" title="Reload">
                        <i class="fas fa-sync-alt"></i>
                    </button>
                    <button class="layer-action-btn danger" onclick="LayerManager.deleteLayer('${layer.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    },

    /**
     * Toggle layer visibility
     */
    async toggleVisibility(layerId, btnElement) {
        const layer = this.layers.find(l => l.id === layerId);
        if (!layer) return;

        const newVisible = !layer.visible;
        layer.visible = newVisible;

        // Update map
        MapController.toggleLayer(layerId, newVisible);

        // Update icon
        if (btnElement) {
            const icon = btnElement.querySelector('i');
            icon.className = `fas fa-${newVisible ? 'eye' : 'eye-slash'}`;
        }

        // Persist
        try {
            await API.put(`/api/layers/${layerId}/visibility?visible=${newVisible}`);
        } catch (e) {
            // Ignore - UI is already updated
        }
    },

    /**
     * Zoom to layer bounds
     */
    zoomTo(layerId) {
        MapController.zoomToLayer(layerId);
    },

    /**
     * Delete a layer
     */
    async deleteLayer(layerId) {
        if (!confirm('Delete this layer?')) return;

        try {
            await API.delete(`/api/layers/${layerId}`);
            MapController.removeLayer(layerId);
            this.layers = this.layers.filter(l => l.id !== layerId);
            this._renderLayersList();
            this._updateBadge();
            this._updateExportDropdown();
            App.showToast('Layer deleted', 'success');
        } catch (error) {
            App.showToast(`Failed to delete: ${error.message}`, 'error');
        }
    },

    /**
     * Update the layers count badge
     */
    _updateBadge() {
        const badge = document.getElementById('layers-badge');
        if (badge) {
            badge.textContent = this.layers.length;
        }
    },

    /**
     * Update the export layer dropdown
     */
    _updateExportDropdown() {
        const select = document.getElementById('export-layer');
        if (!select) return;

        select.innerHTML = '<option value="">— Select a layer —</option>';
        this.layers.forEach(layer => {
            select.innerHTML += `<option value="${layer.id}">${layer.name} (${layer.feature_count} features)</option>`;
        });
    },
};
