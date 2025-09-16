"""Database initialization script."""

import os
import sys
from urllib.parse import urlparse
import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

from disparaai.database.models import Base
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)


def create_database_if_not_exists(database_url: str):
    """
    Create the database if it doesn't exist.
    
    Args:
        database_url: Full database connection URL
    """
    # Parse the database URL
    parsed = urlparse(database_url)
    
    # Extract connection details
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    username = parsed.username or "disparaai"  # Default to disparaai user
    password = parsed.password or ""
    database_name = parsed.path.lstrip("/") if parsed.path else "disparaai"
    
    # Try to connect directly to the target database first
    try:
        # Test connection to target database
        test_engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
        with test_engine.connect():
            logger.info(f"✅ Database '{database_name}' already exists and is accessible")
            test_engine.dispose()
            return
    except:
        pass
    
    # If target database doesn't exist, try to create it
    # Use the provided user credentials to connect to postgres database
    admin_url = f"postgresql+psycopg://{username}:{password}@{host}:{port}/postgres"
    
    logger.info(f"🔍 Checking if database '{database_name}' exists...")
    
    try:
        # Connect to PostgreSQL server (postgres database)
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        
        with admin_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": database_name}
            )
            
            if result.fetchone():
                logger.info(f"✅ Database '{database_name}' already exists")
            else:
                logger.info(f"🔨 Creating database '{database_name}'...")
                conn.execute(text(f'CREATE DATABASE "{database_name}"'))
                logger.info(f"✅ Database '{database_name}' created successfully")
        
        admin_engine.dispose()
        
    except Exception as e:
        logger.error(f"❌ Error creating database: {str(e)}")
        logger.info("\n💡 Manual database creation:")
        logger.info(f"   sudo -u postgres createdb {database_name}")
        logger.info(f"   # OR connect to PostgreSQL and run:")
        logger.info(f"   CREATE DATABASE {database_name};")
        raise


def init_tables(database_url: str):
    """
    Initialize database tables.
    
    Args:
        database_url: Database connection URL
    """
    logger.info("🔨 Creating database tables...")
    
    try:
        engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully!")
        
        # Print created tables
        logger.info("\n📋 Created tables:")
        for table_name in Base.metadata.tables.keys():
            logger.info(f"   • {table_name}")
        
        engine.dispose()
        
    except Exception as e:
        logger.error(f"❌ Error creating tables: {str(e)}")
        raise


def main():
    """Main initialization function."""
    logger.info("🚀 Initializing DisparaAI Database...\n")
    
    # Load environment variables
    load_dotenv()
    
    # Get database URL from environment or use default
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://disparaai:disparaai123@localhost:5432/disparaai"
    )
    
    logger.info(f"🔗 Database URL: {database_url.replace(database_url.split('@')[0].split('://')[1], '***')}")
    
    try:
        # Step 1: Create database if it doesn't exist
        create_database_if_not_exists(database_url)
        
        # Step 2: Create tables
        init_tables(database_url)
        
        logger.info("\n🎉 Database initialization completed successfully!")
        logger.info("\n📝 Next steps:")
        logger.info("   1. Update your .env file with the correct DATABASE_URL")
        logger.info("   2. Run: uv run python main.py")
        
    except Exception as e:
        logger.error(f"\n💥 Database initialization failed: {str(e)}")
        logger.info("\n🔧 Troubleshooting steps:")
        logger.info("   1. Make sure PostgreSQL is running:")
        logger.info("      sudo systemctl start postgresql")
        logger.info("   2. Check PostgreSQL connection:")
        logger.info("      psql -h localhost -U postgres -d postgres")
        logger.info("   3. Update DATABASE_URL in .env file")
        logger.info("   4. Install PostgreSQL if not installed:")
        logger.info("      sudo apt install postgresql postgresql-contrib")
        sys.exit(1)


if __name__ == "__main__":
    main()