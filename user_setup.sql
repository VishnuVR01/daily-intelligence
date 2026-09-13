CREATE USER daily_intel
WITH PASSWORD '11803143@#dailyuser';
--updated password 11803143%40%23dailyuser

CREATE DATABASE daily_intelligence
WITH
OWNER = daily_intel
ENCODING = 'UTF8';

GRANT ALL PRIVILEGES
ON DATABASE daily_intelligence
TO daily_intel;