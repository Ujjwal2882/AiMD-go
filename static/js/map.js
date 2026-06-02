/**
 * AiMD-go Map Controller
 * CesiumJS globe initialization, layer rendering, and interaction.
 */

const MapController = {
    viewer: null,
    baseLayers: {},
    currentBaseLayer: null,
    overlayLayers: {},   // layer_id -> Cesium.GeoJsonDataSource
    _searchClickMode: false,
    _searchRadiusEntity: null,
    _searchMarkerEntity: null,
    _popupElement: null,
    _popupRenderHandler: null,
    _selectedEntity: null,

    /**
     * Initialize the Cesium Viewer
     */
    init() {
        // Create custom popup element
        this._popupElement = document.createElement('div');
        this._popupElement.className = 'cesium-custom-popup';
        this._popupElement.style.opacity = '0';
        this._popupElement.style.pointerEvents = 'none';
        document.getElementById('map').appendChild(this._popupElement);

        // Define base imagery providers (no API key required)
        this.baseLayers = {
            streets: new Cesium.UrlTemplateImageryProvider({
                url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                credit: 'OpenStreetMap'
            }),
            satellite: new Cesium.UrlTemplateImageryProvider({
                url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                credit: 'Esri, USGS, NOAA'
            }),
            dark: new Cesium.UrlTemplateImageryProvider({
                url: 'https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
                credit: 'CartoDB'
            }),
            terrain: new Cesium.UrlTemplateImageryProvider({
                url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
                credit: 'OpenTopoMap'
            })
        };

        // Create Cesium Viewer
        this.viewer = new Cesium.Viewer('map', {
            imageryProvider: this.baseLayers.dark,
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            infoBox: false,
            sceneModePicker: false,
            selectionIndicator: false,
            timeline: false,
            navigationHelpButton: false,
            navigationInstructionsInitiallyVisible: false,
            animation: false,
            fullscreenButton: false,
            scene3DOnly: true
        });

        // Tweak UI rendering
        this.viewer.scene.globe.enableLighting = false; // keep it bright
        this.currentBaseLayer = 'dark';

        // Setup events
        this._setupEvents();
        this._setupControls();

        // Initial view
        this.viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(0, 20, 20000000), // lat 20, lon 0, alt 20M meters
            duration: 0
        });

        console.log('[Map] Cesium Globe Initialized');
    },

    /**
     * Setup map event listeners
     */
    _setupEvents() {
        // Track mouse position for coordinates
        const handler = new Cesium.ScreenSpaceEventHandler(this.viewer.scene.canvas);

        handler.setInputAction((movement) => {
            const cartesian = this.viewer.camera.pickEllipsoid(movement.endPosition, this.viewer.scene.globe.ellipsoid);
            if (cartesian) {
                const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                const lon = Cesium.Math.toDegrees(cartographic.longitude);
                const lat = Cesium.Math.toDegrees(cartographic.latitude);
                
                document.getElementById('coords-lat').textContent = `Lat: ${lat.toFixed(4)}`;
                document.getElementById('coords-lon').textContent = `Lon: ${lon.toFixed(4)}`;
            }
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

        // Track zoom (height)
        this.viewer.camera.moveEnd.addEventListener(() => {
            const height = this.viewer.camera.positionCartographic.height;
            // approximate zoom level based on altitude
            const zoom = Math.max(0, Math.round(27 - Math.log2(height)));
            document.getElementById('coords-zoom').textContent = `Zoom: ${zoom}`;
        });

        // Click handler for search and popups
        handler.setInputAction((click) => {
            if (this._searchClickMode) {
                const cartesian = this.viewer.camera.pickEllipsoid(click.position, this.viewer.scene.globe.ellipsoid);
                if (cartesian) {
                    const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
                    const lon = Cesium.Math.toDegrees(cartographic.longitude);
                    const lat = Cesium.Math.toDegrees(cartographic.latitude);

                    this._searchClickMode = false;
                    this.viewer.scene.canvas.style.cursor = '';
                    document.getElementById('search-lat').value = lat.toFixed(6);
                    document.getElementById('search-lon').value = lon.toFixed(6);
                    App.showToast('Location selected! Click "Search Nearby" to find features.', 'info');
                }
            } else {
                // Feature selection (Popup)
                const pickedObject = this.viewer.scene.pick(click.position);
                if (Cesium.defined(pickedObject) && pickedObject.id) {
                    this._selectedEntity = pickedObject.id;
                    const properties = pickedObject.id.properties;
                    if (properties) {
                        const name = properties.getValue ? properties.getValue(this.viewer.clock.currentTime) : properties;
                        this._showPopup(name, pickedObject.id);
                    }
                } else {
                    this._hidePopup();
                }
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // Update popup position every frame if visible
        this._popupRenderHandler = this.viewer.scene.postRender.addEventListener(() => {
            if (this._selectedEntity && this._popupElement.style.opacity === '1') {
                const position = this._selectedEntity.position ? this._selectedEntity.position.getValue(this.viewer.clock.currentTime) : null;
                // If it's a polygon/line, it might not have a position. We can approximate or just use a stored click pos,
                // but for simplicity, we will calculate center if possible.
                let cartesian = position;
                
                if (!cartesian) {
                    // Try to get center of bounding sphere if no position (e.g. polygons)
                    if (this._selectedEntity.polygon || this._selectedEntity.polyline) {
                         cartesian = this._computeEntityCenter(this._selectedEntity);
                    }
                }

                if (cartesian) {
                    const canvasPosition = Cesium.SceneTransforms.wgs84ToWindowCoordinates(this.viewer.scene, cartesian);
                    if (Cesium.defined(canvasPosition)) {
                        this._popupElement.style.left = `${canvasPosition.x}px`;
                        this._popupElement.style.top = `${canvasPosition.y}px`;
                        this._popupElement.style.display = 'block';
                    } else {
                        this._popupElement.style.display = 'none'; // Behind globe
                    }
                }
            }
        });
    },

    _computeEntityCenter(entity) {
        if (entity.polygon && entity.polygon.hierarchy) {
            const positions = entity.polygon.hierarchy.getValue(this.viewer.clock.currentTime).positions;
            return Cesium.BoundingSphere.fromPoints(positions).center;
        } else if (entity.polyline && entity.polyline.positions) {
            const positions = entity.polyline.positions.getValue(this.viewer.clock.currentTime);
            return Cesium.BoundingSphere.fromPoints(positions).center;
        }
        return null;
    },

    /**
     * Show custom popup
     */
    _showPopup(propertiesObj, entity) {
        // extract raw properties
        const props = {};
        for (let key in propertiesObj) {
            if (propertiesObj.hasOwnProperty(key) && key !== '_propertyNames') {
                const val = propertiesObj[key];
                props[key] = (val && typeof val.getValue === 'function') ? val.getValue(this.viewer.clock.currentTime) : val;
            }
        }
        
        let html = `<h4>Feature Properties</h4>`;
        const entries = Object.entries(props);
        
        if (entries.length === 0) {
            html += '<p style="color: var(--text-muted);">No properties</p>';
        } else {
            for (const [key, value] of entries) {
                if (value === null || value === undefined || typeof value === 'object') continue;
                html += `<div class="popup-property">
                    <span class="popup-key">${key}</span>
                    <span class="popup-value">${value}</span>
                </div>`;
            }
        }

        this._popupElement.innerHTML = html;
        this._popupElement.style.opacity = '1';
        this._popupElement.style.pointerEvents = 'auto';
    },

    _hidePopup() {
        this._popupElement.style.opacity = '0';
        this._popupElement.style.pointerEvents = 'none';
        this._selectedEntity = null;
    },

    /**
     * Setup custom map controls
     */
    _setupControls() {
        // Zoom buttons
        document.getElementById('btn-zoom-in')?.addEventListener('click', () => {
            const camera = this.viewer.camera;
            camera.zoomIn(camera.positionCartographic.height * 0.5);
        });
        document.getElementById('btn-zoom-out')?.addEventListener('click', () => {
            const camera = this.viewer.camera;
            camera.zoomOut(camera.positionCartographic.height * 0.5);
        });

        // Locate button
        document.getElementById('btn-locate')?.addEventListener('click', () => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition((pos) => {
                    this.viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(pos.coords.longitude, pos.coords.latitude, 5000)
                    });
                });
            }
        });

        // Fullscreen button
        document.getElementById('btn-fullscreen')?.addEventListener('click', () => {
            const el = document.documentElement;
            if (!document.fullscreenElement) {
                el.requestFullscreen?.();
            } else {
                document.exitFullscreen?.();
            }
        });

        // Basemap selector
        document.querySelectorAll('.basemap-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const basemap = btn.dataset.basemap;
                this.setBaseLayer(basemap);

                // Update active state
                document.querySelectorAll('.basemap-option').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    },

    /**
     * Switch base layer
     */
    setBaseLayer(name) {
        if (this.currentBaseLayer === name) return;
        if (!this.baseLayers[name]) return;

        const imageryLayers = this.viewer.imageryLayers;
        imageryLayers.removeAll();
        imageryLayers.addImageryProvider(this.baseLayers[name]);
        
        this.currentBaseLayer = name;
    },

    /**
     * Add a GeoJSON layer to the map
     */
    async addGeoJSONLayer(layerId, geojson, style = {}, name = '') {
        // Remove if exists
        this.removeLayer(layerId);

        const defaultStyle = {
            color: Cesium.Color.fromCssColorString(style.color || '#6366f1'),
            fillColor: Cesium.Color.fromCssColorString(style.fillColor || style.color || '#6366f1').withAlpha(style.fillOpacity || 0.6),
            strokeWidth: style.weight || 2,
            pointSize: (style.radius || 6) * 2,
        };

        try {
            const dataSource = await Cesium.GeoJsonDataSource.load(geojson, {
                stroke: defaultStyle.color,
                fill: defaultStyle.fillColor,
                strokeWidth: defaultStyle.strokeWidth,
                markerSize: defaultStyle.pointSize,
                markerColor: defaultStyle.fillColor,
                clampToGround: true // Drape over terrain/globe
            });

            // Customize styling for entities
            const entities = dataSource.entities.values;
            for (let i = 0; i < entities.length; i++) {
                const entity = entities[i];
                if (entity.billboard) {
                    // Replace default billboard with a point
                    entity.billboard = undefined;
                    entity.point = new Cesium.PointGraphics({
                        color: defaultStyle.fillColor,
                        pixelSize: defaultStyle.pointSize,
                        outlineColor: defaultStyle.color,
                        outlineWidth: 1,
                        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
                    });
                }
                if (entity.polygon) {
                    entity.polygon.material = new Cesium.ColorMaterialProperty(defaultStyle.fillColor);
                    entity.polygon.outline = new Cesium.ConstantProperty(true);
                    entity.polygon.outlineColor = new Cesium.ConstantProperty(defaultStyle.color);
                    entity.polygon.outlineWidth = new Cesium.ConstantProperty(defaultStyle.strokeWidth);
                }
                if (entity.polyline) {
                    entity.polyline.material = new Cesium.ColorMaterialProperty(defaultStyle.color);
                    entity.polyline.width = new Cesium.ConstantProperty(defaultStyle.strokeWidth);
                }
            }

            await this.viewer.dataSources.add(dataSource);
            this.overlayLayers[layerId] = dataSource;

            return dataSource;
        } catch (e) {
            console.error('Error loading GeoJSON into Cesium:', e);
            throw e;
        }
    },

    /**
     * Remove a layer from the map
     */
    removeLayer(layerId) {
        if (this.overlayLayers[layerId]) {
            this.viewer.dataSources.remove(this.overlayLayers[layerId]);
            delete this.overlayLayers[layerId];
        }
        if (this._selectedEntity) {
            this._hidePopup();
        }
    },

    /**
     * Toggle layer visibility
     */
    toggleLayer(layerId, visible) {
        const dataSource = this.overlayLayers[layerId];
        if (dataSource) {
            dataSource.show = visible;
        }
        if (!visible) {
            this._hidePopup();
        }
    },

    /**
     * Zoom to fit a layer's bounds
     */
    zoomToLayer(layerId) {
        const dataSource = this.overlayLayers[layerId];
        if (dataSource) {
            this.viewer.flyTo(dataSource);
        }
    },

    /**
     * Zoom to specific bounds
     */
    zoomToBounds(bounds) {
        if (bounds && bounds.north && bounds.south) {
            this.viewer.camera.flyTo({
                destination: Cesium.Rectangle.fromDegrees(
                    bounds.west, bounds.south, bounds.east, bounds.north
                )
            });
        }
    },

    /**
     * Add a search radius circle
     */
    addSearchRadius(lat, lon, radiusMeters) {
        // Remove previous
        if (this._searchRadiusEntity) {
            this.viewer.entities.remove(this._searchRadiusEntity);
        }
        if (this._searchMarkerEntity) {
            this.viewer.entities.remove(this._searchMarkerEntity);
        }

        const center = Cesium.Cartesian3.fromDegrees(lon, lat);

        this._searchRadiusEntity = this.viewer.entities.add({
            position: center,
            ellipse: {
                semiMinorAxis: radiusMeters,
                semiMajorAxis: radiusMeters,
                material: Cesium.Color.fromCssColorString('#06b6d4').withAlpha(0.1),
                outline: true,
                outlineColor: Cesium.Color.fromCssColorString('#06b6d4'),
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
            }
        });

        this._searchMarkerEntity = this.viewer.entities.add({
            position: center,
            point: {
                pixelSize: 10,
                color: Cesium.Color.fromCssColorString('#06b6d4'),
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
            }
        });

        // Zoom to it
        this.viewer.flyTo(this._searchRadiusEntity);
    },

    /**
     * Enable click-to-search mode
     */
    enableSearchClickMode() {
        this._searchClickMode = true;
        this.viewer.scene.canvas.style.cursor = 'crosshair';
        App.showToast('Click on the globe to select a location', 'info');
    },

    /**
     * Clear all layers
     */
    clearAllLayers() {
        for (const layerId in this.overlayLayers) {
            this.viewer.dataSources.remove(this.overlayLayers[layerId]);
        }
        this.overlayLayers = {};
        
        if (this._searchRadiusEntity) {
            this.viewer.entities.remove(this._searchRadiusEntity);
            this._searchRadiusEntity = null;
        }
        if (this._searchMarkerEntity) {
            this.viewer.entities.remove(this._searchMarkerEntity);
            this._searchMarkerEntity = null;
        }
        this._hidePopup();
    },
};
