import sqlite3
from config import DATABASE_PATH

def insert_sample_data():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()

    # Insert sample candidates
    c.execute('DELETE FROM candidates')
    c.execute('''
    INSERT INTO candidates (candidate_id, name, skills, preferred_locations, education)
    VALUES (?, ?, ?, ?, ?)
    ''', ('c1', 'John Doe', 'python,data analysis', 'bangalore,hyderabad', 'B.Tech'))

    c.execute('''
    INSERT INTO candidates (candidate_id, name, skills, preferred_locations, education)
    VALUES (?, ?, ?, ?, ?)
    ''', ('c2', 'Jane Smith', 'java,communication', 'mumbai,delhi', 'BBA'))

    # Insert sample internships
    c.execute('DELETE FROM internships')
    c.execute('''
    INSERT INTO internships (internship_id, company, job_title, description, skills_required, location)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('i1', 'DataCorp', 'Data Science Intern', 'Analyze datasets for insights', 'python,machine learning', 'bangalore'))

    c.execute('''
    INSERT INTO internships (internship_id, company, job_title, description, skills_required, location)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('i2', 'TechSoft', 'Backend Developer Intern', 'Assist in backend APIs', 'python,django', 'chennai'))

    c.execute('''
    INSERT INTO internships (internship_id, company, job_title, description, skills_required, location)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('i3', 'AI Labs', 'Machine Learning Intern', 'Build ML models and process data', 'python,data analysis,tensorflow', 'hyderabad'))

    c.execute('''
    INSERT INTO internships (internship_id, company, job_title, description, skills_required, location)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('i4', 'WebWorks', 'Front-end Developer Intern', 'Develop UI using React', 'javascript,css', 'mumbai'))

    c.execute('''
    INSERT INTO internships (internship_id, company, job_title, description, skills_required, location)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', ('i5', 'CloudNet', 'Data Analyst Intern', 'Analyze datasets and reports', 'excel,data analysis', 'bangalore'))

    conn.commit()
    conn.close()
    print("Sample data inserted successfully.")

if __name__ == "__main__":
    insert_sample_data()
