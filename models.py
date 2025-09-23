import sqlite3
from config import DATABASE_PATH

def create_tables():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Create candidates table
    c.execute('''
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id TEXT PRIMARY KEY,
        name TEXT,
        skills TEXT,
        preferred_locations TEXT,
        education TEXT
    )
    ''')

    # Create internships table
    c.execute('''
    CREATE TABLE IF NOT EXISTS internships (
        internship_id TEXT PRIMARY KEY,
        company TEXT,
        job_title TEXT,
        description TEXT,
        skills_required TEXT,
        location TEXT
    )
    ''')

    conn.commit()
    conn.close()
    print("Tables created successfully.")

if __name__ == "__main__":
    create_tables()
