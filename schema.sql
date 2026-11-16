CREATE TABLE IF NOT EXISTS eha_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK(status IN ('running','ok','error')),
    error TEXT,
    bucket_count INTEGER
);
CREATE TABLE IF NOT EXISTS eha_revisions (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES eha_runs(id),
    day DATE NOT NULL,
    hour SMALLINT NOT NULL CHECK(hour BETWEEN 0 AND 23),
    soc_name TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS eha_revisions_day ON eha_revisions(day, hour);
CREATE TABLE IF NOT EXISTS eha_latest (
    day DATE NOT NULL,
    hour SMALLINT NOT NULL CHECK(hour BETWEEN 0 AND 23),
    soc_name TEXT NOT NULL,
    revision_id BIGINT NOT NULL REFERENCES eha_revisions(id),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(day, hour, soc_name)
);
CREATE TABLE IF NOT EXISTS eha_facts (
    revision_id BIGINT NOT NULL REFERENCES eha_revisions(id),
    soc_name TEXT NOT NULL,
    operator TEXT NOT NULL,
    exception_reason TEXT NOT NULL,
    fluxo TEXT NOT NULL,
    sub_area TEXT NOT NULL,
    before_station_type TEXT NOT NULL,
    bips BIGINT NOT NULL CHECK(bips>=0),
    shipments BIGINT NOT NULL CHECK(shipments>=0),
    PRIMARY KEY(revision_id,soc_name,operator,exception_reason,fluxo,sub_area,before_station_type)
);
CREATE TABLE IF NOT EXISTS eha_preferences (
    email TEXT PRIMARY KEY,
    station TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS eha_unit_settings (
    soc_name TEXT PRIMARY KEY,
    shift_starts JSONB NOT NULL CHECK(jsonb_typeof(shift_starts)='array' AND jsonb_array_length(shift_starts)=3),
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS eha_unit_settings_audit (
    id BIGSERIAL PRIMARY KEY,
    soc_name TEXT NOT NULL,
    shift_starts JSONB NOT NULL,
    version INTEGER NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
