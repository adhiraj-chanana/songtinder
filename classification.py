import pandas as pd
from transformers import pipeline
from sentence_transformers import SentenceTransformer
import numpy as  np
import faiss



song_data=pd.read_csv('data/spotify_songs.csv')


classified_songs=[]

genre_labels = ["pop", "rock", "hip hop", "electronic", "dance", "indie", 
 "classical", "jazz", "blues", "country", "metal", 
 "reggae", "folk", "acoustic", "instrumental", "latin"]

mood_labels=["happy", "sad", "energetic", "calm", "romantic", 
 "dark", "uplifting", "dreamy", "aggressive", "melancholic", 
 "funky", "chill", "playful", "intense", "mellow"]


# df_shuffled = song_data.sample(frac=1, random_state=42)
song_info=[]
song_sentences=[]
classifier = pipeline("zero-shot-classification",
                      model="facebook/bart-large-mnli")
for i,row in song_data.iterrows():
    genre=row['playlist_genre']
    sub_genre=row['playlist_subgenre']
    playlist_name=row['playlist_name']

    sequence_to_classify=f"{genre}, {sub_genre}, {playlist_name}"
    result_genre=classifier(sequence_to_classify, genre_labels)
    result_mood=classifier(sequence_to_classify, mood_labels)
    top_genres = result_genre['labels'][:3]
    top_moods = result_mood['labels'][:3]
    tags = top_genres + top_moods
    sentence_to_embed = ", ".join(tags)
    song_sentences.append(sentence_to_embed)
    song_info.append([row["track_name"], row["track_artist"]])

#Embedding the senteces of the songs
model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')
embeddings = model.encode(song_sentences)
print(embeddings.shape)
audio_features=[]
for i,row in song_data.iterrows():
    audio_features.append([row['danceability'], row['energy'], row['key']/11, (row['loudness']+60)/60, row['mode'], row['speechiness'], row['acousticness'], row['instrumentalness'], row['liveness'], row['valence'], row['tempo']])
audio_features=np.array(audio_features,  dtype=np.float32)
combined_vector = np.hstack([embeddings, audio_features])
print(combined_vector.shape)
norms = np.linalg.norm(combined_vector, axis=1, keepdims=True)
normalized_vectors = combined_vector / norms
index = faiss.IndexFlatIP(395)
index.add(normalized_vectors)
print(index.ntotal)
# print(song_sentences)
# print(song_info)








