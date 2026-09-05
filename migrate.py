"""
migrate.py — Standalone Database Migration & Schema Sync Script for markkundo.
Run: python migrate.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from sqlalchemy import inspect, text

def run_migrations():
    app = create_app()
    with app.app_context():
        print("Starting Database Schema Verification & Sync...")
        db.create_all()

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables in Database: {tables}")

        def add_column_if_missing(table_name, column_name, column_type):
            if table_name in tables:
                columns = [col['name'] for col in inspector.get_columns(table_name)]
                if column_name not in columns:
                    db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"))
                    db.session.commit()
                    print(f"  + Added column '{column_name}' ({column_type}) to table '{table_name}'")
                else:
                    print(f"  [OK] Column '{column_name}' exists in '{table_name}'")


        # Students columns
        add_column_if_missing('students', 'course', 'VARCHAR(100)')
        add_column_if_missing('students', 'college', 'VARCHAR(255)')
        add_column_if_missing('students', 'enrolled_subjects', 'TEXT')

        # Marks columns
        add_column_if_missing('marks', 'semester', 'INTEGER')

        # Subjects columns
        add_column_if_missing('subjects', 'credits', 'INTEGER DEFAULT 4')
        add_column_if_missing('subjects', 'is_elective', 'BOOLEAN DEFAULT FALSE')
        add_column_if_missing('subjects', 'elective_group', 'VARCHAR(100)')

        print("\nDatabase Schema is completely synchronized and production-ready!")

if __name__ == '__main__':
    run_migrations()
