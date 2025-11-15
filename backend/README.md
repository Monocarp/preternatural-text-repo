# Backend Server Setup

## Prerequisites
- Python 3.8+ installed
- Virtual environment (recommended)

## Installation

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Activate your virtual environment** (if using one):
   ```bash
   # On Windows (PowerShell)
   ..\venv\Scripts\Activate.ps1
   
   # On Windows (Command Prompt)
   ..\venv\Scripts\activate.bat
   
   # On Linux/Mac
   source ../venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Note: You may also need to install `PyJWT` and `cryptography` for JWT authentication:
   ```bash
   pip install PyJWT cryptography
   ```

## Running the Server

### Option 1: Run directly with Python
```bash
python main.py
```

### Option 2: Run with uvicorn (recommended for development)
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The `--reload` flag enables auto-reload on code changes.

## Verifying the Server is Running

1. **Check the console output** - You should see:
   ```
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```

2. **Test the health endpoint:**
   - Open your browser and go to: `http://127.0.0.1:8000/api/health`
   - Or use curl: `curl http://127.0.0.1:8000/api/health`
   - You should get a JSON response with status information

3. **Check API documentation:**
   - FastAPI automatically provides docs at: `http://127.0.0.1:8000/docs`
   - Alternative docs at: `http://127.0.0.1:8000/redoc`

## Troubleshooting

### Port Already in Use
If port 8000 is already in use, you can change it:
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```
Then update `frontend/vite.config.ts` to point to the new port.

### Database Connection Errors
The backend will automatically fall back to JSON file storage if no database is configured. This is normal for local development.

### Missing Dependencies
If you get import errors, make sure all dependencies are installed:
```bash
pip install -r requirements.txt
```

## Environment Variables (Optional)

Create a `.env.local` file in the project root if you want to use a database:
```
POSTGRES_PRISMA_URL=your_database_url_here
HF_TOKEN=your_huggingface_token_here
```

The backend will work without these - it will use JSON file storage instead.

