CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS crawl_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'xhs',
    status TEXT NOT NULL DEFAULT 'pending',
    keywords_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_pages INTEGER NOT NULL DEFAULT 1,
    date_from TIMESTAMPTZ,
    date_to TIMESTAMPTZ,
    sort_type TEXT NOT NULL DEFAULT 'latest',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE crawl_jobs ADD COLUMN IF NOT EXISTS date_from TIMESTAMPTZ;
ALTER TABLE crawl_jobs ADD COLUMN IF NOT EXISTS date_to TIMESTAMPTZ;
ALTER TABLE crawl_jobs ADD COLUMN IF NOT EXISTS sort_type TEXT NOT NULL DEFAULT 'latest';

CREATE TABLE IF NOT EXISTS crawl_job_pages (
    id BIGSERIAL PRIMARY KEY,
    crawl_job_id BIGINT NOT NULL REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    page_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    search_id TEXT,
    raw_response_artifact_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (crawl_job_id, keyword, page_no)
);

CREATE TABLE IF NOT EXISTS crawl_keyword_checkpoints (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'xhs',
    keyword TEXT NOT NULL,
    window_key TEXT NOT NULL,
    date_from TIMESTAMPTZ,
    date_to TIMESTAMPTZ,
    sort_type TEXT NOT NULL DEFAULT 'latest',
    newest_published_at TIMESTAMPTZ,
    oldest_published_at TIMESTAMPTZ,
    last_crawl_job_id BIGINT REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    last_completed_page INTEGER NOT NULL DEFAULT 0,
    total_pages_crawled INTEGER NOT NULL DEFAULT 0,
    total_posts_seen INTEGER NOT NULL DEFAULT 0,
    total_new_posts INTEGER NOT NULL DEFAULT 0,
    consecutive_stale_pages INTEGER NOT NULL DEFAULT 0,
    stop_reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, keyword, window_key, sort_type)
);

CREATE TABLE IF NOT EXISTS crawl_events (
    id BIGSERIAL PRIMARY KEY,
    crawl_job_id BIGINT REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    status TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw_posts (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL DEFAULT 'xhs',
    source_note_id TEXT NOT NULL,
    note_url TEXT,
    xsec_token TEXT,
    xsec_source TEXT,
    note_type TEXT,
    title TEXT,
    content TEXT,
    author_id TEXT,
    author_nickname TEXT,
    author_avatar TEXT,
    ip_location TEXT,
    like_count BIGINT,
    collect_count BIGINT,
    comment_count BIGINT,
    share_count BIGINT,
    published_at TIMESTAMPTZ,
    raw_note_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_note_artifact_path TEXT,
    merged_text TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, source_note_id)
);

CREATE TABLE IF NOT EXISTS post_keyword_hits (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    crawl_job_id BIGINT REFERENCES crawl_jobs(id) ON DELETE SET NULL,
    hit_page_no INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_post_id, keyword, crawl_job_id, hit_page_no)
);

CREATE TABLE IF NOT EXISTS post_images (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    image_index INTEGER NOT NULL,
    image_url TEXT NOT NULL,
    local_path TEXT,
    sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_post_id, image_index)
);

CREATE TABLE IF NOT EXISTS post_classifications (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    primary_label TEXT NOT NULL,
    keep_for_extraction BOOLEAN NOT NULL,
    confidence DOUBLE PRECISION,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    review_needed BOOLEAN NOT NULL DEFAULT FALSE,
    company_name TEXT,
    role_name TEXT,
    model_output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS post_ocr_results (
    id BIGSERIAL PRIMARY KEY,
    post_image_id BIGINT NOT NULL REFERENCES post_images(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    ocr_text TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION,
    model_output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS post_extractions (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    company_name TEXT,
    role_name TEXT,
    interview_stage TEXT,
    is_real_experience_confidence DOUBLE PRECISION,
    model_output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS extracted_questions (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    post_extraction_id BIGINT REFERENCES post_extractions(id) ON DELETE SET NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    question_type TEXT NOT NULL,
    evidence_span TEXT,
    status TEXT NOT NULL DEFAULT 'pending_merge',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS canonical_questions (
    id BIGSERIAL PRIMARY KEY,
    canonical_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    question_type TEXT NOT NULL,
    embedding vector(1024),
    post_count INTEGER NOT NULL DEFAULT 0,
    first_seen_post_id BIGINT REFERENCES raw_posts(id) ON DELETE SET NULL,
    last_seen_post_id BIGINT REFERENCES raw_posts(id) ON DELETE SET NULL,
    review_status TEXT NOT NULL DEFAULT 'approved',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS question_aliases (
    id BIGSERIAL PRIMARY KEY,
    canonical_question_id BIGINT NOT NULL REFERENCES canonical_questions(id) ON DELETE CASCADE,
    extracted_question_id BIGINT NOT NULL REFERENCES extracted_questions(id) ON DELETE CASCADE,
    alias_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    merge_method TEXT NOT NULL,
    merge_score DOUBLE PRECISION,
    review_needed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (canonical_question_id, extracted_question_id)
);

CREATE TABLE IF NOT EXISTS post_question_links (
    id BIGSERIAL PRIMARY KEY,
    raw_post_id BIGINT NOT NULL REFERENCES raw_posts(id) ON DELETE CASCADE,
    canonical_question_id BIGINT NOT NULL REFERENCES canonical_questions(id) ON DELETE CASCADE,
    extracted_question_id BIGINT REFERENCES extracted_questions(id) ON DELETE SET NULL,
    company_name TEXT,
    role_name TEXT,
    interview_stage TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (raw_post_id, canonical_question_id, extracted_question_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_posts_review_status ON raw_posts(review_status);
CREATE INDEX IF NOT EXISTS idx_post_images_status ON post_images(status);
CREATE INDEX IF NOT EXISTS idx_extracted_questions_status ON extracted_questions(status);
CREATE INDEX IF NOT EXISTS idx_canonical_questions_type ON canonical_questions(question_type);
CREATE INDEX IF NOT EXISTS idx_crawl_keyword_checkpoints_lookup ON crawl_keyword_checkpoints(platform, keyword, window_key, sort_type);

CREATE OR REPLACE VIEW canonical_question_stats AS
SELECT
    cq.id,
    cq.canonical_text,
    cq.question_type,
    COUNT(DISTINCT pql.raw_post_id) AS unique_post_count,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(pql.company_name, '')), NULL) AS companies,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(pql.role_name, '')), NULL) AS roles
FROM canonical_questions cq
LEFT JOIN post_question_links pql ON pql.canonical_question_id = cq.id
GROUP BY cq.id, cq.canonical_text, cq.question_type;
