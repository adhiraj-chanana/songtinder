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
import redis
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
redis_url = os.getenv("REDIS_URL")

if redis_url:
    url = urlparse(redis_url)
    redis_client = redis.Redis(
        host=url.hostname,
        port=url.port,
        password=url.password,
        decode_responses=True
    )
else:
    # Fallback to localhost for local dev
    redis_client = redis.Redis(
        host='localhost',
        port=6379,
        db=0,
        decode_responses=True
    )

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

def get_song_embedding(song_dict, artist_name=None, track_name=None):
    """Extract embedding for a song using Last.fm tags and genre classification"""
    try:
        if artist_name is None:
            artist_name = song_dict['artists'][0]['name']
        if track_name is None:
            track_name = song_dict['name']
            
        print(f"Getting embedding for: {track_name} by {artist_name}")
        
        song_audio_tags = requests.get(
            f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={artist_name}&track={track_name}&api_key={last_api_key}&format=json"
        )
        
        if song_audio_tags.status_code == 200:
            response_data = song_audio_tags.json()
            if 'toptags' in response_data and 'tag' in response_data['toptags']:
                tags = response_data['toptags']['tag']
                raw_tags = [tag['name'].strip().lower() for tag in tags if 'name' in tag]
                
                if raw_tags:  # Only proceed if we have tags
                    sequence = ' '.join(raw_tags)
                    raw_scores = model_cross.predict([(sequence, genre) for genre in GENRES])
                    scores = np.array([score[1] for score in raw_scores])
                    
                    top_indices = scores.argsort()[-5:][::-1]
                    top_genres = [GENRES[i] for i in top_indices]
                    
                    # Create a more natural genre sentence with spaces
                    genre_sentence = ' '.join(top_genres)
                    print(f"Genre sentence: {genre_sentence}")
                    
                    # Get embedding and normalize
                    genre_sentence = genre_sentence.lower().strip()
                    cached_embedding = redis_client.get(f"embedding:{genre_sentence}")

                    if cached_embedding:
                        print("📦 Loaded embedding from Redis cache!")
                        normalized_vectors = np.fromstring(cached_embedding, sep=',').reshape(1, -1)
                    else:
                        print("⚙️  Computing embedding from scratch...")
                        embedding = model.encode([genre_sentence])
                        normalized_vectors = embedding / np.linalg.norm(embedding)
                        redis_client.set(f"embedding:{genre_sentence}", ','.join(map(str, normalized_vectors.flatten())))

                    
                    return normalized_embedding
        
        print(f"No tags found for {track_name}, using default embedding")
        # Return a default embedding if no tags found
        default_embedding = model.encode(["pop music"])[0]
        return default_embedding / np.linalg.norm(default_embedding)
        
    except Exception as e:
        print(f"Error getting embedding for {track_name}: {e}")
        # Return default embedding on error
        default_embedding = model.encode(["pop music"])[0]
        return default_embedding / np.linalg.norm(default_embedding)

def search_spotify_track(track_name, artist_name, auth_header):
    """Search for a track on Spotify and return track info"""
    try:
        print(f"Searching for: {track_name} by {artist_name}")

        track_query = track_name.replace(" ", "%20").replace("&", "%26")
        artist_query = artist_name.replace(" ", "%20").replace("&", "%26")
        cache_key = f"spotify:{track_name.lower()}:{artist_name.lower()}"

        cached = redis_client.get(cache_key)
        if cached:
            print("Loaded from cache")
            data = json.loads(cached)
        else:
            search_url = f"https://api.spotify.com/v1/search?q=track:{track_query}%20artist:{artist_query}&type=track&limit=1"
            response = requests.get(search_url, headers=auth_header)
            data = response.json()

            if data.get("tracks", {}).get("items"):
                redis_client.setex(cache_key, 86400, json.dumps(data))
                print("Cached new result")

        if data.get("tracks", {}).get("items"):
            return data["tracks"]["items"][0]
        else:
            print("No track found")
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None


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
    
    session["access_token"] = token_info["access_token"]
    session["refresh_token"] = token_info["refresh_token"]
    session["likedsongs"]=[]
    session["dislikedsongs"]=[]
    session["allsongs"]=[]
    session["song_embeddings"]=[]
    session["liked_embeddings"]=[]  # New: track only liked song embeddings
    session["user_embedding_sum"]=np.zeros(384).tolist()  # Fixed: proper shape
    session["num_likes"]=0
    session["seen_songs"]=[]
    session["tags"]=[]

    auth_header={
        "Authorization": f"Bearer {session['access_token']}"
    }

    # Get top tracks
    songs = requests.get("https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=10", headers=auth_header)
    tracks = songs.json()["items"]
    
    # Generate embeddings for initial tracks
    embeds = []
    for song_dict in tracks:
        embedding = get_song_embedding(song_dict)
        embeds.append(embedding.tolist())
    
    session['song_embeddings'] = embeds
    session["allsongs"] = tracks
    
    return render_template("swipe.html", track=tracks[0], index=0)

@app.route("/swipe")
def swipe():
    return render_template("swipe.html")

@app.route("/handle_action", methods=["POST"])
def handleaction():
    action = request.form["action"]
    index = int(request.form["index"])
    
    auth_header = {
        "Authorization": f"Bearer {session['access_token']}"
    }
    
    # Get session data
    liked_songs = session.get("likedsongs", [])
    liked_embeddings = session.get("liked_embeddings", [])  # Track liked song embeddings separately
    user_embedding_sum = np.array(session.get("user_embedding_sum"))
    num_likes = session.get("num_likes", 0)
    embeddings_list = session.get("song_embeddings", [])
    disliked_songs = session.get("dislikedsongs", [])
    all_songs = session.get("allsongs", [])
    seen_songs = set(session.get("seen_songs", []))
    
    # Ensure we don't go out of bounds
    if index >= len(all_songs):
        return render_template("swipe.html", track=None, index=index, message="No more songs!")
    
    current_song = all_songs[index]
    current_song_id = current_song.get('id', f"{current_song['name']}_{current_song['artists'][0]['name']}")
    
    if action == "like":
        # Add current song to liked songs
        liked_songs.append(current_song['name'])
        
        # Update user embedding ONLY with the current liked song
        if index < len(embeddings_list):
            current_embedding = np.array(embeddings_list[index])
            
            # Store this embedding in liked_embeddings
            liked_embeddings.append(embeddings_list[index])
            
            # Recalculate user preference from scratch using ONLY liked songs
            if liked_embeddings:
                # Convert all liked embeddings to numpy array
                liked_matrix = np.array(liked_embeddings)
                # Calculate weighted average (recent likes get slightly more weight)
                weights = np.exp(np.linspace(0, 1, len(liked_embeddings)))  # Exponential weighting
                weights = weights / np.sum(weights)  # Normalize weights
                
                # Calculate weighted average
                user_embedding_sum = np.average(liked_matrix, axis=0, weights=weights)
                num_likes = len(liked_embeddings)
            
            print(f"User has liked {num_likes} songs")
            print(f"Current user vector magnitude: {np.linalg.norm(user_embedding_sum)}")
            
            # Generate recommendations after every like (more responsive)
            if num_likes > 0:
                print("Generating new recommendations based on updated preferences...")
                
                # Use the recalculated user preference
                user_vector_normalized = user_embedding_sum / np.linalg.norm(user_embedding_sum)
                
                print(f"User vector preview: {user_vector_normalized[:5]}...")  # Debug print
                
                # Search for similar songs using FAISS with some randomness
                search_k = min(50, len(song_info))  # Get more candidates
                distances, indices = faiss_index.search(
                    user_vector_normalized.reshape(1, -1), 
                    search_k
                )
                
                # Add some randomness to recommendations
                import random
                
                # Take top candidates but with some randomization
                top_candidates = list(zip(indices[0][:25], distances[0][:25]))  # Top 25
                # Sort by similarity but add small random factor
                random_factor = 0.1  # 10% randomness
                weighted_candidates = [(idx, dist + random.uniform(-random_factor, random_factor)) 
                                     for idx, dist in top_candidates]
                weighted_candidates.sort(key=lambda x: x[1])  # Sort by adjusted distance
                
                recommendations_added = 0
                max_recommendations = 6  # Fewer per batch for variety
                
                for idx, _ in weighted_candidates:
                    if recommendations_added >= max_recommendations:
                        break
                        
                    track_name, artist_name = song_info[idx]
                    song_key = f"{track_name}_{artist_name}"
                    
                    # Skip if already seen or in current playlist
                    if song_key in seen_songs:
                        continue
                    
                    # Skip if it's too similar to songs already in the current session
                    skip_song = False
                    for existing_song in all_songs:
                        if (existing_song['name'].lower() == track_name.lower() or 
                            existing_song['artists'][0]['name'].lower() == artist_name.lower()):
                            skip_song = True
                            break
                    
                    if skip_song:
                        continue
                    
                    # Add to seen songs
                    seen_songs.add(song_key)
                    
                    # Search for the song on Spotify
                    spotify_track = search_spotify_track(track_name, artist_name, auth_header)
                    
                    if spotify_track:
                        # Get embedding for the new song
                        new_embedding = get_song_embedding(spotify_track, artist_name, track_name)
                        
                        # Add to our collections
                        all_songs.append(spotify_track)
                        embeddings_list.append(new_embedding.tolist())
                        recommendations_added += 1
                        
                        print(f"Added recommendation: {track_name} by {artist_name}")
                    else:
                        print(f"Could not find {track_name} by {artist_name} on Spotify")
    
    else:  # dislike
        disliked_songs.append(current_song["name"])
        print(f"Disliked: {current_song['name']}")
        
        # Optional: Use dislikes to adjust recommendations (negative feedback)
        # You could subtract disliked embeddings or use them to filter future results
    
    # Update session with ALL the data
    session['likedsongs'] = liked_songs
    session['liked_embeddings'] = liked_embeddings  # New: track liked embeddings separately
    session['dislikedsongs'] = disliked_songs
    session['num_likes'] = num_likes
    session["seen_songs"] = list(seen_songs)
    session["user_embedding_sum"] = user_embedding_sum.tolist()
    session["song_embeddings"] = embeddings_list
    session["allsongs"] = all_songs
    
    # Get next song
    next_index = index + 1
    if next_index < len(all_songs):
        next_track = all_songs[next_index]
        return render_template("swipe.html", track=next_track, index=next_index)
    else:
        # No more songs - could show results or generate more
        return render_template("swipe.html", track=None, index=next_index, message="No more songs available!")

@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)