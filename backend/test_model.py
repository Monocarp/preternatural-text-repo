from sentence_transformers import SentenceTransformer
import os

def load_model():
    MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "bge-large-en-v1.5")
    MODEL_PATH = MODEL_DIR if os.path.exists(MODEL_DIR) else "BAAI/bge-large-en-v1.5"
    print(f"Loading model from: {MODEL_PATH}")
    model = SentenceTransformer(MODEL_PATH)
    print("Model loaded successfully!")
    return model

load_model()