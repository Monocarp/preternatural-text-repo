import os
import sys
sys.path.insert(0, 'backend')
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env.local')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

db_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_PRISMA_URL')
if not db_url:
    print("No DATABASE_URL found")
    sys.exit(1)

db_url = db_url.replace('postgres://', 'postgresql://')
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

with Session() as db:
    # Delete the story that was just deleted from UI
    result = db.execute(text("DELETE FROM stories WHERE title LIKE '%Saligario%Treatise%' RETURNING title"))
    deleted = result.fetchall()
    db.commit()
    
    if deleted:
        print(f"DELETED: {deleted[0][0]}")
    else:
        print("Story not found")
    
    result = db.execute(text('SELECT COUNT(*) FROM stories'))
    print(f'Total stories: {result.scalar()}')
