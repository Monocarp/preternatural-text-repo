# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from dotenv import load_dotenv
import os

# Define ROOT like in main.py to ensure correct .env path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(ROOT, '.env.local'))

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
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

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), unique=True, nullable=False)
    book_slug = Column(String(100), nullable=False)
    pages = Column(String(50))
    keywords = Column(Text)
    start_char = Column(Integer, default=0)
    end_char = Column(Integer, default=0)
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