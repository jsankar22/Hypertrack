# MSc AI-Powered Fitness Assistant - Phase 1

This repository contains Phase 1 of the MSc AI-Powered Fitness Assistant. This is a fully functional web application built with Django, Tailwind CSS, and Chart.js, covering user authentication, profile setup, workout tracking, and nutrition logging.

---

## Tech Stack

- **Backend**: Django 5 (Python 3.11) + Django REST Framework
- **Frontend**: Django Templates + Tailwind CSS (via CDN)
- **Charts**: Chart.js (via CDN)
- **Database**: PostgreSQL (via django-environ) with automatic fallback to SQLite (db.sqlite3) for instant out-of-the-box local execution
- **API integrations**: USDA FoodData Central API for nutritional searches

---

## Folder Structure

```
fitness_assistant/
  ├── fitness_assistant/        # Django settings, root URLs, and setup
  ├── accounts/                 # Custom User authentication and dashboard app
  ├── workouts/                 # Workout metrics and volume tracking app
  ├── nutrition/                # Nutrition tracking and USDA API proxy client app
  ├── templates/                # Shared base and app templates
  ├── static/                   # Global CSS and JS interactions
  ├── manage.py                 # Django administrative entry point
  ├── requirements.txt          # Python dependencies
  ├── .env                      # Active local environments config
  └── README-phase1.md          # Setup and testing instructions (this file)
```

---

## Local Setup Instructions

### 1. Create and Activate Virtual Environment
Open a terminal in the `fitness_assistant` directory:

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables Settings
We provide an `.env.example` in the project root. The `.env` file is initialized to use local SQLite immediately.
Ensure your `.env` contains:
```ini
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
USDA_API_KEY=DEMO_KEY
# Keep DATABASE_URL commented out to fallback automatically to SQLite
# DATABASE_URL=postgres://user:password@localhost:5432/dbname
```

### 4. Run DB Migrations
Generate tables using the prepackaged migration operations:
```bash
python manage.py migrate
```

### 5. Create a Superuser (Optional)
To inspect logs inside the Django Admin panel at `http://127.0.0.1:8000/admin/`:
```bash
python manage.py createsuperuser
```

### 6. Start the Server
```bash
python manage.py runserver
```
The application will launch on [http://localhost:8000](http://localhost:8000).

---

## Run Unit Tests
To run the automated test suite verifying auth redirection, validations, API endpoints, and user constraints:
```bash
python manage.py test
```
The test suite utilizes the standard Django SQLite test database automatically.
