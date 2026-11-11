# EduEval AI

## Project Overview

EduEval AI is an academic evaluation and student feedback platform for
educational institutions. It provides separate portals for administrators,
faculty, and students.

Faculty can create subjects and assessments, upload course material, define
marking rubrics, evaluate student submissions with AI assistance, review and
edit scores and feedback, approve evaluations, and publish final results.
Students can submit documents and view approved evaluation reports.
Administrators manage users, subjects, enrollments, faculty assignments, and
system activity.

## Main Features

- Role-based Admin, Faculty, and Student portals
- JWT authentication and role-protected API routes
- Upload and extraction of PDF, DOC/DOCX, PPT/PPTX, TXT, and image submissions
- OCR support for scanned documents and images
- Subject-specific retrieval-augmented generation using course references
- AI-generated criterion marks, feedback, strengths, weaknesses, and suggestions
- Rubric validation that enforces criterion and maximum-mark limits
- Faculty editing of final scores, criterion marks, feedback, and internal notes
- Idempotent re-evaluation that preserves the existing AI evaluation
- Faculty approval, rejection, and publication workflow
- Student-facing feedback and downloadable evaluation reports
- Audit logging for important administrative and evaluation actions

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Axios
- React Router
- Lucide React
- React Hot Toast

### Backend

- Python 3.11
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic and Pydantic Settings
- JWT authentication with Python-Jose
- Passlib and Bcrypt password hashing

### AI and Document Processing

- OpenAI-compatible API through the OpenAI Python SDK
- Sentence Transformers for local embeddings
- FAISS CPU for subject-specific vector search
- PyMuPDF for PDF extraction
- python-docx and python-pptx for Office documents
- Pillow and Tesseract OCR for image and scanned-document processing
- ReportLab for PDF evaluation reports

### Storage

- SQLite for local development
- Uploaded documents stored under `Backend/uploads/`
- FAISS indexes stored under `Backend/faiss_indexes/`

For production, use a managed database and persistent object/file storage
instead of relying on local SQLite and ephemeral deployment disk.

## Deployment Architecture

The frontend and backend should be deployed separately:

1. Deploy `Frontend` to Vercel.
2. Deploy `Backend` to Render or another Python-capable service.
3. Set `VITE_API_BASE_URL` in the frontend to the deployed backend URL.
4. Set `OPENAI_API_KEY`, `SECRET_KEY`, `DATABASE_URL`, and `CORS_ORIGINS`
   only in the backend service environment.

The OpenAI API key must never be placed in frontend source code or in a
`VITE_` environment variable because Vite variables are bundled into the
browser.

## Render Backend Settings

When the Render service root directory is `Backend`, use:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The `Backend/runtime.txt` file pins the service to Python 3.11.9, which keeps
the scientific-computing dependencies compatible with the application.

## Environment Variables

Backend:

```env
OPENAI_API_KEY=server-only-secret
OPENAI_MODEL=gpt-4o-mini
SECRET_KEY=long-random-production-secret
DATABASE_URL=production-database-url
CORS_ORIGINS=https://your-frontend.vercel.app
```

Frontend:

```env
VITE_API_BASE_URL=https://your-backend.onrender.com
```

Never commit `.env` files, API keys, passwords, or production secrets.
