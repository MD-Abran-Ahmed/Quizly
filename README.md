# 🧠 Quizly — AI-Powered Quiz & Assessment Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/framework-Flask%203.x-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-orange.svg)](https://aistudio.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Quizly** is a modern, intelligent quiz generation and self-assessment web application built with **Flask**, **SQLAlchemy**, and **Google Gemini AI**. Designed with an **Apple-inspired "Liquid Glass"** dark aesthetic, Quizly turns study notes and documents into interactive multiple-choice tests in seconds.

---

## ✨ Features

- 📄 **AI-Powered PDF to Quiz** — Upload lecture slides, study guides, or research papers (PDF) and automatically generate structured, curriculum-accurate MCQs using Google Gemini.
- 📊 **CSV Bulk Import** — Import questions in bulk using standard CSV files. Includes a downloadable sample template.
- ✍️ **Manual Question Builder** — Create custom questions on the fly with custom options, designated correct answers, and explanations.
- 🔐 **Dual Authentication** — Secure login via **Google OAuth 2.0** or traditional Email & Password with encrypted hashing.
- ⏱️ **Interactive Quiz Experience** — Real-time quiz taking with progress indicators, question navigation, immediate scoring, and in-depth explanations.
- 📈 **Performance Analytics** — Track accuracy, review previous quiz attempts, examine strengths and weaknesses, and retake tests anytime.
- 📱 **Responsive Glassmorphism UI** — Apple-inspired dark mode UI with frosted glass cards, warm amber accents, and mobile-responsive drawer navigation.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Backend** | Python 3.10+, Flask 3.x, Werkzeug |
| **Database** | SQLite (development) / PostgreSQL ready via SQLAlchemy |
| **AI / LLM** | Google Gemini API (`google-genai` SDK) |
| **Authentication** | Flask-Login, Authlib (Google OAuth 2.0) |
| **PDF Processing** | PyMuPDF (`pymupdf` / `fitz`) |
| **Frontend** | HTML5, Vanilla JavaScript (ES6+), CSS3 Glassmorphism |
| **Testing** | Pytest (100% core route & auth coverage) |

---

## 📁 Project Structure

```
Quizly/
├── app.py                  # Application entry point & route definitions
├── auth.py                 # Authentication blueprint (Email/Password + Google OAuth)
├── database.py             # SQLAlchemy models (User, Document, Quiz, Question, etc.)
├── ai_generator.py         # Google Gemini AI quiz generation engine
├── pdf_processor.py        # PDF text extraction & chunking using PyMuPDF
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables template (safe to commit)
├── .gitignore              # Git ignore rules (protects .env and database)
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Master layout with navigation & glass styles
│   ├── index.html          # Landing page
│   ├── login.html          # Login screen
│   ├── register.html       # User registration screen
│   ├── dashboard.html      # User analytics & quick actions hub
│   ├── notes.html          # Document & note library
│   ├── question_bank.html  # Stored questions repository
│   ├── upload_pdf.html     # PDF upload & AI generator trigger
│   ├── quiz_setup.html     # Quiz configuration (difficulty, count)
│   ├── take_quiz.html      # Live quiz-taking interface
│   ├── quiz_result.html    # Results breakdown & review
│   └── create_question.html# Manual question builder & CSV uploader
├── static/
│   ├── css/                # Apple-inspired Liquid Glass stylesheets
│   │   ├── style.css       # Global variables, typography, animations
│   │   ├── dashboard.css   # Dashboard & layout styling
│   │   ├── quiz.css        # Quiz interface styling
│   │   └── auth.css        # Auth forms styling
│   ├── js/                 # Modular client-side scripts
│   │   ├── main.js         # Core utilities & notifications
│   │   ├── dashboard.js    # Dashboard metrics & event handling
│   │   ├── quiz.js         # Interactive quiz controller
│   │   └── upload.js       # File upload & CSV processing
│   └── downloads/          # Sample templates (CSV demo)
└── tests/
    └── test_app.py         # Automated pytest test suite
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10** or higher
- **Git**
- A **Google Gemini API Key** (Free tier available at [Google AI Studio](https://aistudio.google.com/))
- *(Optional)* **Google OAuth Credentials** (from [Google Cloud Console](https://console.cloud.google.com/)) for Google Sign-In

---

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<YOUR_GITHUB_USERNAME>/Quizly.git
   cd Quizly
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to `.env`:
   ```bash
   # Windows
   copy .env.example .env

   # macOS / Linux
   cp .env.example .env
   ```

   Open `.env` in your text editor and fill in your keys:
   ```env
   # Required: Flask Secret Key
   SECRET_KEY=generate_a_random_secure_key_here

   # Port configuration
   PORT=5000
   FLASK_DEBUG=True

   # Database (defaults to local SQLite)
   DATABASE_URI=sqlite:///quizly.db

   # Required for AI generation:
   GEMINI_API_KEY=your_gemini_api_key_here

   # Optional for Google Sign-In:
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```
   Open your browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

---

## 🔑 Google OAuth Setup (Optional)

If you wish to enable **Sign in with Google**:
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and navigate to **APIs & Services > Credentials**.
3. Create an **OAuth 2.0 Client ID** (Application type: *Web application*).
4. Add the following to **Authorized redirect URIs**:
   - `http://127.0.0.1:5000/auth/google/callback`
   - `http://localhost:5000/auth/google/callback`
5. Copy the **Client ID** and **Client Secret** into your `.env` file.

> **Note**: For local development, always access the site via `127.0.0.1:5000` or `localhost:5000`. Google OAuth does not allow arbitrary IP callbacks like `0.0.0.0`.

---

## 🧪 Running Tests

Quizly includes comprehensive test suites covering user authentication, document parsing, quiz generation, and scoring logic:

```bash
# Run all tests
pytest tests/ -v
```

---

## 🔒 Security & Privacy

- **API Keys & Secrets**: All private keys, client IDs, and credentials are strictly stored in `.env` (which is excluded via `.gitignore`).
- **Data Protection**: Passwords are saved using salted cryptographic hashes (`generate_password_hash`).
- **Input Validation**: All CSV and PDF uploads are validated for file size, MIME type, and structure before processing.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check the [issues page](https://github.com/<YOUR_GITHUB_USERNAME>/Quizly/issues) if you want to contribute.
