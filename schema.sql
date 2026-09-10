-- ORCA Supabase schema
-- Run this in the Supabase SQL editor before connecting the app.
-- The app functions normally even if these tables are missing / unreachable.

create table if not exists locations (
  zone_key text primary key,
  name text not null,
  lat double precision not null,
  lon double precision not null,
  description text
);

create table if not exists analysis_snapshots (
  id bigserial primary key,
  zone text not null,
  safety_score numeric,
  fishing_score numeric,
  recommendation_score numeric,
  raw_data jsonb,
  created_at timestamptz default now()
);

create table if not exists chat_history (
  id bigserial primary key,
  query text not null,
  response text,
  intent text,
  language text,
  created_at timestamptz default now()
);

create index if not exists idx_analysis_snapshots_zone on analysis_snapshots(zone);
create index if not exists idx_analysis_snapshots_created_at on analysis_snapshots(created_at desc);
create index if not exists idx_chat_history_created_at on chat_history(created_at desc);
