# RAG Chat Frontend

React + TypeScript + TailwindCSS frontend for the RAG PDF chatbot.

## Structure

```
src/
├── components/
│   ├── Sidebar.tsx        # Left panel: upload, document list, re-index
│   ├── ChatWindow.tsx     # Main chat area, input bar
│   ├── MessageBubble.tsx # User/assistant messages, citations, copy
│   ├── UploadDropzone.tsx # Drag & drop, progress bar
│   ├── ThinkingIndicator.tsx # Animated "Thinking…" state
│   ├── LoginScreen.tsx    # Auth form
│   └── Toast.tsx          # Success/error notifications
├── hooks/
│   ├── useAuth.ts         # JWT login/logout state
│   └── useDocuments.ts    # Document list, upload, delete
├── App.tsx
├── main.tsx
└── index.css
```

## Scripts

- `npm run dev` — Dev server (port 5173) with API proxy to backend
- `npm run build` — Production build → `dist/`
- `npm run preview` — Preview production build

## API Integration

- `POST /users/register`, `POST /users/login` — Auth
- `POST /upload` — File upload (multipart)
- `GET /ask?query=...&token=...` — SSE streaming
- `GET /documents` — List documents
- `DELETE /documents/:id` — Remove document
- `POST /analyze` — Weather/analysis requests
