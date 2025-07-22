import pandas as pd

# Load the data
song_data1 = pd.read_csv('data/high_popularity_spotify_data.csv')
song_data2 = pd.read_csv('data/low_popularity_spotify_data.csv')
song_data = pd.concat([song_data1, song_data2], ignore_index=True)

# Extract unique genres and subgenres
unique_genres = sorted(song_data['playlist_genre'].dropna().unique())
unique_subgenres = sorted(song_data['playlist_subgenre'].dropna().unique())

print(unique_genres)

print("-----")
print(unique_subgenres)