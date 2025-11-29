# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv
import os

# Define ROOT like in main.py to ensure correct .env path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))

# Check multiple possible env var names (Vercel uses NEON_ prefix)
DATABASE_URL = (
    os.getenv("DATABASE_URL") or 
    os.getenv("POSTGRES_PRISMA_URL") or
    os.getenv("NEON_DATABASE_URL") or
    os.getenv("NEON_POSTGRES_PRISMA_URL")
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Test connections before using them
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_size=5,         # Maximum number of connections to keep
    max_overflow=10      # Maximum number of connections that can be created beyond pool_size
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)
    role = Column(String)

class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    year = Column(String(10))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    # Relationship to stories
    stories = relationship("Story", back_populates="book")

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), unique=True, nullable=False)
    book_slug = Column(String(100), nullable=False)  # Keep for backwards compatibility
    book_id = Column(Integer, ForeignKey("books.id"), nullable=True)  # New FK relationship
    pages = Column(String(50))
    keywords = Column(Text)
    start_char = Column(Integer, default=0)
    end_char = Column(Integer, default=0)
    indexed = Column(Boolean, default=False)  # Add this line
    # Relationships
    book = relationship("Book", back_populates="stories")
    categories = relationship("CodexNode", secondary="node_stories", back_populates="stories")

class CodexNode(Base):
    __tablename__ = "codex_nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("codex_nodes.id"))
    parent = relationship("CodexNode", remote_side=[id], backref="children")
    stories = relationship("Story", secondary="node_stories", back_populates="categories")

class NodeStory(Base):
    __tablename__ = "node_stories"
    node_id = Column(Integer, ForeignKey("codex_nodes.id"), primary_key=True)
    story_id = Column(Integer, ForeignKey("stories.id"), primary_key=True)