# AutoCleanAI

**AutoCleanAI** is an AI-Assisted Data Quality Analysis, Transformation & Validation Platform.

## Architecture

This project is divided into a frontend (Next.js) and a backend (FastAPI).

### Local Setup (Without Docker)

#### Backend
1. Open a terminal in the `backend` folder.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in your details (AWS credentials, etc).
5. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The backend will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

#### Frontend
1. Open a terminal in the `frontend` folder.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js dev server:
   ```bash
   npm run dev
   ```
   The frontend will be available at [http://localhost:3000](http://localhost:3000).

## Note on Architecture
Due to the lack of Docker in the local environment, the local setup defaults to using **SQLite** (instead of PostgreSQL) and **ThreadPoolExecutor** (instead of Celery/Redis) for background tasks.
