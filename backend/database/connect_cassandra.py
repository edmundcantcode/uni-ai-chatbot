from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.policies import DCAwareRoundRobinPolicy
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global session and cluster
session = None
cluster = None

def get_cassandra_config():
    """Load Cassandra config from environment"""
    return {
        'hosts': [os.getenv('CASSANDRA_HOST', 'localhost')],
        'port': int(os.getenv('CASSANDRA_PORT', 9042)),
        'keyspace': os.getenv('CASSANDRA_KEYSPACE', 'university'),
        'username': os.getenv('CASSANDRA_USERNAME'),
        'password': os.getenv('CASSANDRA_PASSWORD'),
    }

async def initialize_database():
    """Initialize Cassandra connection with retry"""
    global session, cluster

    if session is not None:
        return session

    config = get_cassandra_config()
    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Attempting to connect to Cassandra... (attempt {attempt + 1}/{max_retries})")

            # Authentication if provided
            auth_provider = None
            if config['username'] and config['password']:
                auth_provider = PlainTextAuthProvider(config['username'], config['password'])

            # Connect to cluster
            cluster = Cluster(
                config['hosts'],
                port=config['port'],
                auth_provider=auth_provider,
                load_balancing_policy=DCAwareRoundRobinPolicy(),
                protocol_version=4
            )

            session = cluster.connect()

            # Try to create keyspace (but don't fail if it doesn't work)
            try:
                session.execute(f"""
                    CREATE KEYSPACE IF NOT EXISTS {config['keyspace']}
                    WITH replication = {{
                        'class': 'SimpleStrategy',
                        'replication_factor': 1
                    }}
                """)
                logger.info(f"✅ Keyspace {config['keyspace']} created/verified")
            except Exception as keyspace_error:
                logger.warning(f"⚠️ Could not create keyspace (this is OK if it already exists): {keyspace_error}")

            # Set keyspace - this should work even without CREATE permissions
            session.set_keyspace(config['keyspace'])
            logger.info(f"✅ Using keyspace: {config['keyspace']}")

            # Test with a simple query that doesn't require specific tables
            try:
                # Try to query a table if it exists
                session.execute("SELECT COUNT(*) FROM students LIMIT 1")
                logger.info("✅ Successfully queried students table")
            except Exception as query_error:
                logger.warning(f"⚠️ Could not query students table (table might not exist): {query_error}")
                # Just test basic connection instead
                session.execute("SELECT release_version FROM system.local")
                logger.info("✅ Basic Cassandra connection verified")

            logger.info("✅ Connected to Cassandra successfully")
            return session

        except Exception as e:
            logger.error(f"❌ Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise Exception(f"❌ Could not connect to Cassandra after {max_retries} attempts: {e}")

def close_connection():
    """Close Cassandra session and cluster"""
    global session, cluster

    if session:
        session.shutdown()
        session = None

    if cluster:
        cluster.shutdown()
        cluster = None

    logger.info("✅ Database connection closed")

def get_session():
    """Access the current Cassandra session"""
    global session
    if session is None:
        raise Exception("⚠️ Database not initialized. Call initialize_database() first.")
    return session