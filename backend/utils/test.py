from backend.database.connect_cassandra import session

rows = session.execute("SELECT * FROM subjects WHERE id = 2733926 ALLOW FILTERING")
for row in rows:
    print(row)
