"""Database connection and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator

from disparaai.database.models import Base
from disparaai.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Database connection manager."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", 
            "postgresql+psycopg://user:password@localhost:5432/disparaai"
        )
        
        # Create engine
        self.engine = create_engine(
            self.database_url,
            poolclass=StaticPool,
            pool_pre_ping=True,
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true"
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, 
            autoflush=False, 
            bind=self.engine
        )
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session with automatic cleanup.
        
        Yields:
            SQLAlchemy session
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_session_sync(self) -> Session:
        """
        Get database session (synchronous).
        
        Returns:
            SQLAlchemy session
        """
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.
    
    Yields:
        Database session
    """
    with db_manager.get_session() as session:
        yield session


def init_database():
    """Initialize database tables."""
    try:
        db_manager.create_tables()
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        logger.info("Please run: uv run python -m disparaai.database.init")
        raise


if __name__ == "__main__":
    init_database()