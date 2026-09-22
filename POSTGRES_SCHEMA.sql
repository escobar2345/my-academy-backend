-- ============================================================
-- BOI RSU POSTGRESQL SCHEMA  (updated 2026-09)
-- ============================================================
-- Plain PostgreSQL DDL — replaces the old Supabase schema.
-- Applied automatically on backend startup by pgdb.py (safe to
-- re-run: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT
-- EXISTS everywhere). You can also apply it by hand:
--   psql "postgresql://postgres:YOUR_PASSWORD@localhost:5432/YOUR_DB" -f backend/POSTGRES_SCHEMA.sql
--
-- Matches every field the code reads/writes today, including the full
-- registration form (course_name, track, goals, location, qualification...)
-- from registration.vue + boirsu.enroll_student().
-- ============================================================
-- NOTE: Row Level Security / policies were a Supabase-only concept.
-- The browser never touches the database directly any more — every
-- read/write goes through the backend portal API (api_server.py on
-- :5055, /api/portal/*) or the auth servers. Harden that layer
-- before going to production.
-- ============================================================

-- Students table
CREATE TABLE IF NOT EXISTS students (
  student_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT,
  email TEXT UNIQUE,
  career_path TEXT,
  experience_level TEXT DEFAULT 'beginner',
  intake_month TEXT,
  class_type TEXT,
  class_group TEXT,
  preferred_time TEXT,
  preferred_daily_times JSONB,
  sponsor_id TEXT,
  password_salt TEXT,
  password_hash TEXT,
  goals JSONB DEFAULT '[]'::jsonb,
  duration_months INTEGER,
  class_minutes INTEGER DEFAULT 60,
  location TEXT,
  country TEXT,
  gender TEXT,
  dob TEXT,
  occupation TEXT,
  qualification TEXT,
  field_study TEXT,
  institution TEXT,
  research TEXT,
  track TEXT,
  course_name TEXT,
  enrolled_date TIMESTAMP DEFAULT NOW(),
  payment_status TEXT DEFAULT 'paid',
  current_month INTEGER DEFAULT 1,
  current_topic_index INTEGER DEFAULT 0,
  classes_attended INTEGER DEFAULT 0,
  classes_missed INTEGER DEFAULT 0,
  total_classes INTEGER DEFAULT 0,
  assignments_submitted INTEGER DEFAULT 0,
  assignments_missed INTEGER DEFAULT 0,
  avg_quiz_score FLOAT DEFAULT 0,
  avg_assignment_score FLOAT DEFAULT 0,
  overall_grade TEXT DEFAULT 'N/A',
  last_interaction TIMESTAMP,
  mood TEXT DEFAULT 'excited',
  personal_notes TEXT DEFAULT '',
  certificate_issued BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Attendance records table
CREATE TABLE IF NOT EXISTS attendance_records (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  class_number INTEGER,
  attended BOOLEAN,
  joined_at TIMESTAMP,
  recorded_on TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Quiz records table
CREATE TABLE IF NOT EXISTS quiz_records (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  topic TEXT,
  score INTEGER,
  total_questions INTEGER,
  percentage FLOAT,
  taken_on TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Assignment records table
CREATE TABLE IF NOT EXISTS assignment_records (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  assignment_number INTEGER,
  title TEXT,
  submission_file TEXT,
  score INTEGER,
  feedback TEXT,
  submitted_on TIMESTAMP,
  graded_on TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Courses table (for AI-generated courses)
CREATE TABLE IF NOT EXISTS courses (
  id TEXT PRIMARY KEY,
  title TEXT,
  topic TEXT,
  ai BOOLEAN DEFAULT FALSE,
  sections JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Student courses (enrollment tracking)
CREATE TABLE IF NOT EXISTS student_courses (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  student_id TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
  course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  progress FLOAT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SCHOOL PORTAL TABLES  (teachers, partners, admins, hub spaces)
-- ============================================================

-- Teachers table
CREATE TABLE IF NOT EXISTS teachers (
  teacher_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  phone TEXT,
  specialty TEXT,
  status TEXT DEFAULT 'active',
  hired_on DATE DEFAULT CURRENT_DATE,
  courses JSONB DEFAULT '[]'::jsonb,
  login_email TEXT,
  password_salt TEXT,
  password_hash TEXT,
  password_set_at TIMESTAMP,
  -- Single-device enforcement: the most recent sign-in writes its token here.
  session_token TEXT,
  session_active_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Partners / sponsors table.
-- sponsor_id is the public code a partner shares (e.g. "BOI-ORBIT-247").
-- Students type it during registration; the code is stored on the
-- student row (students.sponsor_id) so partners only ever see their
-- own sponsored cohort.
CREATE TABLE IF NOT EXISTS partners (
  partner_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sponsor_id TEXT UNIQUE NOT NULL,
  org_name TEXT NOT NULL,
  contact_person TEXT,
  email TEXT,
  phone TEXT,
  status TEXT DEFAULT 'active',
  notes TEXT DEFAULT '',
  login_email TEXT,
  password_salt TEXT,
  password_hash TEXT,
  password_set_at TIMESTAMP,
  -- 'partner' = real partner (manages teacher accounts); 'parent' = read-only monitoring.
  partner_type TEXT DEFAULT 'partner',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Admins table
CREATE TABLE IF NOT EXISTS admins (
  admin_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE,
  phone TEXT,
  access_level TEXT DEFAULT 'full',
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Hub spaces table (physical / virtual hubs, e.g. Lagos Innovation Hub)
CREATE TABLE IF NOT EXISTS hub_spaces (
  hub_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  location TEXT,
  hub_type TEXT DEFAULT 'classroom',
  capacity INTEGER DEFAULT 0,
  manager_name TEXT,
  status TEXT DEFAULT 'open',
  facilities JSONB DEFAULT '[]'::jsonb,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ADMIN PRICING + PARTNER FEE AGREEMENTS
-- ============================================================

-- School fee per course. The registration page reads the amount from here
-- for BOTH the Paystack checkout and the bank-transfer slip, so whatever
-- the admin sets becomes the price students are charged.
CREATE TABLE IF NOT EXISTS course_fees (
  course TEXT PRIMARY KEY,
  amount INTEGER NOT NULL,
  currency TEXT DEFAULT 'NGN',
  updated_at TIMESTAMP DEFAULT NOW(),
  updated_by TEXT DEFAULT 'admin'
);

-- Per-partner fee agreements. When a student registers with a partner's
-- sponsor ID, an ACTIVE agreement for their course overrides the base
-- course_fees price — this is how the fee deal between the admin and the
-- partner is honoured automatically at registration.
CREATE TABLE IF NOT EXISTS partner_fees (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  sponsor_id TEXT NOT NULL,
  course TEXT NOT NULL,
  amount INTEGER NOT NULL,
  currency TEXT DEFAULT 'NGN',
  active BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_students_email ON students(email);
CREATE INDEX IF NOT EXISTS idx_students_phone ON students(phone);
CREATE INDEX IF NOT EXISTS idx_students_career_path ON students(career_path);
CREATE INDEX IF NOT EXISTS idx_students_intake_month ON students(intake_month);
CREATE INDEX IF NOT EXISTS idx_students_class_group ON students(class_group);
CREATE INDEX IF NOT EXISTS idx_students_sponsor_id ON students(sponsor_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student_id ON attendance_records(student_id);
CREATE INDEX IF NOT EXISTS idx_quiz_student_id ON quiz_records(student_id);
CREATE INDEX IF NOT EXISTS idx_assignment_student_id ON assignment_records(student_id);
CREATE INDEX IF NOT EXISTS idx_student_courses_student_id ON student_courses(student_id);
CREATE INDEX IF NOT EXISTS idx_partners_sponsor_id ON partners(sponsor_id);
CREATE INDEX IF NOT EXISTS idx_teachers_email ON teachers(email);
CREATE INDEX IF NOT EXISTS idx_hub_spaces_status ON hub_spaces(status);
CREATE INDEX IF NOT EXISTS idx_partner_fees_sponsor ON partner_fees(sponsor_id);

-- ============================================================
-- PERFORMANCE INDEXES  (added 2026-09 — scale hardening)
-- ------------------------------------------------------------
-- These match the real query patterns of the portal:
--   * students.payment_status  -> boirsu morning check-in / motivation
--                                 filters paid students
--   * students.created_at      -> admin "last 30 days" registrations
--   * students.course_name     -> cohort grouping / classroom rooms
--   * timestamp columns        -> activity feeds sort by taken_on /
--                                 recorded_on / submitted_on
--   * status columns           -> portal lists filter status='active'
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_students_payment_status ON students(payment_status);
CREATE INDEX IF NOT EXISTS idx_students_created_at ON students(created_at);
CREATE INDEX IF NOT EXISTS idx_students_course_name ON students(course_name);
CREATE INDEX IF NOT EXISTS idx_quiz_taken_on ON quiz_records(taken_on);
CREATE INDEX IF NOT EXISTS idx_attendance_recorded_on ON attendance_records(recorded_on);
CREATE INDEX IF NOT EXISTS idx_assignment_submitted_on ON assignment_records(submitted_on);
CREATE INDEX IF NOT EXISTS idx_student_courses_course_id ON student_courses(course_id);
CREATE INDEX IF NOT EXISTS idx_teachers_status ON teachers(status);
CREATE INDEX IF NOT EXISTS idx_partners_status ON partners(status);
CREATE INDEX IF NOT EXISTS idx_partner_fees_active ON partner_fees(active);

-- Login-email uniqueness (teacher/partner logins are minted in the school
-- portal; duplicate emails are rejected with Postgres error 23505, which the
-- portal pages translate into "that login email is already used").
CREATE UNIQUE INDEX IF NOT EXISTS idx_teachers_login_email ON teachers(login_email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_login_email ON partners(login_email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_partner_fees_unique ON partner_fees(sponsor_id, course);

