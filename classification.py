import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import json

# Load song data
song_data1 = pd.read_csv('data/high_popularity_spotify_data.csv')
song_data2 = pd.read_csv('data/low_popularity_spotify_data.csv')
song_data = pd.concat([song_data1, song_data2], ignore_index=True)

# Labels (optional — currently not used)
genre_labels = ["pop", "rock", "hip hop", "electronic", "dance", "indie", 
 "classical", "jazz", "blues", "country", "metal", 
 "reggae", "folk", "acoustic", "instrumental", "latin"]

mood_labels = ["happy", "sad", "energetic", "calm", "romantic", 
 "dark", "uplifting", "dreamy", "aggressive", "melancholic", 
 "funky", "chill", "playful", "intense", "mellow"]

# Storage for sentences and metadata
song_sentences = []
song_info = []

for _, row in song_data.iterrows():
    genre = row['playlist_genre']
    sub_genre = row['playlist_subgenre']
    sentence = f"{genre}, {sub_genre}"  # Simple sentence for embedding
    song_sentences.append(sentence)
    song_info.append([row["track_name"], row["track_artist"]])

print(f"✅ Processed {len(song_sentences)} songs.")

# Embed the genre/subgenre sentences
model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
embeddings = model.encode(song_sentences, batch_size=64, show_progress_bar=True)

# Normalize embeddings
normalized_vectors = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

# Build FAISS index
index = faiss.IndexFlatIP(normalized_vectors.shape[1])
index.add(normalized_vectors)
faiss.write_index(index, "song_index.faiss")
print("✅ Saved FAISS index to song_index.faiss")

# Save song info (track name + artist)
with open("song_info.json", "w") as f:
    json.dump(song_info, f)
print("✅ Saved song info to song_info.json")

# Final sanity check
assert len(song_info) == normalized_vectors.shape[0], "Mismatch between embeddings and metadata"
