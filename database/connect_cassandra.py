from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

CASSANDRA_HOST = "sunway.hep88.com"
PORT = 9042
USERNAME = "planusertest"
PASSWORD = "Ic7cU8K965Zqx"
KEYSPACE = "subjectplanning"

auth_provider = PlainTextAuthProvider(username=USERNAME, password=PASSWORD)
cluster = Cluster([CASSANDRA_HOST], port=PORT, auth_provider=auth_provider)

try:
    session = cluster.connect()
    session.set_keyspace(KEYSPACE)
    print("✅ Connected to Cassandra:", KEYSPACE)
except Exception as e:
    print("❌ Failed to connect to Cassandra:", e)
    session = None
