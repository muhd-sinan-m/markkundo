import psycopg2

db_url = 'postgresql://postgres.tjjnpmmwcpmkbksawfpq:Akshara2003200@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres'
conn = psycopg2.connect(db_url)
cur = conn.cursor()

# Add credits column if missing
cur.execute('ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS credits INTEGER DEFAULT 4')

credits_map = {
    # Sem 1
    'Cyber Laws and Security': 4,
    'Digital Fundamentals': 4,
    'Discrete mathematics': 4,
    'Fundamentals of Programming Using C++': 4,
    'English for Science': 3,
    'Principles and Practices of  Management': 4,
    'Financial Accounting': 4,
    'Business Statistics and Logic': 4,
    'Business Communication - I': 3,
    'Indian Systems of Health &  Wellness': 2,
    'Environmental Science and  Sustainability': 2,
    # Sem 2
    'Web Technologies': 4,
    'Operating Systems': 4,
    'Data Structures': 4,
    'Mathematics Foundations to Computer Science': 4,
    'AEC - English': 3,
    'Indian Constitution: Legal and Ethical Perspectives': 2,
    'Human Behavior and Organization': 4,
    'Marketing Management': 4,
    'Business Economics': 4,
    'Media Literacy and Critical Thinking': 3,
    # Sem 3
    'Python': 4,
    'DBMS': 4,
    'Design and Analysis of Algorithms': 4,
    'Software Engineering': 4,
    'Quantitative Techniques': 4,
    'Feature Engineering': 3,
    'Human Resources Management and Industrial Relations': 4,
    'Cost and Management Accounting': 4,
    'Legal Framework for Business Transactions': 4,
    'Indian Ethos in Management': 3,
    'Management Information System': 4,
    # Sem 4
    'Object Oriented Programming Using Java': 4,
    'Design Thinking and Innovation': 3,
    'Entrepreneurship and Startup Ecosystem': 3,
    'Probability Distributions and Statistical Inference': 4,
    'Artificial Intelligence': 4,
    'Network Simulation': 3,
    'Introduction to Machine Learning': 4,
    'Business Environment and Public Policy': 4,
    'Financial Management': 4,
    'Entrepreneurship and Start-Ups': 3,
    'Business Research Methods': 4,
    # Sem 5
    'Computer Networks': 4,
    'Digital Marketing': 3,
    'Disaster Management': 3,
    'Introduction to Deep Learning': 4,
    'Natural Language Processing': 4,
    'Cloud Security': 4,
    'Web Development with Python Django/Flask': 4,
    'Modern Web Application Devolopment with React.js': 4,
    'Digital Image Processing': 4
}

for name, cr in credits_map.items():
    cur.execute('UPDATE public.subjects SET credits = %s WHERE name = %s', (cr, name))

cur.execute("UPDATE public.subjects SET credits = 3 WHERE name LIKE 'AEC%'")
conn.commit()
print("Successfully populated credits column in database!")
