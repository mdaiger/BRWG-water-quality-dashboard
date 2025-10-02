-- Enable RLS on sites and restrict writes to approved admins

-- 1) Ensure sites table exists (skip if already created)
-- CREATE TABLE IF NOT EXISTS sites (
--   id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   site_number int,
--   full_name text,
--   short_name text,
--   latitude double precision,
--   longitude double precision,
--   elevation int,
--   description text,
--   updated_at timestamptz DEFAULT now()
-- );

-- 2) Turn on RLS
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;

-- 3) Helper: create a view or use an EXISTS policy to check pending_admins
-- Read access: allow everyone if you want public reads via anon key; otherwise restrict
DROP POLICY IF EXISTS sites_read_all ON sites;
CREATE POLICY sites_read_all ON sites
FOR SELECT
USING (true);

-- Write access: only authenticated users whose email is approved in pending_admins
DROP POLICY IF EXISTS sites_admin_writes ON sites;
CREATE POLICY sites_admin_writes ON sites
FOR ALL
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM pending_admins pa
    WHERE pa.email = auth.jwt() ->> 'email'
      AND pa.status = 'approved'
  )
)
WITH CHECK (
  EXISTS (
    SELECT 1 FROM pending_admins pa
    WHERE pa.email = auth.jwt() ->> 'email'
      AND pa.status = 'approved'
  )
);


