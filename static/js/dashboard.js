/**
 * AiMD-go Dashboard
 * Real-time KPI cards and charts.
 */

const Dashboard = {
    chartInstance: null,

    /**
     * Initialize dashboard
     */
    init() {
        // Dashboard refreshes when panel is opened
    },

    /**
     * Refresh all dashboard data
     */
    async refresh() {
        try {
            const stats = await API.get('/api/stats');
            this._updateKPIs(stats);
            this._updateChart(stats);
        } catch (error) {
            console.error('[Dashboard] Failed to load stats:', error);
        }
    },

    /**
     * Update KPI card values
     */
    _updateKPIs(stats) {
        this._animateNumber('kpi-layers', stats.total_layers || 0);
        this._animateNumber('kpi-features', stats.total_features || 0);
        this._animateNumber('kpi-detections', stats.total_detections || 0);
        this._animateNumber('kpi-projects', stats.total_projects || 0);
    },

    /**
     * Animate a number counting up
     */
    _animateNumber(elementId, target) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const start = parseInt(el.textContent) || 0;
        const duration = 600;
        const startTime = performance.now();

        const animate = (now) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.round(start + (target - start) * eased);

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    },

    /**
     * Update the features-by-source chart
     */
    _updateChart(stats) {
        const canvas = document.getElementById('chart-sources');
        if (!canvas) return;

        const sourceData = stats.features_by_source || {};
        const labels = Object.keys(sourceData);
        const values = Object.values(sourceData);

        const colors = {
            csv: '#6366f1',
            shapefile: '#10b981',
            geojson: '#f59e0b',
            ai_detection: '#ef4444',
            lidar: '#06b6d4',
            upload: '#8b5cf6',
        };

        const backgroundColors = labels.map(l => colors[l] || '#6366f1');

        // Destroy previous chart
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        if (labels.length === 0) {
            canvas.parentElement.innerHTML = `
                <h3>Features by Source</h3>
                <p style="color: var(--text-muted); text-align: center; padding: 32px;">
                    No data yet. Upload some files to see statistics.
                </p>
            `;
            return;
        }

        this.chartInstance = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels.map(l => l.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())),
                datasets: [{
                    data: values,
                    backgroundColor: backgroundColors,
                    borderColor: 'rgba(10, 10, 18, 0.8)',
                    borderWidth: 3,
                    hoverBorderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#9ca3af',
                            font: { family: 'Inter', size: 12 },
                            padding: 16,
                            usePointStyle: true,
                            pointStyleWidth: 12,
                        },
                    },
                },
                animation: {
                    animateRotate: true,
                    duration: 800,
                },
            },
        });
    },
};
