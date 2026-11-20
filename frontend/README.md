# GlucoRAG frontend

React 19 + Vite interface for the GlucoRAG FastAPI backend.

## Start

```powershell
npm install
npm run dev
```

Vite normally serves the app at `http://localhost:5173`.

The frontend expects the backend at `http://127.0.0.1:8000`. To override this, create `.env` in this folder:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Restart Vite after editing `.env`. See the root `README.md` for full setup instructions, API endpoints, feature descriptions, and safety limitations.
