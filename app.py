import os
from dotenv import load_dotenv
import json
from functools import wraps
from datetime import datetime
import random
import math

from flask import *

from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import requests
from pip._vendor import cachecontrol

import firebase_admin
from firebase_admin import credentials, firestore

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth
from spotipy import *

class FirestoreCacheHandler(spotipy.cache_handler.CacheHandler):
    """A custom cache handler that stores Spotify token info in a firestore database using the current user logged into the flask session."""

    def __init__(self, db, session):
        self.db = db
        self.session = session

    def get_cached_token(self):
        token_info = None
        try:
            doc = self.db.collection("users").document(self.session["google_id"]["sub"]).get()
            if doc.exists:
                # Retrieve the token_info dictionary from Firestore
                token_info = doc.to_dict().get('spotify_token')
        except Exception as e:
            print(f"Error retrieving token from Firestore: {e}")
        return token_info

    def save_token_to_cache(self, token_info):
        try:
            # Save the full token_info
            self.db.collection("users").document(self.session["google_id"]["sub"]).set({'spotify_token': token_info}, merge=True)
        except Exception as e:
            print(f"Error saving token to Firestore: {e}")

def login_required(function):
    """A decorator function that checks if the user is logged in before allowing access to certain routes"""

    @wraps(function)
    def wrapper(*args, **kwargs):
        if "sub" not in session.get("google_id", {}):
            return redirect("/")
        else:
            return function()

    return wrapper

def get_playlist(playlists, playlist_id):
    """Helper function to find the requested playlist item from a list of the user's playlists returned from Spotify's API"""

    for playlist in playlists['items']:
        if playlist['id'] == playlist_id:
            return playlist
    return None

def hybrid_shuffle_softplus(songs, scale=1, temperature=0.5):
    """
    Uses softplus and log transformations to shuffle a list of songs using their net votes

    :param scale: factor to scale votes by (default=1)
    :param temperature: scales how much randomness affects the final list (lower=less shuffled)
    """

    for i in range(len(songs)):
        songs[i] = songs[i].to_dict()
        songs[i]["net"] = songs[i]["upvotes"] - songs[i]["downvotes"]

    def weighted_key(song):
        scaled_net = song["net"] / scale
        x = math.log1p(math.exp(scaled_net))  # softplus: log(1 / 1+e^scaled_net)
        weight = max(x, 1e-6)
        noise = math.log(random.random())
        return noise / (weight * temperature)

    return sorted(songs, key=weighted_key, reverse=True)

def sort_by_votes(songs):
    """Sorts songs purely by their net votes"""
    
    for i in range(len(songs)):
        songs[i] = songs[i].to_dict()
        songs[i]["net"] = songs[i]["upvotes"] - songs[i]["downvotes"]
    return sorted(songs, key=lambda x: x["net"], reverse=True)

load_dotenv()

# Flask app setup
project_root = os.path.dirname(os.path.realpath('__file__'))
static_path = os.path.join(project_root, 'static')
app = Flask(__name__, static_folder=static_path)
app.secret_key = os.getenv("APP_SECRET_KEY")

# Google OAuth setup
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # TODO: REMOVE THIS WHEN YOU DEPLOY
flow = Flow.from_client_secrets_file(  
	client_secrets_file="oauth.json",
	scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],  
	redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
)

# Initialize Firebase Admin SDK
cred = credentials.Certificate("cred.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Spotify OAuth setup
sp_cache_handler = FirestoreCacheHandler(db, session)
sp_oauth = SpotifyOAuth(client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
                        scope=os.getenv("SPOTIPY_SCOPE"),
                        cache_handler=sp_cache_handler,
                        show_dialog=True)

# Root Endpoint
@app.route("/", methods=["GET"]) # Login Page
def root():
    if "sub" in session.get("google_id", {}): # Redirect to app if logged in
        return redirect("/app")
    
    response = make_response(render_template("index.html"))
    return response

# App Endpoints
@app.route("/app", methods=["GET"]) # Main app page
@login_required
def main_app():
    user_playlists = {}
    current_playlist = {}
    current_playlist_exists = None
    devices = None

    token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
    if token_info:
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_playlists = sp.current_user_playlists()
        current_playlist_id = request.args.get('playlist-id')

        for playlist in user_playlists["items"]:
            playlist_ref = db.collection('playlists').document(playlist["id"])
            playlist["exists"] = playlist_ref.get().exists
            if current_playlist_id == playlist["id"]:
                current_playlist_exists = playlist["exists"]
                current_playlist = playlist

        devices = sp.devices()["devices"]

    visited = request.cookies.get("visited_today")
    response = make_response(render_template("app.html", session=session, user_playlists=user_playlists, current_playlist=current_playlist, current_playlist_exists=current_playlist_exists, devices=devices, shuffle_state=session.get("shuffle_state"), show_popup=(visited == None)))
    if visited is None:
        response.set_cookie("visited_today", "true", max_age=60*60*12) # show popup once per 12 hours
    return response

@app.route("/songs", methods=["GET"]) # Get playlist songs and the user's votes
@login_required
def songs():
    if 'playlist-id' in request.args:
        token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
        if token_info:
            playlist_id = request.args.get('playlist-id')
            sp = spotipy.Spotify(auth=token_info['access_token'])
            playlist = sp.playlist(playlist_id)
            songs_list = []  
            song_ids = set()            
            for track in playlist['items']['items']:
                if track["item"] == None: continue  # Skip broken songs
                id = track["item"]["id"]
                track_name = track["item"]["name"]
                track_artist = track["item"]["artists"][0]["name"]
                track_album = track["item"]["album"]["name"]
                cover_url = track["item"]["album"]["images"][0]["url"]
                explicit = track["item"]["explicit"]
                uri = track["item"]["uri"]
                songs_list.append({"uri": uri, "id": id, "name": track_name, "artist": track_artist, "album": track_album, "cover_url": cover_url, "added_at": track["added_at"], "explicit": explicit})
                song_ids.add(id)

            playlist_ref = db.collection('playlists').document(playlist_id)
            songs_ref = playlist_ref.collection('songs')
            for song in songs_list:
                song_doc = songs_ref.document(song["id"]).get()
                if song_doc.exists:
                    data = song_doc.to_dict()
                    if session["google_id"]["sub"] in data["upvote_subs"]:
                        song["vote"] = 1
                    elif session["google_id"]["sub"] in data["downvote_subs"]:
                        song["vote"] = -1
                    else:
                        song["vote"] = 0

                    song["add_profile_picture"] = data["add_profile_picture"]
                    song["add_user_name"] = data["add_user_name"]
                    song["added_at"] = data["added_at"].timestamp()
                    song["user_added"] = (data["add_sub"] == session["google_id"]["sub"]) or (data["add_sub"] == "")
                    song["net_votes"] = data["upvotes"] - data["downvotes"]
                else:
                    playlist_ref.update({"length": firestore.Increment(1), "song_ids": firestore.ArrayUnion([song["id"]])})
                    added_date = datetime.fromisoformat(song["added_at"].replace("Z", "+00:00"))
                    songs_ref.document(song["id"]).set({"song_uri": song["uri"], "song_name": song["name"], "song_artist": song["artist"], "upvotes": 0, "upvote_subs": [], "downvotes": 0, "downvote_subs": [], "added_at": added_date, "add_sub": "", "add_user_name": "", "add_profile_picture": ""})
                    song["vote"] = 0
                    song["added_at"] = added_date.timestamp()
                    song["user_added"] = True
                    song["net_votes"] = 0

            db_song_ids = set(playlist_ref.get().to_dict()["song_ids"])
            diff = db_song_ids - song_ids
            if diff:  # Delete songs not in spotify playlist
                for id in diff:
                    songs_ref.document(id).delete()
                    playlist_ref.update({"length": firestore.Increment(-1), "song_ids": firestore.ArrayRemove([id])})
                    
            return jsonify(songs_list), 200
        
        return jsonify({"message": "Unable to update Spotify token"}), 401
    return jsonify({"message": "Missing playlist-id query"}), 400

@app.route("/create-playlist", methods=["POST"]) # Create playlist in database
@login_required
def create_playlist():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data.get("playlist_id")
        if "playlist_name" in data:
            playlist_name = data.get("playlist_name")
            playlist_ref = db.collection("playlists").document(playlist_id)
            if not playlist_ref.get().exists:
                playlist_ref.set({"playlist_name": playlist_name, "date_created": firestore.SERVER_TIMESTAMP, "length": 0, "song_ids": []})
                return jsonify({"message": "Playlist created"}), 200
            return jsonify({"message": "Playlist already created"}), 200
        return jsonify({"message": "Missing playlist_name field"}), 400
    return jsonify({"message": "Missing playlist_id field"}), 400

@app.route('/search', methods=["GET"]) # Song search
def search():
    if "q" in request.args:
        try:
            sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
            results = sp.search(request.args.get('q'), 10)['tracks']['items']
            song_data = {}
            for i in range(len(results)):
                song = {}
                song["id"] = results[i]['id']
                song["cover_img"] = results[i]['album']['images'][0]['url']
                song["name"] = results[i]['name']
                song["artist"] = results[i]['album']['artists'][0]['name']
                song["explicit"] = results[i]['explicit']
                song_data[song["id"]] = song
            return json.dumps(song_data), 200
        except Exception as e:
            print("Error during spotify song search: ", e)
            return jsonify({"message": "An error occurred during search"}), 500
    return jsonify({"message": "Missing search query (q)"}), 400

@app.route('/add', methods=["POST"]) # Add song to playlist
@login_required
def add():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data['playlist_id']
        if "track_id" in data:
            track_id = data['track_id']
            token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
            if token_info:
                sp = spotipy.Spotify(auth=token_info['access_token'])
                track_info = sp.track(track_id)

                song_name = track_info['name']
                song_artist = track_info['artists'][0]['name']
                song_album = track_info['album']['name']
                cover_url = track_info['album']['images'][0]['url']
                explicit = track_info['explicit']
                song_uri = track_info['uri']

                playlist_ref = db.collection('playlists').document(playlist_id)
                song_ref = playlist_ref.collection('songs').document(track_id)
                if not song_ref.get().exists: # Add song if not already in database
                    song_ref.set({
                        "song_uri": song_uri,
                        "song_name": song_name,
                        "song_artist": song_artist,
                        "upvotes": 0, "upvote_subs": [],
                        "downvotes": 0, "downvote_subs": [],
                        "added_at": firestore.SERVER_TIMESTAMP,
                        "add_sub": session["google_id"]["sub"],
                        "add_user_name": session["google_id"]["name"],
                        "add_profile_picture": session["google_id"]["picture"]
                    })

                    playlist_ref.update({"length": firestore.Increment(1), "song_ids": firestore.ArrayUnion([track_id])})
                    playlist_length = playlist_ref.get().to_dict().get("length")
                    sp.playlist_add_items(playlist_id, [track_id])

                    # Return song data needed to create a song div
                    return jsonify({
                        "message": "Song added to playlist", 
                            "song_data": {
                                "playlist_id": playlist_id, 
                                "id": track_id, "number": playlist_length, 
                                "name": song_name, "artist": song_artist, 
                                "album": song_album, "cover_url": cover_url, 
                                "added_at": song_ref.get().to_dict().get("added_at").timestamp(),
                                "explicit": explicit,
                                "user_added": True,
                                "add_user_name": session["google_id"]["name"],
                                "add_profile_picture": session["google_id"]["picture"],
                                "net_votes": 0
                            }
                        }), 200

                return jsonify({"message": "Song already added to playlist"}), 200
            return jsonify({"message": "Unable to update Spotify token"}), 401
        return jsonify({"message": "Missing track_id"}), 400
    return jsonify({"message": "Missing playlist_id"}), 400

@app.route('/upvote', methods=["POST"]) # Upvote a song
def upvote():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data['playlist_id']
        if "track_id" in data:
            track_id = data['track_id']
            songs_ref = db.collection('playlists').document(playlist_id).collection('songs')
            song_doc = songs_ref.document(track_id).get()
            
            if song_doc.exists:
                song_data = song_doc.to_dict()
                if session["google_id"]["sub"] not in song_data["upvote_subs"]:  # if user has not already upvoted, add upvote
                    songs_ref.document(track_id).update({"upvotes": firestore.Increment(1), "upvote_subs": firestore.ArrayUnion([session["google_id"]["sub"]])})

                    if session["google_id"]["sub"] in song_data["downvote_subs"]:  # if user has already downvoted, remove downvote
                        songs_ref.document(track_id).update({"downvotes": firestore.Increment(-1), "downvote_subs": firestore.ArrayRemove([session["google_id"]["sub"]])})
                    return jsonify({"message": "upvote added"}), 200
                
                else: # if user has already upvoted, remove upvote
                    songs_ref.document(track_id).update({"upvotes": firestore.Increment(-1), "upvote_subs": firestore.ArrayRemove([session["google_id"]["sub"]])})
                    return jsonify({"message": "upvote removed"}), 200
                
            return jsonify({"message": "Song not found"}), 404
        return jsonify({"message": "Missing track-id"}), 400
    return jsonify({"message": "Missing playlist-id"}), 400

@app.route('/downvote', methods=["POST"]) # Downvote a song
def downvote():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data['playlist_id']
        if "track_id" in data:
            track_id = data['track_id']
            songs_ref = db.collection('playlists').document(playlist_id).collection('songs')
            song_doc = songs_ref.document(track_id).get()
            
            if song_doc.exists:
                song_data = song_doc.to_dict()
                if session["google_id"]["sub"] not in song_data["downvote_subs"]: # if user has not already downvoted, add downvote
                    songs_ref.document(track_id).update({"downvotes": firestore.Increment(1), "downvote_subs": firestore.ArrayUnion([session["google_id"]["sub"]])})

                    if session["google_id"]["sub"] in song_data["upvote_subs"]:  # if user has already upvoted, remove upvote
                        songs_ref.document(track_id).update({"upvotes": firestore.Increment(-1), "upvote_subs": firestore.ArrayRemove([session["google_id"]["sub"]])})
                    return jsonify({"message": "downvote added"}), 200
                
                else: # if user has already downvoted, remove downvote
                    songs_ref.document(track_id).update({"downvotes": firestore.Increment(-1), "downvote_subs": firestore.ArrayRemove([session["google_id"]["sub"]])})
                    return jsonify({"message": "downvote removed"}), 200
                
            return jsonify({"message": "Song not found"}), 404
        return jsonify({"message": "Missing track-id"}), 400
    return jsonify({"message": "Missing playlist-id"}), 400

@app.route("/delete", methods=["POST"])  # Delete a song
def delete():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data['playlist_id']
        if "track_id" in data:
            track_id = data['track_id']
            playlist_ref = db.collection('playlists').document(playlist_id)
            song_ref = playlist_ref.collection('songs').document(track_id)
            song_doc = song_ref.get()
            if song_doc.exists:
                song_doc = song_doc.to_dict()
                if song_doc.get("add_sub") == "" or song_doc.get("add_sub") == session["google_id"]["sub"]:
                    token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
                    if token_info:
                        sp = spotipy.Spotify(auth=token_info['access_token'])
                        sp.playlist_remove_all_occurrences_of_items(playlist_id, [track_id])

                        song_ref.delete()
                        playlist_ref.update({"length": firestore.Increment(-1), "song_ids": firestore.ArrayRemove([track_id])})
                        return jsonify({"message": "Song deleted from Spotify and database"}), 200
                    return jsonify({"message": "Unable to update Spotify token"}), 401
                return jsonify({"message": "Only the user who added the song may delete it"}), 401
            return jsonify({"message": "Could not find song in database"}), 500
        return jsonify({"message": "Missing track-id field"}), 400
    return jsonify({"message": "Missing playlist-id field"}), 400

@app.route("/play", methods=["POST"])
def play():
    data = request.get_json()
    if "playlist_id" in data:
        playlist_id = data.get("playlist_id")
        token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
        if token_info:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            playlist_ref = db.collection("playlists").document(playlist_id)
            if playlist_ref.get().exists:
                name = playlist_ref.get().to_dict()["playlist_name"]
                songs_collection = list(playlist_ref.collection("songs").stream())
                
                session["shuffle_state"] = data.get("shuffle_state", session.get("shuffle_state"))
                shuffled_songs = hybrid_shuffle_softplus(songs_collection) if session["shuffle_state"] else sort_by_votes(songs_collection)
                try:
                    sp.start_playback(uris=[song["song_uri"] for song in shuffled_songs], device_id=data.get("device_id"))
                except SpotifyException as e:
                    if e.reason == "NO_ACTIVE_DEVICE":
                        devices = sp.devices()["devices"]
                        if len(devices) != 0:  # If there are any devices at all, use the first one
                            sp.start_playback(uris=[song["song_uri"] for song in shuffled_songs], device_id=devices[0]["id"])
                            return jsonify({"message": "No active device found, using first one"}), 200
                        return jsonify({"message": "No active device found"}), 404
                    elif "Device not found" in e.msg:
                        return jsonify({"message": "Device not found"}), 404
                    else:
                        return jsonify({"message": "Error occured: " + str(e)}), 500
                return jsonify({"message": "Playing from " + name}), 200
            return jsonify({"message": "Playlist doesn't exist"}), 404
        return jsonify({"message": "Unable to update Spotify token"}), 401
    return jsonify({"message": "Missing playlist-id field"}), 400


# OAuth Endpoints
@app.route("/login")  # Login with Google
def login():
    authorization_url, state = flow.authorization_url()
    session["google_id"] = {"state": state}
    return redirect(authorization_url)

@app.route("/callback")  # Google OAuth callback
def callback():
    if not session["google_id"]["state"] == request.args["state"]:
        print("Google OAuth state does not match! Redirecting...")
    else:
        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            print("Error fetching Google OAuth token:", e)
            return redirect("/")
        credentials = flow.credentials
        request_session = requests.session()
        cached_session = cachecontrol.CacheControl(request_session)
        token_request = google.auth.transport.requests.Request(session=cached_session)

        id_info = id_token.verify_oauth2_token(
            id_token=credentials._id_token,
            request=token_request,
            audience=flow.client_config["client_id"]
        )
        print("User logged in: ", id_info["name"], id_info["email"], id_info["sub"])
        session["google_id"] = {
            **session.get("google_id", {}),
            **id_info
        }

        doc = db.collection("users").document(id_info["sub"]).get()
        if doc.exists: db.collection("users").document(id_info["sub"]).update({**id_info})
        else: db.collection("users").document(id_info["sub"]).set({**id_info})

    return redirect("/spotify-login")

@app.route("/spotify-login")  # Login with Spotify
@login_required
def spotify_login():
    token_info = sp_cache_handler.get_cached_token()
    if token_info:
        print("Spotify token retreived from database for", session["google_id"]["name"], "(" + session["google_id"]["sub"] + ")")
        return redirect("/app")
    return redirect(sp_oauth.get_authorize_url())

@app.route("/spotify-callback")  # Spotify OAuth callback
@login_required
def spotify_callback():
    sp_oauth.get_access_token(request.args.get('code'))
    print("Spotify token created for", session["google_id"]["name"], "(" + session["google_id"]["sub"] + ")")
    return redirect("/app")
    
@app.route("/logout")  # Logout and clear session
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host="0.0.0.0", port=80, debug=True)