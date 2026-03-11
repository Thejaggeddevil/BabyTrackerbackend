import os
import pickle
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MODEL_DIR = "models"

datasets = {}
vectorizers = {}
vectors = {}

# simple intent keywords
INTENT_MAP = {
    "sleep": ["sleep", "night", "nap", "wake", "bed"],
    "feeding": ["feed", "milk", "breast", "formula", "eat", "hunger"],
    "development": ["crawl", "walk", "play", "toy", "learn"],
    "health": ["sick", "fever", "cry", "pain"]
}


def detect_intent(text):
    text = text.lower()

    for intent, words in INTENT_MAP.items():
        for w in words:
            if w in text:
                return intent

    return None


def load_models():

    for file in os.listdir(MODEL_DIR):

        if file.endswith(".pkl"):

            name = file.replace(".pkl", "")
            path = os.path.join(MODEL_DIR, file)

            with open(path, "rb") as f:
                df = pickle.load(f)

            datasets[name] = df

            text_data = df.astype(str).agg(" ".join, axis=1)

            vectorizer = TfidfVectorizer(stop_words="english")

            X = vectorizer.fit_transform(text_data)

            vectorizers[name] = vectorizer
            vectors[name] = X


load_models()


def predict(model_name, query):

    if model_name not in datasets:
        return {"error": "Model not found"}

    df = datasets[model_name]

    intent = detect_intent(query)

    # optional domain filtering
    if intent:
        df_filtered = df[df["domain"].str.contains(intent, case=False, na=False)]
        if len(df_filtered) > 0:
            df = df_filtered

    vectorizer = TfidfVectorizer(stop_words="english")
    text_data = df.astype(str).agg(" ".join, axis=1)

    X = vectorizer.fit_transform(text_data)

    query_vec = vectorizer.transform([query])

    similarity = cosine_similarity(query_vec, X)

    best_index = similarity.argmax()

    result = df.iloc[best_index].to_dict()

    return result