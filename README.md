# Skinify 🧴

> Skincare recommendations grounded in your skin, not someone else's.

Navigating the skincare market has never been more overwhelming. With thousands of viral trends, ingredients, and products saturating social media, it's easy to spend money on recommendations that simply weren't made for your skin. Influencer favorites and TikTok trends are often tailored to one person's skin, unavailable in the US, or missing context about who they actually work for.

Skinify takes a different approach. Rather than following trends, Skinify centers the user's own experience of their skin through a guided checklist and free-text description of how their skin feels. Skinify uses that input to identify the user's skin type and concerns, then recommends products available at **Sephora**, **Ulta**, and **Olive Young US** by analyzing ingredient lists and how specific ingredients interact with different skin types. Each recommendation comes with a plain-language explanation of why it was suggested, grounded in the user's skin profile.

---

## Features

- **Skin type identification** via quiz (checklist + free-text input)
- **NLP-powered input processing** using sentence-transformers to understand how users naturally describe their skin
- **Ingredient-based recommendations** matched to your skin type using a curated ingredient-to-skin-condition lookup table
- **Plain-language explanations** for every recommendation so you know exactly why a product was suggested
- **Products from Sephora, Ulta, and Olive Young US** — US-available only, no TikTok products you can't find
- **Focused on facial skincare** — recommendations cover face-targeted categories 
including cleansers, moisturizers, serums, toners, sunscreens, masks, and treatments

---

## Tech Stack

| Layer | Technology |
|---|---|
| Back end | FastAPI (Python) |
| Front end | React |
| ML / Classification | scikit-learn |
| NLP | sentence-transformers |
| Deployment | Render (API), Vercel (frontend) |

---

## Project Structure

```
Skinify/
├── scraper/          # Data collection scripts
├── data/             # Raw and cleaned CSVs (not tracked in git)
├── notebooks/        # EDA and model training notebooks
├── models/           # Saved model files (.pkl / .joblib)
├── api/              # FastAPI backend
├── frontend/         # React app
├── docs/             # Roadmap and reference material
└── README.md
```

---

## Data Sources

| Source | Use |
|---|---|
| Olive Young US (scraped) | Product listings + ingredient lists |
| Sephora dataset (Kaggle) | Product listings + ingredient lists |
| Ulta dataset (Kaggle) | Product listings + ingredient lists |
| INCIDecoder / CosDNA | Ingredient function + skin type ratings |
| Paula's Choice Ingredient Dictionary | Ingredient compatibility validation |
| r/SkincareAddiction (Reddit) | How real users describe their skin in plain language |
| Dermatology guides | Skin concern taxonomy + symptom descriptions |

---

## Pipeline Overview

```
User quiz input (checklist + free text)
    → NLP pipeline (sentence-transformers embeddings)
        → Skin type classifier (scikit-learn)
            → Ingredient-based recommendation system
                → LLM generates plain-language explanation
                    → FastAPI returns results to React frontend
```

---

## Roadmap

| Phase | Status |
|---|---|
| Data acquisition (Olive Young scraper) | 🔄 In progress |
| Data acquisition (Sephora + Ulta Kaggle datasets) | ⬜ Upcoming |
| Data cleaning + ingredient mapping | ⬜ Upcoming |
| NLP pipeline | ⬜ Upcoming |
| Skin type classifier | ⬜ Upcoming |
| Recommendation system | ⬜ Upcoming |
| FastAPI backend | ⬜ Upcoming |
| React frontend | ⬜ Upcoming |
| Deployment | ⬜ Upcoming |

---

## Setup

```bash
# Clone the repo
git clone https://github.com/dairalmerino/Skinify.git
cd Skinify

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r scraper/requirements.txt
```

### Run the Olive Young scraper

```bash
python scraper/oliveyoung_scraper.py
```

Output is saved to `data/oliveyoung_skincare.csv`. Progress is checkpointed after every product — safe to interrupt and resume.

---

## Privacy

Skinify does not collect, store, or transmit any personal user data. All skin assessment inputs are processed in memory and discarded after results are returned.

---

## Status

🚧 **Active development** — targeting v1 deployment September 2026

---

*Built by [Daira Merino](https://github.com/dairalmerino) — Cognitive Science (ML & Neural Computation), UC San Diego*
