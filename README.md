# 🎯 VictoryAI

An AI-powered autonomous job discovery and application intelligence platform that continuously scans company career portals, ranks opportunities using semantic AI matching, stores results in PostgreSQL, and presents them through a cloud-hosted interactive dashboard.

---
## ✨ Features

* 🔍 Discover jobs from hundreds of ATS platforms

  * Greenhouse
  * Lever
  * Ashby
  * Workday
  * iCIMS
  * SmartRecruiters
  * Generic career pages

* 🤖 AI-powered semantic matching using Sentence Transformers

* 📊 Interactive Streamlit dashboard

* 🗄️ PostgreSQL-backed persistent storage

* ☁️ Cloud deployment with Railway

* 🔄 Automated scheduled job discovery

* 📈 Intelligent relevance scoring

* 💼 Designed for AI, Analytics, Data Science, ML, Product, and Business Analyst roles

---

# System Architecture

```
                GitHub
                   │
                   ▼
            Railway Deployment
          ┌───────────────────┐
          │   Streamlit UI     │
          └─────────┬─────────┘
                    │
                    ▼
             PostgreSQL Database
                    ▲
                    │
          AI Job Discovery Worker
                    │
                    ▼
        Greenhouse • Lever • Ashby
      Workday • iCIMS • SmartRecruiters
         Generic Company Career Pages
```

---

# Technology Stack

* Python
* Streamlit
* PostgreSQL
* Railway
* Sentence Transformers
* HuggingFace Embeddings
* Pandas
* psycopg2
* Tavily Search API
* Azure OpenAI
* GitHub Actions Ready

---

# Dashboard

The dashboard provides:

* Total jobs indexed
* Strong AI matches
* Possible matches
* Search by title
* Search by company
* Search by location
* AI similarity score
* Job descriptions
* Direct application links

---

# AI Matching Pipeline

```
Job Discovery
      │
      ▼
Normalize Jobs
      │
      ▼
Generate Embeddings
      │
      ▼
Semantic Similarity
      │
      ▼
Rank Opportunities
      │
      ▼
Store in PostgreSQL
      │
      ▼
Display on Dashboard
```

---

# Database Tables

* jobs
* jobs_seen
* boards
* workflow_runs

---

# Deployment

VictoryAI is deployed on Railway using:

* Railway Web Service
* Railway PostgreSQL
* Environment Variables
* Scheduled Worker
* Public Dashboard

---

# Future Roadmap

* AI resume tailoring
* AI cover letter generation
* Cold email generation
* LinkedIn outreach generation
* Automatic application tracking
* Daily email summaries
* Cached board discovery
* ATS optimization scoring
* LLM-powered job analysis
* One-click application automation

---

# Installation

```
git clone https://github.com/yourusername/VictoryAI.git

cd VictoryAI

pip install -r requirements.txt

python -m orchestrator.workflow

streamlit run dashboard/app.py
```

---

# Environment Variables

```
DATABASE_URL= *****

TAVILY_API_KEY= *****

AZURE_OPENAI_API_KEY= *****

AZURE_OPENAI_ENDPOINT= *****

AZURE_OPENAI_MODEL= *****
```

---

# Disclaimer

VictoryAI is a personal AI-powered career intelligence platform intended for educational and personal productivity purposes. Users are responsible for complying with the terms of service of job platforms and employer websites when using automated discovery or application workflows.

---

## ⭐ If you found this project interesting, consider starring the repository!
## 🎯 Personalization

VictoryAI is designed to be **fully customizable**.

The repository currently contains a set of **personalized keywords, target roles, and skills** tailored to the developer's own career interests (AI, Data Science, Business Analytics, Machine Learning, Product Analytics, etc.).

Users can easily customize the platform by modifying the profile configuration (or `profile.json`) to match their own preferences.

Examples of customizable fields include:

* 🎯 Target job titles
* 🛠️ Technical skills
* 💼 Preferred industries
* 🌍 Preferred locations
* 📍 Experience level (Intern, New Grad, Senior)
* 🔑 Custom search keywords
* 🧠 AI semantic matching profile
* 🏢 Preferred companies

Once updated, VictoryAI will automatically personalize:

* Job discovery
* Semantic AI matching
* Relevance scoring
* Dashboard recommendations
* Outreach message generation

This allows the same platform to be used by **students, new graduates, experienced professionals, career switchers, and researchers** with only a few configuration changes.

