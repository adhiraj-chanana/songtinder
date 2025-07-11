import pandas as pd
from transformers import pipeline

song_data=pd.read_csv('data/spotify_songs.csv')


classified_songs=[]

genre_labels = ["pop", "rock", "hip hop", "electronic", "dance", "indie", 
 "classical", "jazz", "blues", "country", "metal", 
 "reggae", "folk", "acoustic", "instrumental", "latin"]

mood_labels=["happy", "sad", "energetic", "calm", "romantic", 
 "dark", "uplifting", "dreamy", "aggressive", "melancholic", 
 "funky", "chill", "playful", "intense", "mellow"]

classifier = pipeline("zero-shot-classification",
                      model="facebook/bart-large-mnli")
df_shuffled = song_data.sample(frac=1, random_state=42)
for i,row in df_shuffled.iloc[:32].iterrows():
    genre=row['playlist_genre']
    sub_genre=row['playlist_subgenre']
    playlist_name=row['playlist_name']

    sequence_to_classify=f"{genre}, {sub_genre}, {playlist_name}"
    result_genre=classifier(sequence_to_classify, genre_labels)
    result_mood=classifier(sequence_to_classify, mood_labels)
    top_genres = result_genre['labels'][:3]
    top_moods = result_mood['labels'][:3]
    print(top_genres, top_moods)




