from flask import Flask, render_template, request, session
import requests
from dotenv import load_dotenv
from flask_session import Session
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
from transformers import pipeline
from sentence_transformers import SentenceTransformer
from sentence_transformers import CrossEncoder
import numpy as np
import faiss
import json
load_dotenv()


app = Flask(__name__)
client_id = os.environ.get("SPOTIFY_CLIENT_ID")
redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")
scopes = os.environ.get("SPOTIFY_SCOPES")
state = os.environ.get("STATE")
client_secret= os.environ.get("CLIENT_SECRET")
app.secret_key = os.environ.get("SECRET_KEY") or "fwbefwiejdiuebfibefib"
api_key=os.environ.get("API_KEY")
last_api_key=os.environ.get("LAST_FM_API")

faiss_index = faiss.read_index("similarity_search/song_index.faiss")
with open("similarity_search/song_info.json", "r") as f:
    song_info = json.load(f)
app.config["SESSION_TYPE"] = "filesystem"
spotify_auth_url = "https://accounts.spotify.com/authorize?" + \
    "client_id=" + str(client_id) + \
    "&response_type=code" + \
    "&redirect_uri=" + str(redirect_uri) + \
    "&scope=" + str(scopes) + \
    "&state=" + str(state)

client = genai.Client(api_key=api_key)

model_cross= CrossEncoder('cross-encoder/nli-distilroberta-base')
model = SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2')

Session(app)
genre_tags=['afrobeats', 'ambient', 'arabic', 'blues', 'brazilian', 'cantopop', 'classical', 'country', 'disco', 'electronic', 'folk', 'funk', 'gaming', 'gospel', 'hip-hop', 'indian', 'indie', 'j-pop', 'jazz', 'k-pop', 'korean', 'latin', 'lofi', 'mandopop', 'metal', 'pop', 'punk', 'r&b', 'reggae', 'rock', 'soca', 'soul', 'turkish', 'wellness', 'world']
subgenre_tags=['80s', '90s', 'academic', 'african', 'afro house', 'afro-latin', 'alternative', 'amapiano', 'american', 'anime', 'australian', 'avant-garde', 'bedroom', 'bhangra', 'bollywood', 'cajun', 'carnival', 'celtic', 'chill', 'chinese', 'choral', 'cinematic', 'classic', 'classical', 'cumbia', 'death', 'deep house', 'delta', 'desi', 'drama', 'drill', 'essential', 'experimental', 'feel-good', 'forró', 'french', 'funk', 'fusion', 'future', 'future bass', 'gangster', 'global', 'gqom', 'grime', 'hardstyle', 'heavy', 'hip-hop', 'indie', 'indigenous', 'irish', 'italo', 'japanese', 'jewish', 'klezmer', 'latin', 'mainstream', 'meditative', 'melodic', 'modern', 'neo-classical', 'nigerian', 'noir', 'nordic', 'pop', 'pop punk', 'post-rock', 'reggaeton', 'retro', 'samba', 'scandi', 'smooth', 'soft', 'soundtracks', 'southern', 'spanish', 'tango', 'techno', 'throat singing', 'throwback', 'trap', 'tropical', 'vaporwave', 'workout', 'yoga']

GENRES = [tag.lower() for tag in genre_tags + subgenre_tags]

@app.route("/")
def login():
    return render_template("login.html", spotify_auth_url=spotify_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    token_url="https://accounts.spotify.com/api/token"
    payload={
        "grant_type":"authorization_code",
        "code":code,
        "redirect_uri":redirect_uri,
        "client_id":client_id,
        "client_secret":client_secret
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(token_url, data=payload, headers=headers)
    token_info=response.json()
    #print("token\n", token_info )
    session["access_token"] = token_info["access_token"]
    session["refresh_token"] = token_info["refresh_token"]
    session["likedsongs"]=[]
    session["dislikedsongs"]=[]
    session["allsongs"]=[]
    session["song_embeddings"]=[]
    session["user_embedding_sum"]=np.zeros((1,384))
    session["num_likes"]=0
    session["seen_songs"]=[]
    session["tags"]=[]

    #print("session_access_token\n", session["access_token"])

    song_url="https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=10"
    auth_header={
    "Authorization": f"Bearer {session["access_token"]}"
    }

    songs = requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=10", headers=auth_header)
    tracks = songs.json()["items"]
    index=0
    song_recs=set()
    k=tracks[index]
    print("THESE ARE THE KEYS!!!!")
    print(k.keys())
    print("trying to get audio features now!")
    similar_Songs=[]
    
    COMMON_TAGS = {
    "music", "song", "songs", "favorite", "favorites", "spotify", "myspotigrambot",
    "2020", "2021", "2022", "2023", "2024", "new", "old", "top", "hits", "artist", "track"
}
    
    embeds=[]
    for song_dict in tracks:
        #print(song_dict['id'])
        #print(auth_header)
        print(song_dict['name'])
        #print(f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={song_dict['artists'][0]}&track={song_dict['name']}&api_key={last_api_key}&format=json")
        song_audio_tags= requests.get(f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={song_dict['artists'][0]['name']}&track={song_dict['name']}&api_key={last_api_key}&format=json")
        if song_audio_tags.status_code == 200:
            # Parse the JSON response
            response_data = song_audio_tags.json()
            #print(f"Full response: {response_data}")
            if 'toptags' in response_data and 'tag' in response_data['toptags']:
                tags = response_data['toptags']['tag']
                raw_tags = [tag['name'].strip().lower() for tag in tags if 'name' in tag]

                # Filter tags

                # Optional: remove duplicates
                sequence = ' '.join(raw_tags)
                raw_scores = model_cross.predict([(sequence, genre) for genre in GENRES])
                scores = np.array([score[1] for score in raw_scores])  # take probability for label=1

                top_indices = scores.argsort()[-5:][::-1]
                top_genres = [(GENRES[i], scores[i]) for i in top_indices]

                genre_sentence = f"{top_genres[0][0]} {top_genres[1][0]} {top_genres[2][0]}{top_genres[3][0]}{top_genres[4][0]}"
                print(genre_sentence)
                # Format the genres into a sentence
                embeddings = model.encode([genre_sentence]) 
                print("Embedding shape:", embeddings.shape)
                normalized_vectors = embeddings / np.linalg.norm(embeddings)
                embeds.append(normalized_vectors)
                #distances, indices = faiss_index.search(normalized_vectors, 5)
                #for idx, dist in zip(indices[0], distances[0]):
                 #   track_name, artist_name = song_info[idx]
                 #   print(f"{track_name} by {artist_name} (Score: {dist:.4f})")
                  # song_recs.add((track_name,artist_name))
            # else:
            #     print(f"No tags found for {track_name}")
            #     song_dict['lastfm_tags'] = []
    session['song_embeddings']=embeds
    new_tracks=[]
    # for song_name,artist in song_recs:
    #     song_name_url=song_name.replace(" ", "%20")
    #     print(song_name_url)
    #     search_url=f"https://api.spotify.com/v1/search?q={song_name_url}&type=track&limit=1"
    #     new_song = requests.get(search_url, headers=auth_header)
    #     track = new_song.json()
    #     new_tracks.append(track['tracks']['items'][0])

    #print(i.keys())
    #for i in tracks:
    session["allsongs"]=tracks
    #print(session["favsongs"s])
    #print(session["favsongs"])
    #print("RECIEVED SONGS!!!\n", songs_info)
    #print("this is your code\n",code)
    return render_template("swipe.html", track=k, index=index)



@app.route("/swipe")
def swipe():
    return render_template("swipe.html")

@app.route("/handle_action", methods=["POST"])
def handleaction():
    action=request.form["action"]
    index=int(request.form["index"])
    auth_header={
    "Authorization": f"Bearer {session["access_token"]}"
    }
    liked_songs=session.get("likedsongs", [])
    user_embedding_sum = np.array(session.get("user_embedding_sum")).reshape(-1)
    numlikes=session.get("num_likes",0)
    embeddings_matrix = np.vstack(session.get("song_embeddings"))
    disliked_songs=session.get("dislikedsongs", [])
    all_songs=session.get("allsongs", [])
    seen = set(session.get("seen_songs", []))
    if action=="like":
        current_embedding = session["song_embeddings"][index]
        current_embedding = np.array(session["song_embeddings"][index]).reshape(-1)
        user_embedding_sum += current_embedding
        numlikes+=1
        print(numlikes)
        liked_songs.append(all_songs[index]['name'])

        if numlikes%5==0:
            #searching with 5 liked songs with faiss to get 10 recommendations
            user_vector = user_embedding_sum / numlikes
            normal_embedded_sum=user_vector / np.linalg.norm(user_vector)
            distances, indices = faiss_index.search(normal_embedded_sum.reshape(1, -1), 10)

            for idx, dist in zip(indices[0], distances[0]):
                track_name, artist_name = song_info[idx]
                print(f"{track_name} by {artist_name} (Score: {dist:.4f})")
                if (track_name,artist_name) not in seen:
                    seen.add((track_name, artist_name))
                else:
                    continue
                song_name_url=track_name.replace(" ", "%20")
                search_url=f"https://api.spotify.com/v1/search?q={song_name_url}&type=track&limit=1"
                new_song = requests.get(search_url, headers=auth_header)
                track = new_song.json()
                all_songs.append(track['tracks']['items'][0])
                song_audio_tags= requests.get(f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist_name}&track={track_name}&api_key={last_api_key}&format=json")
                if song_audio_tags.status_code == 200:
                    # Parse the JSON response
                    response_data = song_audio_tags.json()
                    if 'toptags' in response_data and 'tag' in response_data['toptags']:
                        tags = response_data['toptags']['tag']
                        raw_tags = [tag['name'].strip().lower() for tag in tags if 'name' in tag]
                        sequence = ' '.join(raw_tags)
                        raw_scores = model_cross.predict([(sequence, genre) for genre in GENRES])
                        scores = np.array([score[1] for score in raw_scores])  # take probability for label=1
                        top_indices = scores.argsort()[-5:][::-1]
                        top_genres = [(GENRES[i], scores[i]) for i in top_indices]
                        genre_sentence = f"{top_genres[0][0]} {top_genres[1][0]} {top_genres[2][0]}{top_genres[3][0]}{top_genres[4][0]}"
                        # Format the genres into a sentence
                        embedding = model.encode([genre_sentence])[0]
                        normalized_vectors = embedding / np.linalg.norm(embedding)
                        normalized_embedding = normalized_vectors.reshape(-1)
                        embeddings_matrix = np.vstack([embeddings_matrix, normalized_embedding])
    else:
        disliked_songs.append(all_songs[index]["name"])
        print(disliked_songs)
        session['dislikedsongs']=disliked_songs
    session['num_likes']=numlikes
    session["seen_songs"] = list(seen)
    session["user_embedding_sum"] = user_embedding_sum.tolist()
    session["song_embeddings"] = embeddings_matrix.tolist()
    session["allsongs"]=all_songs
    return render_template("swipe.html", track=all_songs[index], index=index+1)


