from flask import Flask, render_template, request, session
import requests
from dotenv import load_dotenv

import os


client_id = os.environ.get("SPOTIFY_CLIENT_ID")
redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")
scopes = os.environ.get("SPOTIFY_SCOPES")
state = os.environ.get("STATE")
client_secret= os.environ.get("CLIENT_SECRET")

spotify_auth_url="https://accounts.spotify.com/authorize?"+"client_id="+str(client_id)+"&response_type=code&redirect_uri="+str(redirect_uri)+"&scope="+str(scopes)+"&state="+str(state)
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

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
    favsongs=session.get("allsongs", [])
    print("YOUR INTQ!!!\n", index)
    if action=="like":
        #print(session["favsongs"])
        session["likedsongs"].append(session["allsongs"][index-1]["name"])
    else:
        session["dislikedsongs"].append(session["allsongs"][index-1]["name"])
    return render_template("swipe.html", track=session["allsongs"][session["index"]])




