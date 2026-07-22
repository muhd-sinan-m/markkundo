"""
run.py — Entry point for the markkundo Flask application.

Development:   python run.py
Production:    gunicorn "run:app"
"""
import os
from dotenv import load_dotenv

# Load .env before creating the app so all config picks up env vars
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()

if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '1') == '1'
    port = int(os.getenv('PORT')) if os.getenv('PORT') else 5000
    app.run(debug=debug, port=port)
