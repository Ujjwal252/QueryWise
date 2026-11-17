
# QueryWise

**Intelligent Database Query Optimizer with Security Analysis**

QueryWise is a web-based application that analyzes SQL queries, suggests optimized alternatives, evaluates query performance, and identifies potential database security risks.

## Features

- User authentication and database connection management.
- SQL parsing, validation, and query analysis.
- Automatic SQL query optimization.
- MySQL execution plan analysis using EXPLAIN.
- Index recommendations.
- Query performance benchmarking.
- Query result equivalence verification.
- Database security analysis and sensitive-column detection.
- Query history and performance dashboard.

## Tech Stack

**Frontend:** React, JavaScript, Vite

**Backend:** Python, Flask

**Database:** MySQL 8.0+

**SQL Parser:** SQLGlot

## Project Structure

```text
QueryWise/
├── backend/
├── frontend/
├── README.md
└── .gitignore
```

## Getting Started

### Backend

```bash
cd backend
python -m venv ../venv
```

Activate the virtual environment and install dependencies:

```powershell
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Configure the required environment variables in `backend/.env` before starting the backend.

### Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend at:

`http://localhost:5173`

Backend default address:

`http://localhost:5000`

## Security

- Database credentials are encrypted before storage.
- SQL validation restricts query operations to approved read-only SELECT statements.
- Database connections use least-privilege credentials.
- Security findings help identify potential risks.

## Project Status

Under development. Core backend and frontend modules are implemented. Final integration testing and documentation are in progress.