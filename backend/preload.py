from sentence_transformers import SentenceTransformer
import torch

# Pre-load the model during build to cache it and reduce startup RAM on Render
MODEL_PATH = "BAAI/bge-large-en-v1.5"  # Match utils.py

print("Pre-loading model...")
model = SentenceTransformer(MODEL_PATH, model_kwargs={'device': 'cpu', 'torch_dtype': torch.float16})
print("Model pre-loaded successfully!")
