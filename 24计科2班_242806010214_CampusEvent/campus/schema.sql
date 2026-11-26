CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    grade INTEGER NOT NULL DEFAULT 1 CHECK (grade BETWEEN 1 AND 4)
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    start_at TEXT NOT NULL,
    location TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    policy_type TEXT NOT NULL CHECK (policy_type IN ('direct', 'audit')),
    grade_limited INTEGER NOT NULL DEFAULT 0 CHECK (grade_limited IN (0, 1)),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    student_id TEXT NOT NULL REFERENCES students(student_id),
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_registration_active
    ON registrations(activity_id, student_id)
    WHERE status IN ('PENDING', 'APPROVED');

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    activity_id TEXT NOT NULL REFERENCES activities(activity_id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    event_key TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS email_logs (
    log_id TEXT PRIMARY KEY,
    registration_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('SENT', 'FAILED')),
    error TEXT,
    created_at TEXT NOT NULL,
    event_key TEXT NOT NULL UNIQUE
);
