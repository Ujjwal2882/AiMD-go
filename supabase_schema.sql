-- ═══════════════════════════════════════════════════════════════════
-- AiMD-go: Complete Supabase Schema
-- Paste this entire block into Supabase SQL Editor and run it.
-- ═══════════════════════════════════════════════════════════════════

-- 1. Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════
-- USERS TABLE
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email      TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ═══════════════════════════════════════════════════════════════════
-- PROJECTS TABLE
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    owner_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════════════════════════════════════
-- LAYERS TABLE
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS layers (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id     UUID REFERENCES projects(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    file_type      TEXT NOT NULL,               -- 'csv', 'shapefile', 'geojson', 'ai_detection'
    geojson_path   TEXT,                         -- local disk path to processed .geojson
    drive_file_id  TEXT,                         -- Google Drive file ID for raw upload
    geometry       GEOMETRY(Geometry, 4326),     -- PostGIS geometry (bounding box / hull)
    created_at     TIMESTAMPTZ DEFAULT now(),
    version        INT DEFAULT 1
);

-- Spatial index for fast geo-queries
CREATE INDEX IF NOT EXISTS idx_layers_geometry ON layers USING GIST (geometry);

-- Regular indexes
CREATE INDEX IF NOT EXISTS idx_layers_project_id ON layers (project_id);

-- ═══════════════════════════════════════════════════════════════════
-- UPLOADS TABLE (tracks raw file ingestion)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS uploads (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id        UUID REFERENCES projects(id) ON DELETE SET NULL,
    original_filename TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    drive_file_id     TEXT,                              -- Google Drive file ID
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads (status);

-- ═══════════════════════════════════════════════════════════════════
-- DETECTIONS TABLE (AI inference results)
-- ═══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS detections (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    layer_id    UUID REFERENCES layers(id) ON DELETE CASCADE,
    model_used  TEXT NOT NULL,                    -- e.g. 'yolov8l.pt'
    results     JSONB DEFAULT '{}',               -- full detection payload
    created_at  TIMESTAMPTZ DEFAULT now(),
    version     INT DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_detections_layer_id ON detections (layer_id);

-- ═══════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- Users can only see/modify their own projects and related data
-- ═══════════════════════════════════════════════════════════════════

-- Enable RLS on all tables
ALTER TABLE projects   ENABLE ROW LEVEL SECURITY;
ALTER TABLE layers     ENABLE ROW LEVEL SECURITY;
ALTER TABLE uploads    ENABLE ROW LEVEL SECURITY;
ALTER TABLE detections ENABLE ROW LEVEL SECURITY;

-- Projects: owner can CRUD their own projects
CREATE POLICY projects_owner_select ON projects
    FOR SELECT USING (owner_id = auth.uid());
CREATE POLICY projects_owner_insert ON projects
    FOR INSERT WITH CHECK (owner_id = auth.uid());
CREATE POLICY projects_owner_update ON projects
    FOR UPDATE USING (owner_id = auth.uid());
CREATE POLICY projects_owner_delete ON projects
    FOR DELETE USING (owner_id = auth.uid());

-- Layers: user can access layers belonging to their projects
CREATE POLICY layers_owner_select ON layers
    FOR SELECT USING (
        project_id IN (SELECT id FROM projects WHERE owner_id = auth.uid())
    );
CREATE POLICY layers_owner_insert ON layers
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM projects WHERE owner_id = auth.uid())
    );

-- Uploads: user can access uploads belonging to their projects
CREATE POLICY uploads_owner_select ON uploads
    FOR SELECT USING (
        project_id IN (SELECT id FROM projects WHERE owner_id = auth.uid())
    );
CREATE POLICY uploads_owner_insert ON uploads
    FOR INSERT WITH CHECK (
        project_id IN (SELECT id FROM projects WHERE owner_id = auth.uid())
    );

-- Detections: user can access detections for layers in their projects
CREATE POLICY detections_owner_select ON detections
    FOR SELECT USING (
        layer_id IN (
            SELECT l.id FROM layers l
            JOIN projects p ON l.project_id = p.id
            WHERE p.owner_id = auth.uid()
        )
    );

-- ═══════════════════════════════════════════════════════════════════
-- GRANT SERVICE ROLE ACCESS (for backend Celery workers)
-- The backend connects with the service_role key, which bypasses RLS.
-- No extra grants needed — service_role already has full access.
-- ═══════════════════════════════════════════════════════════════════

-- Done! Your schema is ready.
