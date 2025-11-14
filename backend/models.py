# backend/models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

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