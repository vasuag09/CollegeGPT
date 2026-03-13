# NM-GPT Demo Script

## 10 Example Questions

| # | Question | Expected Topic |
|---|----------|---------------|
| 1 | What is the minimum attendance requirement? | Attendance policy |
| 2 | What are the rules for exam revaluation? | Examination rules |
| 3 | What happens if I miss an exam due to illness? | Medical leave / exams |
| 4 | What is the grading system used? | Grading policy |
| 5 | What are the rules for internal assessments? | Assessment rules |
| 6 | How do I apply for a leave of absence? | Leave procedures |
| 7 | What is the anti-ragging policy? | Discipline / safety |
| 8 | What are the library rules? | Library policy |
| 9 | What scholarships are available? | Financial aid |
| 10 | What is the code of conduct for students? | Student conduct |

## 2-Minute Demo Flow

### Setup (before demo)
1. Ensure backend is running: `uvicorn backend.app:app --port 8000`
2. Ensure Streamlit is running: `streamlit run streamlit_app/app.py`
3. Open the Streamlit URL in a browser

### Demo Steps (~2 minutes)

**[0:00 – 0:15] Introduction**
> "This is NM-GPT — an AI assistant that answers student questions using the official Student Resource Book."

**[0:15 – 0:45] First Question — Simple Lookup**
- Click "What is the minimum attendance requirement?" from the sidebar
- Point out: the answer, page citations, and confidence score
- Expand the sources panel to show retrieved text

**[0:45 – 1:15] Second Question — Nuanced Policy**
- Type: "What happens if I miss an exam due to illness?"
- Highlight: the answer references specific pages and includes procedural steps

**[1:15 – 1:30] Third Question — Edge Case**
- Type: "Can I bring a pet to campus?"
- Show: the system responds "I could not find this information…" when an answer isn't in the SRB

**[1:30 – 1:50] Architecture Overview**
> "The system works in three steps:
> 1. The SRB is split into chunks and indexed
> 2. When you ask a question, we find the most relevant chunks
> 3. We send those chunks to Google Gemini, which generates a cited answer"

**[1:50 – 2:00] Closing**
> "This prototype runs locally and can scale to include more documents, departments, and campus systems."
