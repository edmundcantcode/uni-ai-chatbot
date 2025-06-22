
# 🎓 Uni-AI Chatbot

An AI-powered chatbot for university student support — answer queries, predict academic outcomes, and explain decisions using NLP + ML.

---

## 🚀 Features

- 🔍 Natural language query parsing with spaCy + fuzzy logic
- 🎯 Predict student graduation outcomes (CGPA-based)
- 🧠 DeepSeek integration for LLM fallback
- 📊 Cassandra database support (live student & subject data)
- 💬 Chatbot interface via FastAPI
- 🛠 React frontend (planned)

---

## 📂 Project Structure

```
uni-ai-chatbot/
├── backend/
│   ├── main.py
│   ├── chatbot_router.py
│   ├── parse_query.py
│   ├── intent/
│   │   ├── show_students.py
│   │   ├── predict_honors.py
│   └── database/
│       └── connect_cassandra.py
├── data/
│   ├── students.csv
│   ├── subjects.csv
├── models/
│   └── trained_model.pkl
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚙️ Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/edmundcantcode/uni-ai-chatbot.git
cd uni-ai-chatbot
```

### 2. Create and activate virtualenv

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 4. Run the FastAPI backend

```bash
uvicorn backend.main:app --reload
```

---

## ✅ Example Query

> “Show all Chinese male students in Computer Science who failed 2 or more subjects.”

Backend will:
- Parse intent
- Extract filters (gender, race, programme, fail count)
- Run query on Cassandra DB
- Return results in JSON

---

## 🧠 Built With

- Python, FastAPI, spaCy, DeepSeek
- CassandraDB, Pandas
- React (frontend WIP)

---

## 📘 License

MIT – do whatever you want, just don't blame me.
