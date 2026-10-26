-- EvalBot platform schema (PostgreSQL / Supabase). Idempotent: safe to run on every start.

create extension if not exists pgcrypto;

create table if not exists companies (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    website     text,
    about       text,
    created_by  uuid not null,
    created_at  timestamptz not null default now()
);

create table if not exists profiles (
    id          uuid primary key,                 -- = auth.users.id
    email       text,
    full_name   text,
    role        text not null default 'candidate' check (role in ('candidate', 'recruiter')),
    company_id  uuid references companies(id) on delete set null,
    headline    text,
    target_track text,
    locale      text not null default 'en',
    created_at  timestamptz not null default now()
);

create table if not exists jobs (
    id            uuid primary key default gen_random_uuid(),
    company_id    uuid not null references companies(id) on delete cascade,
    created_by    uuid not null,
    title         text not null,
    track         text not null,
    level         text not null,
    description   text,
    questions     jsonb not null default '[]'::jsonb,   -- [{"text": "...", "kind": "technical|behavioral|custom"}]
    answer_seconds int not null default 120,
    status        text not null default 'open' check (status in ('draft', 'open', 'closed')),
    share_token   text not null unique default encode(gen_random_bytes(9), 'hex'),
    created_at    timestamptz not null default now()
);
create index if not exists jobs_company_idx on jobs(company_id);

create table if not exists sessions (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null,
    job_id        uuid references jobs(id) on delete set null,
    mode          text not null check (mode in ('mock', 'job', 'upload')),
    track         text,
    level         text,
    interview_type text,
    language      text not null default 'en',
    status        text not null default 'in_progress' check (status in ('in_progress', 'processing', 'completed', 'failed')),
    context       jsonb not null default '{}'::jsonb,   -- cv / job description summary used for questions
    overall_score real,
    report        jsonb,
    pdf_path      text,
    error         text,
    created_at    timestamptz not null default now(),
    completed_at  timestamptz
);
create index if not exists sessions_user_idx on sessions(user_id, created_at desc);
create index if not exists sessions_job_idx on sessions(job_id);

create table if not exists answers (
    id            uuid primary key default gen_random_uuid(),
    session_id    uuid not null references sessions(id) on delete cascade,
    idx           int not null,
    question      text not null,
    kind          text,
    is_followup   boolean not null default false,
    audio_path    text,
    duration_s    real,
    transcript    text,
    voice         jsonb,
    presence      jsonb,          -- camera metrics computed in the browser (optional)
    feedback      jsonb,
    score         int,
    created_at    timestamptz not null default now(),
    unique (session_id, idx)
);

create table if not exists reviews (
    session_id    uuid primary key references sessions(id) on delete cascade,
    reviewer_id   uuid not null,
    status        text not null default 'new' check (status in ('new', 'shortlisted', 'rejected', 'hired')),
    rating        int check (rating between 1 and 5),
    notes         text,
    updated_at    timestamptz not null default now()
);

-- v2: job board, richer job posts and company profiles (idempotent migrations)
alter table companies add column if not exists industry text;
alter table companies add column if not exists size text;
alter table companies add column if not exists location text;

alter table jobs add column if not exists location text;
alter table jobs add column if not exists work_mode text not null default 'onsite';         -- onsite | remote | hybrid
alter table jobs add column if not exists employment_type text not null default 'full_time'; -- full_time | part_time | internship | contract
alter table jobs add column if not exists salary text;
alter table jobs add column if not exists skills jsonb not null default '[]'::jsonb;
alter table jobs add column if not exists deadline date;
alter table jobs add column if not exists visibility text not null default 'public';        -- public (job board) | link (only via link)
alter table jobs add column if not exists views int not null default 0;
create index if not exists jobs_board_idx on jobs(status, visibility, created_at desc);

-- Lock tables against Supabase's public Data API: the app server connects as the database owner
-- (which bypasses RLS), while the anon/authenticated API roles get no rows at all (no policies).
alter table companies enable row level security;
alter table profiles  enable row level security;
alter table jobs      enable row level security;
alter table sessions  enable row level security;
alter table answers   enable row level security;
alter table reviews   enable row level security;
