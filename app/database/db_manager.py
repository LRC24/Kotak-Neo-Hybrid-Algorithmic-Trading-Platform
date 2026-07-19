import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from config import get_config
from ..logging import db_logger

config = get_config()
DATABASE_URI = config.SQLALCHEMY_DATABASE_URI

db_logger.info(f"Connecting to database at: {DATABASE_URI}")

# Create database engine with busy timeout configuration for thread safety
engine = create_engine(
    DATABASE_URI,
    connect_args={"timeout": 30},
    echo=False
)

# Apply SQLite WAL optimizations on connect event
@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        db_logger.debug("SQLite WAL, NORMAL sync, and FK pragmas configured successfully.")
    except Exception as e:
        db_logger.error(f"Failed to apply database pragmas: {e}")
    finally:
        cursor.close()

# Scoped session factory
session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db_session = scoped_session(session_factory)

# Base class for SQLAlchemy ORM models
Base = declarative_base()

def init_db():
    """Builds database schemas if they are missing"""
    try:
        db_logger.info("Building database schemas...")
        Base.metadata.create_all(bind=engine)
        db_logger.info("Database schemas built successfully.")
    except Exception as e:
        db_logger.critical(f"Failed to build database schemas: {e}", exc_info=True)
        raise

def get_db_session():
    """Returns the current thread-safe scoped session"""
    return db_session()
