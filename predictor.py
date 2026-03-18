import os
import pickle
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL_DIR = "models"

datasets    = {}   # model_name -> DataFrame
vectorizers = {}   # model_name -> TfidfVectorizer (pre-fitted)
vectors     = {}   # model_name -> sparse matrix

# ── Intent keywords for domain filtering ─────────────────────────────────────
INTENT_MAP = {
    "sleep":       ["sleep", "night", "nap", "wake", "bed", "bedtime"],
    "feeding":     ["feed", "milk", "breast", "formula", "eat", "hunger", "latch"],
    "development": ["crawl", "walk", "play", "toy", "learn", "sit", "stand"],
    "health":      ["sick", "fever", "cry", "pain", "hygiene"],
    "safety":      ["safe", "touch", "danger", "stranger", "fire", "electric"],
    "language":    ["word", "speak", "talk", "read", "write", "sentence"],
    "math":        ["count", "number", "add", "subtract", "fraction", "math"],
    "science":     ["plant", "animal", "living", "force", "matter", "science"],
    "social":      ["family", "friend", "community", "share", "emotion"],
}


def detect_intent(text: str):
    text = text.lower()
    for intent, words in INTENT_MAP.items():
        for w in words:
            if w in text:
                return intent
    return None


def load_models():
    """Load all .pkl files at startup — called once."""
    if not os.path.exists(MODEL_DIR):
        print(f"⚠️  models/ directory not found")
        return

    for file in os.listdir(MODEL_DIR):
        if not file.endswith(".pkl"):
            continue

        name = file.replace(".pkl", "")
        path = os.path.join(MODEL_DIR, file)

        try:
            with open(path, "rb") as f:
                df = pickle.load(f)

            if not isinstance(df, pd.DataFrame) or df.empty:
                print(f"⚠️  Skipping {name}: not a valid DataFrame")
                continue

            datasets[name] = df

            # Pre-build TF-IDF vectors at startup — fast path for every request
            text_data = df.astype(str).agg(" ".join, axis=1)
            vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
            X = vectorizer.fit_transform(text_data)

            vectorizers[name] = vectorizer
            vectors[name]     = X

            print(f"✅ Loaded: {name} ({len(df)} rows)")

        except Exception as e:
            print(f"❌ Failed to load {name}: {e}")


load_models()


def predict(model_name: str, query: str) -> dict:
    """
    Find the best matching row for `query` in `model_name`.

    Model name must match one of the .pkl file names (without .pkl).
    If the model is not found, returns {"error": "..."}.
    """

    # ── Model lookup ──────────────────────────────────────────────────────────
    if model_name not in datasets:
        # Try fallback to parent_0_24 for any unknown model name
        if "parent_0_24" in datasets:
            model_name = "parent_0_24"
        else:
            return {"error": f"Model '{model_name}' not found. Available: {list(datasets.keys())}"}

    df         = datasets[model_name]
    vectorizer = vectorizers[model_name]
    X          = vectors[model_name]

    # ── Optional domain filtering ─────────────────────────────────────────────
    intent = detect_intent(query)
    if intent and "domain" in df.columns:
        df_filtered = df[df["domain"].str.contains(intent, case=False, na=False)]
        if len(df_filtered) >= 5:
            # Refit on filtered subset only
            text_filtered = df_filtered.astype(str).agg(" ".join, axis=1)
            vec_filtered  = TfidfVectorizer(stop_words="english", max_features=5000)
            X_filtered    = vec_filtered.fit_transform(text_filtered)
            query_vec     = vec_filtered.transform([query])
            similarity    = cosine_similarity(query_vec, X_filtered)
            best_index    = similarity.argmax()
            return df_filtered.iloc[best_index].to_dict()

    # ── Use pre-built vectorizer (fast path) ──────────────────────────────────
    query_vec  = vectorizer.transform([query])
    similarity = cosine_similarity(query_vec, X)
    best_index = similarity.argmax()

    return df.iloc[best_index].to_dict()
