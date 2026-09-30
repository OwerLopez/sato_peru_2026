import json
import time

import requests

refs = [
    "Gondia Siam El-Dakhakhni Nassar Machine learning algorithms for construction projects delay risk prediction",
    "Egwim Alaka Toriola-Coker Balogun Sunmola Applied artificial intelligence for predicting construction projects delay",
    "Assaf Al-Hejji Causes of delay in large construction projects",
    "Gallego Rivero Martinez Preventing rather than punishing: An early warning model of malfeasance in public procurement",
    "Decarolis Giuffrida Iossa Mollisi Spagnolo Bureaucratic competence and procurement outcomes",
    "Bajari Houghton Tadelis Bidding for incomplete contracts: an empirical analysis of adaptation costs",
    "Flyvbjerg What you should know about megaprojects and why: an overview",
    "Kaufman Rosset Perlich Stitelman Leakage in data mining: formulation, detection, and avoidance",
    "Saito Rehmsmeier The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets",
    "Lundberg Lee A unified approach to interpreting model predictions",
    "Lundberg Erion Chen From local explanations to global understanding with explainable AI for trees",
    "Ke Meng Finley LightGBM: a highly efficient gradient boosting decision tree",
    "Reimers Gurevych Sentence-BERT: sentence embeddings using siamese BERT-networks",
    "Reimers Gurevych Making monolingual sentence embeddings multilingual using knowledge distillation",
    "Canete Chaperon Fuentes Ho Kang Perez Spanish pre-trained BERT model and evaluation data",
    "Zhang Tixier construction site accident analysis using text mining and natural language processing techniques",
    "Tixier Hallowell Rajagopalan Bowman Automated content analysis for construction safety: a natural language processing system",
    "Cerqueira Torgo Mozetic Evaluating time series forecasting models: an empirical study on performance estimation methods",
    "Fazekas Kocsis Uncovering high-level corruption: cross-national objective corruption risk indicators using public procurement data",
    "Sambasivan Soon Causes and effects of delays in Malaysian construction industry",
    "Niculescu-Mizil Caruana Predicting good probabilities with supervised learning",
    "Chen Guestrin XGBoost: a scalable tree boosting system",
    "Roberts Bergmeir cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure",
    "Sanni-Anibire Zin Olatunji Machine learning model for delay risk assessment in tall building projects",
]
out = []
for q in refs:
    for attempt in range(6):
        try:
            r = requests.get(
                "https://api.crossref.org/works",
                params={"query.bibliographic": q, "rows": 2, "select": "DOI,title,container-title,issued,author,type"},
                headers={"User-Agent": "SATO-AQP thesis research"},
                timeout=60,
            ).json()
            break
        except Exception:
            time.sleep(3 * (attempt + 1))
    it = r["message"]["items"][0]
    t = it.get("title", [""])[0]
    c = (it.get("container-title") or [""])[0]
    y = it.get("issued", {}).get("date-parts", [[None]])[0][0]
    a = ", ".join(x.get("family", "") for x in it.get("author", [])[:4])
    out.append({"query": q, "title": t, "authors": a, "year": y, "venue": c, "doi": it["DOI"], "type": it.get("type")})
    print(f"{y} | {a} | {t[:110]} | {c[:60]} | {it['DOI']}")
    time.sleep(0.5)
json.dump(out, open("docs/research/references_crossref.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
