CREATE TABLE IF NOT EXISTS photo_analysis_jobs (
    job_id uuid PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    user_id text NOT NULL,
    image_key text NOT NULL UNIQUE,
    meal_type text NOT NULL,
    target_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED')),
    attempt_count integer NOT NULL DEFAULT 0,
    result jsonb,
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS photo_analysis_jobs_user_created_idx
    ON photo_analysis_jobs (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS outbox_events (
    id bigserial PRIMARY KEY,
    event_id uuid NOT NULL UNIQUE,
    causation_event_id uuid,
    topic text NOT NULL,
    event_key text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    publish_attempts integer NOT NULL DEFAULT 0,
    last_error text
);

ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS causation_event_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS outbox_events_topic_causation_uidx
    ON outbox_events (topic, causation_event_id)
    WHERE causation_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS outbox_events_unpublished_idx
    ON outbox_events (id) WHERE published_at IS NULL;

-- Supports the retention sweep, which scans published rows by age.
CREATE INDEX IF NOT EXISTS outbox_events_published_at_idx
    ON outbox_events (published_at) WHERE published_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS processed_events (
    event_id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    status text NOT NULL CHECK (status IN ('DONE', 'FAILED')),
    processed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS diet_uploads (
    upload_id uuid PRIMARY KEY,
    user_id text NOT NULL,
    source_ref text NOT NULL,
    image_key text NOT NULL,
    mode text,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (user_id, source_ref)
);

CREATE INDEX IF NOT EXISTS diet_uploads_user_created_idx
    ON diet_uploads (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS diet_analysis_jobs (
    analysis_id uuid PRIMARY KEY,
    request_event_id uuid NOT NULL UNIQUE,
    upload_id uuid NOT NULL UNIQUE REFERENCES diet_uploads(upload_id),
    user_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('PENDING', 'PROCESSING', 'DONE', 'FAILED')),
    attempt_count integer NOT NULL DEFAULT 0,
    result jsonb,
    failure_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS diet_analysis_jobs_user_created_idx
    ON diet_analysis_jobs (user_id, created_at DESC);
