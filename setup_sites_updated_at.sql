-- Ensure sites table has an automatic updated_at timestamp

-- 1) Add updated_at column with default now() if it doesn't exist
ALTER TABLE sites
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- 2) Create or replace a trigger function to bump updated_at on UPDATE
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3) Attach trigger to sites table
DROP TRIGGER IF EXISTS sites_set_updated_at ON sites;
CREATE TRIGGER sites_set_updated_at
BEFORE UPDATE ON sites
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


