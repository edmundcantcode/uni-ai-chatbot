# schema_dump.py
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import os

HOST     = os.getenv("CASSANDRA_HOST", "localhost")
PORT     = int(os.getenv("CASSANDRA_PORT", 9042))
KEYSPACE = os.getenv("CASSANDRA_KEYSPACE")  # optional: limit to one KS
USER     = os.getenv("CASSANDRA_USERNAME")
PASS     = os.getenv("CASSANDRA_PASSWORD")

def main():
    auth = PlainTextAuthProvider(USER, PASS) if USER and PASS else None
    cluster = Cluster([HOST], port=PORT, auth_provider=auth)
    session = cluster.connect()
    meta = cluster.metadata

    ks_names = [KEYSPACE] if KEYSPACE else list(meta.keyspaces.keys())
    for ks in ks_names:
        if ks not in meta.keyspaces:
            print(f"[!] Keyspace '{ks}' not found"); continue
        print(f"\n=== KEYSPACE: {ks} ===")
        for tname, tmeta in meta.keyspaces[ks].tables.items():
            print(f"\n--- TABLE: {tname} ---")
            print("Columns:")
            for cname, cmeta in tmeta.columns.items():
                print(f"  - {cname}: {cmeta.cql_type}")
            pk = [c.name for c in tmeta.primary_key]
            print("Primary key :", pk)
            print("DDL:\n", tmeta.export_as_string())

    session.shutdown()
    cluster.shutdown()

if __name__ == "__main__":
    main()
