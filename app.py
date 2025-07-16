from flask import Flask, render_template, request, session
import requests
from dotenv import load_dotenv
from flask_session import Session
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
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
app.config["SESSION_TYPE"] = "filesystem"
spotify_auth_url = "https://accounts.spotify.com/authorize?" + \
    "client_id=" + str(client_id) + \
    "&response_type=code" + \
    "&redirect_uri=" + str(redirect_uri) + \
    "&scope=" + str(scopes) + \
    "&state=" + str(state)

client = genai.Client(api_key=api_key)




Session(app)


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
    session["likedsongs"]=['hello']
    session["dislikedsongs"]=[]
    session["allsongs"]=[]
    session["tags"]=[]

    #print("session_access_token\n", session["access_token"])

    song_url="https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=10"
    auth_header={
    "Authorization": f"Bearer {session["access_token"]}"
    }

    songs = requests.get("https://api.spotify.com/v1/me/top/tracks", headers=auth_header)
    tracks = songs.json()["items"]
    index=0
    k=tracks[index]
    index+=1
    print("THESE ARE THE KEYS!!!!")
    print(k.keys())
    print("trying to get audio features now!")
    for song_dict in tracks:
        #print(song_dict['id'])
        #print(auth_header)
        #print(f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={song_dict['artists'][0]}&track={song_dict['name']}&api_key={last_api_key}&format=json")
        song_audio_tags= requests.get(f"https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&artist={song_dict['artists'][0]['name']}&track={song_dict['name']}&api_key={last_api_key}&format=json")
        if song_audio_tags.status_code == 200:
            # Parse the JSON response
            response_data = song_audio_tags.json()
            #print(f"Full response: {response_data}")
            
            # Check if the response has tags
            if 'toptags' in response_data and 'tag' in response_data['toptags']:
                tags = response_data['toptags']['tag']
                # Extract tag names
                tag_names = []
                for tag in tags:
                    if 'name' in tag:
                        tag_names.append(tag['name'])
                        
                
                print(f"{tag_names[:10]}")

                # Store tags in your song dict
                song_dict['lastfm_tags'] = tag_names
                
            else:
                print(f"No tags found")
                song_dict['lastfm_tags'] = []

    


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
    session['song_data']={}
    song_data={}
    #tracks=list(request.form["allltracks"])
    #print("this is the track", tracks)
    #name=request.form["track"]
    song_index=index-1
    
    tags=session.get("tags",[])
    liked_songs=session.get("likedsongs", [])
    disliked_songs=session.get("dislikedsongs", [])
    #print( "pRINTHIGN ", liked_songs)
    favsongs=session.get("allsongs", [])
    print("this is handle_action",len(favsongs))
    #print("YOUR INTQ!!!\n", index)
    if action=="like":
        #print(session["favsongs"])
        liked_songs.append(favsongs[song_index]["name"])
        song_data[favsongs[song_index]["name"]]={"id": favsongs[song_index]["id"], "artists": favsongs[song_index]["artists"]}
        response = client.models.generate_content(
            model="gemini-1.5-pro-002",
            contents=f"Give me 6 short, comma-separated descriptive tags for the song {favsongs[song_index]["name"]} by {favsongs[song_index]["artists"]}. Focus on mood, genre, tempo, context, and lyrics. done end on period only csv",
        )
        print(favsongs[song_index]["preview_url"])

        print(response.text)
        a=response.text.split()
        if len(tags)>10:
            tags.pop(0)
            tags.append(a)
        else:
            tags.append(a)
        session["tags"]=tags
        #print(tags)
        # vectorizer = TfidfVectorizer()
        # tag_matrix = vectorizer.fit_transform(a)
        # #print(tag_matrix)
        # similarity_matrix = cosine_similarity(tag_matrix)
        # print(similarity_matrix)
        print(len(tags))
        if len(tags)%10==0:
            response2 = client.models.generate_content(
                model="gemini-2.5-pro",
                contents= f"""
                    I will give you music tags. Based only on these tags: {tags}, give me a list of exactly 10 Spotify songs that match these tags.

                    Only output the song titles as a comma-separated list. Do NOT write anything else — no explanations, no numbering.

                    Example format:
                    Song1, Song2, Song3, Song4, Song5, Song6
                    """,
                )
            #print(response2.text)
            c=str(response2.text)
            ab=c.split(", ")
            print(ab)
            access1=session.get("access_token")
            headers2 = {
                "Authorization": f"Bearer {access1}"  # Use a valid token
            }

            
            for song_name in ab:
                song_name_url=song_name.replace(" ", "%20")
                print(song_name_url)
                search_url=f"https://api.spotify.com/v1/search?q={song_name_url}&type=track&limit=1"
                new_song = requests.get(search_url, headers=headers2)
                track = new_song.json()
                favsongs.pop(0)
                favsongs.append(track['tracks']['items'][0])
                session['allsongs']=favsongs
                trial_a=session.get('allsongs', [])
                for i in trial_a:
                    print(i['name'])
        # elif len(tags)>=13:
        #     response2 = client.models.generate_content(
        #         model="gemini-2.0-flash",
        #         contents= f"""
        #             I will give you music tags. Based only on these tags: {tags}, give me a list of exactly 6 Spotify songs that match these tags.

        #             Only output the song titles as a comma-separated list. Do NOT write anything else — no explanations, no numbering.

        #             Example format:
        #             Song1, Song2, Song3, Song4, Song5, Song6
        #             """,
        #         )
        #     c=str(response2.text)
        #     ab=c.split(", ")
        #     print(ab)
       
            #print(response2.text)
        
       
            

       
        

        # try:
        #     print("Error JSON:", song_features.json())
        # except ValueError:
        #     print("Response is not JSON formatted.")
        session['likedsongs']=liked_songs
    else:
        disliked_songs.append(favsongs[song_index]["name"])
        print(disliked_songs)
        session['dislikedsgptongs']=disliked_songs
    if index>=19:
        index=0
    return render_template("swipe.html", track=favsongs[index], index=index+1)


