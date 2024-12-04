-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (managed by Supabase Auth)
CREATE TABLE IF NOT EXISTS auth.users (
    id UUID REFERENCES auth.users NOT NULL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Video Groups table
CREATE TABLE IF NOT EXISTS video_groups (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_red BOOLEAN DEFAULT FALSE,
    is_temporary BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES auth.users(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    gemini_file_id TEXT NOT NULL,
    group_id UUID REFERENCES video_groups(id) NOT NULL,
    thumbnail_path TEXT,
    source_url TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    is_red BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES auth.users(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Prompts table
CREATE TABLE IF NOT EXISTS prompts (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    text TEXT NOT NULL,
    description VARCHAR(255) NOT NULL,
    created_by UUID REFERENCES auth.users(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Analysis Batches table
CREATE TABLE IF NOT EXISTS analysis_batches (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_videos INTEGER NOT NULL,
    group_id UUID REFERENCES video_groups(id) NOT NULL,
    prompt_id UUID REFERENCES prompts(id) NOT NULL,
    created_by UUID REFERENCES auth.users(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT valid_progress CHECK (progress >= 0 AND progress <= 100)
);

-- Analysis Tasks table
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    batch_id UUID REFERENCES analysis_batches(id) NOT NULL,
    video_id UUID REFERENCES videos(id) NOT NULL,
    prompt_id UUID REFERENCES prompts(id) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    result JSONB,
    error TEXT,
    is_red BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES auth.users(id) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_videos_group_id ON videos(group_id);
CREATE INDEX IF NOT EXISTS idx_videos_created_by ON videos(created_by);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_batch_id ON analysis_tasks(batch_id);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_video_id ON analysis_tasks(video_id);
CREATE INDEX IF NOT EXISTS idx_analysis_tasks_prompt_id ON analysis_tasks(prompt_id);
CREATE INDEX IF NOT EXISTS idx_analysis_batches_group_id ON analysis_batches(group_id);
CREATE INDEX IF NOT EXISTS idx_analysis_batches_created_by ON analysis_batches(created_by);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_video_groups_updated_at
    BEFORE UPDATE ON video_groups
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_prompts_updated_at
    BEFORE UPDATE ON prompts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_batches_updated_at
    BEFORE UPDATE ON analysis_batches
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_tasks_updated_at
    BEFORE UPDATE ON analysis_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) Policies
ALTER TABLE video_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_tasks ENABLE ROW LEVEL SECURITY;

-- Video Groups RLS
CREATE POLICY video_groups_select ON video_groups
    FOR SELECT TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY video_groups_insert ON video_groups
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY video_groups_update ON video_groups
    FOR UPDATE TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

CREATE POLICY video_groups_delete ON video_groups
    FOR DELETE TO authenticated
    USING (created_by = auth.uid());

-- Videos RLS
CREATE POLICY videos_select ON videos
    FOR SELECT TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY videos_insert ON videos
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY videos_update ON videos
    FOR UPDATE TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

CREATE POLICY videos_delete ON videos
    FOR DELETE TO authenticated
    USING (created_by = auth.uid());

-- Prompts RLS
CREATE POLICY prompts_select ON prompts
    FOR SELECT TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY prompts_insert ON prompts
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY prompts_update ON prompts
    FOR UPDATE TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

CREATE POLICY prompts_delete ON prompts
    FOR DELETE TO authenticated
    USING (created_by = auth.uid());

-- Analysis Batches RLS
CREATE POLICY analysis_batches_select ON analysis_batches
    FOR SELECT TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY analysis_batches_insert ON analysis_batches
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY analysis_batches_update ON analysis_batches
    FOR UPDATE TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

CREATE POLICY analysis_batches_delete ON analysis_batches
    FOR DELETE TO authenticated
    USING (created_by = auth.uid());

-- Analysis Tasks RLS
CREATE POLICY analysis_tasks_select ON analysis_tasks
    FOR SELECT TO authenticated
    USING (created_by = auth.uid());

CREATE POLICY analysis_tasks_insert ON analysis_tasks
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY analysis_tasks_update ON analysis_tasks
    FOR UPDATE TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

CREATE POLICY analysis_tasks_delete ON analysis_tasks
    FOR DELETE TO authenticated
    USING (created_by = auth.uid()); 