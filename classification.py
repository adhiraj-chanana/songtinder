import pandas as pd
from transformers import pipeline
from sentence_transformers import SentenceTransformer
import numpy as  np
import faiss
import torch
import json
import matplotlib.pyplot as plt


song_data=pd.read_csv('data/spotify_songs.csv')
# Frequency of genres
# Playlist Genre


classified_songs=[]

genre_labels = ["pop", "rock", "hip hop", "electronic", "dance", "indie", 
 "classical", "jazz", "blues", "country", "metal", 
 "reggae", "folk", "acoustic", "instrumental", "latin"]

mood_labels=["happy", "sad", "energetic", "calm", "romantic", 
 "dark", "uplifting", "dreamy", "aggressive", "melancholic", 
 "funky", "chill", "playful", "intense", "mellow"]

all_labels=genre_labels+mood_labels

# df_shuffled = song_data.sample(frac=1, random_state=42)
song_info=[]
song_sentences=[]
# #classifier = pipeline(
#     "zero-shot-classification",
#     model="valhalla/distilbart-mnli-12-1",
#     device=0 
# )


batch_size = 16
batch_sequence=[]
batch_info=[]
c=0

for i,row in song_data.iterrows():
    genre=row['playlist_genre']
    sub_genre=row['playlist_subgenre']
    playlist_name=row['playlist_name']
    sequence_to_classify=f"{genre}, {sub_genre}"
    batch_sequence.append(sequence_to_classify)
    batch_info.append([row["track_name"], row["track_artist"]])
    if len(batch_sequence) == batch_size:
        #results = classifier(batch_sequence, all_labels)
        for result, info in zip(batch_sequence, batch_info):
          #  tags = result['labels'][:4]
          #  sentence_to_embed = ", ".join(tags)
            song_sentences.append(result)
            song_info.append(info)
        batch_sequence = []
        batch_sequence = []
        print("batch" ,c )
        c+=1
print(len(song_sentences))
print(len(song_info))
if len(batch_sequence) > 0:
    #esults = classifier(batch_sequence, all_labels)
    for result, info in zip(batch_sequence, batch_info):
        # tags = result['labels'][:4]
        # sentence_to_embed = ", ".join(tags)
        song_sentences.append(result)
        song_info.append(info)

#Embedding the senteces of the songs
model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
embeddings = model.encode(song_sentences)
print(embeddings.shape)
audio_features=[]
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
normalized_vectors = embeddings / norms
index = faiss.IndexFlatIP(384)
index.add(normalized_vectors)
faiss.write_index(index, "song_index.faiss")

print("✅ Saved FAISS index to song_index.faiss")
with open("song_info.json", "w") as f:
    json.dump(song_info, f)
print("✅ Saved song info to song_info.json")
# print(song_sentences)
# print(song_info)








