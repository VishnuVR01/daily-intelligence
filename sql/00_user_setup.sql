-- ============================================================
-- Daily Intelligence
-- PostgreSQL user and database bootstrap
-- ============================================================
-- Run this file as a PostgreSQL administrator.
--
-- SECURITY:
-- Replace CHANGE_ME locally before execution.
-- Do not commit a real password to Git.
-- ============================================================

CREATE USER daily_intel
WITH PASSWORD 'CHANGE_ME';

CREATE DATABASE daily_intelligence
WITH
    OWNER = daily_intel
    ENCODING = 'UTF8';

GRANT ALL PRIVILEGES
ON DATABASE daily_intelligence
TO daily_intel;
