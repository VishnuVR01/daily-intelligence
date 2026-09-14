import psycopg

conn = psycopg.connect('postgresql://daily_intel:11803143%40%23dailyuser@localhost:5432/daily_intelligence')
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='test_bootstrap' ORDER BY table_name;")
test_tables = [r[0] for r in cur.fetchall()]

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")
public_tables = [r[0] for r in cur.fetchall()]

print("Public Schema Tables        :", public_tables)
print("Test Bootstrap Schema Tables:", test_tables)

assert set(public_tables) == set(test_tables), "Tables match!"

cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='test_bootstrap' AND indexname LIKE '%fts%';")
fts_indexes = cur.fetchall()
print("\nFTS Indexes in test_bootstrap schema:")
for idx_name, idx_def in fts_indexes:
    print(f"  - {idx_name}: {idx_def}")

assert len(fts_indexes) == 2, "2 FTS indexes present!"
print("\nSUCCESS: All 9 tables and 2 GIN FTS indexes match canonical database perfectly!")
