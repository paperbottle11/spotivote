import os
from dotenv import load_dotenv
import json
from functools import wraps

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

class spotify_data():
    def __init__(self,name):
        search_str = name
        sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())
        self.result = sp.search(search_str,5)
        self.veri=dict()
        for i in range(5):
            my_dict={}
            my_dict["id"]=self.result['tracks']['items'][i]['id']
            my_dict["cover_img"]=self.result['tracks']['items'][i]['album']['images'][0]['url']
            my_dict["name"]=self.result['tracks']['items'][i]['name']
            my_dict["artist"]=self.result['tracks']['items'][i]['album']['artists'][0]['name']
            self.veri[my_dict["id"]] = my_dict

def login_required(function):
    # A decorator function that checks if the user is logged in before allowing access to certain routes
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "sub" not in session.get("google_id", {}):
            return redirect("/")
        else:
            return function()
        
    return wrapper

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
class FirestoreCacheHandler(spotipy.cache_handler.CacheHandler):
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

sp_cache_handler = FirestoreCacheHandler(db, session)
sp_oauth = SpotifyOAuth(client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
                        scope=os.getenv("SPOTIPY_SCOPE"),
                        cache_handler=sp_cache_handler,
                        show_dialog=True)

@app.route("/", methods=["GET"])
def root():
    user_playlists = {}
    
    if "sub" in session.get("google_id", {}): # If user logged in
        token_info = sp_oauth.validate_token(sp_cache_handler.get_cached_token())
        if token_info:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            user_playlists = sp.current_user_playlists()

    return render_template("index.html", session=session, user_playlists=user_playlists, current_playlist={}) # "name": "Spotivote", "playlist_url": "", "image_url": ""

    current_playlist_id = "7APR2GKM3MVHa3T3uLwcOX"

    if "playlist_id" in request.args:
        current_playlist_id = request.args.get('playlist_id')
    
    current_playlist = sp.playlist(current_playlist_id)
    image_url = current_playlist['images'][0]['url'] if current_playlist['images'] else None
    name = current_playlist['name']
    user_playlists = {}
    if "sub" in session: # If user logged in
        users = db.collection("users").document(session["sub"]).get()
        if not users.exists: # Create user if not found
            db.collection("users").document(session["sub"]).set({"name": session["name"], "profile_picture_url": session["picture"], "playlists": []})
        else: # Get user playlists
            playlists = users.to_dict().get("playlists", [])
            for playlist_id in playlists:
                playlist = sp.playlist(playlist_id)
                user_playlists[playlist_id] = {"name": playlist["name"], "image_url": playlist["images"][0]["url"] if playlist["images"] else None}

    return render_template("base.html",session=session, image_url=image_url, name=name, playlist_id=current_playlist_id, user_playlists=user_playlists)

@app.route("/songs", methods=["GET"])
def songs():
    if 'playlist_id' in request.args:
        playlist_id = request.args.get('playlist_id')

        song_ids = []
        songs_list = []
        for track in sp.playlist_tracks(playlist_id)["items"]:
            id = track["item"]["id"]
            track_name = track["item"]["name"]
            track_artist = track["item"]["artists"][0]["name"]
            track_album = track["item"]["album"]["name"]
            cover_url = track["item"]["album"]["images"][0]["url"]
        
            song_ids.append(id)
            songs_list.append({"id": id, "name": track_name, "artist": track_artist, "album": track_album, "cover_url": cover_url})
        
        playlist_ref = db.collection('playlists').document(playlist_id)
        songs_ref = playlist_ref.collection('songs')
        

        for song in songs_list:
            song_doc = songs_ref.document(song["id"]).get()
            if song_doc.exists:
                data = song_doc.to_dict()
                if "sub" in session:
                    if session["sub"] in data["upvote_subs"]:
                        song["vote"] = 1
                    elif session["sub"] in data["downvote_subs"]:
                        song["vote"] = -1
                    else:
                        song["vote"] = 0
                else:
                    song["vote"] = 0
                song["add_profile_picture"] = data["add_profile_picture"]
                song["add_sub"] = data["add_sub"]
                song["add_user_name"] = data["add_user_name"]
                song["date_added"] = data["date_added"].timestamp()
            else:
                songs_ref.document(song["id"]).set({"song_name": song["name"], "song_artist": song["artist"], "upvotes": 0, "upvote_subs": [], "downvotes": 0, "downvote_subs": [], "date_added": firestore.SERVER_TIMESTAMP, "add_sub": "", "add_user_name": "", "add_profile_picture": ""})
                song["vote"] = 0

        for doc in songs_ref.stream():
            if doc.id not in song_ids:
                songs_ref.document(doc.id).delete()

        return json.dumps(songs_list)
    return "Error: Missing playlist_id query"

@app.route('/add', methods=["POST"])
def add():
    if "playlist_id" in request.args and "track_id" in request.args:
        track_id = request.args.get('track_id')
        track_uris = [f'spotify:track:{track_id}']  # Replace with the track URIs
        list_id = request.args.get('playlist_id')
        sp.playlist_add_items(list_id, track_uris)

        track_info = sp.track(track_id)

        song_name = track_info['name']
        song_artist = track_info['artists'][0]['name']

        playlist_ref = db.collection('playlists').document(list_id)
        songs_ref = playlist_ref.collection('songs')

        songs_ref.document(track_id).set({"song_name": song_name, "song_artist": song_artist, "upvotes": 0, "upvote_subs": [], "downvotes": 0, "downvote_subs": [], "date_added": firestore.SERVER_TIMESTAMP, "add_sub": session["sub"], "add_user_name": session["name"], "add_profile_picture": session["picture"]})

        return "success"
    return "Error: Missing playlist_id or track_id query"

@app.route('/upvote', methods=["POST"])
def upvote():
    request_data = request.get_json()
    if "playlist_id" in request_data and "track_id" in request_data:
        track_id = request_data['track_id']
        list_id = request_data['playlist_id']

        playlist_ref = db.collection('playlists').document(list_id)
        songs_ref = playlist_ref.collection('songs')
        song_doc = songs_ref.document(track_id).get()
        if song_doc.exists:
            song_data = song_doc.to_dict()
            if session["sub"] not in song_data["upvote_subs"]:
                songs_ref.document(track_id).update({"upvotes": firestore.Increment(1), "upvote_subs": firestore.ArrayUnion([session["sub"]])})
                if session["sub"] in song_data["downvote_subs"]:
                    songs_ref.document(track_id).update({"downvotes": firestore.Increment(-1), "downvote_subs": firestore.ArrayRemove([session["sub"]])})
                return jsonify({"message": "upvote added"}), 200
            else:
                songs_ref.document(track_id).update({"upvotes": firestore.Increment(-1), "upvote_subs": firestore.ArrayRemove([session["sub"]])})
                return jsonify({"message": "upvote removed"}), 200
        else:
            return jsonify({"message": "Song not found"}), 400
    return jsonify({"message": "Missing data"}), 400

@app.route('/downvote', methods=["POST"])
def downvote():
    request_data = request.get_json()
    if "playlist_id" in request.args and "track_id" in request.args:
        track_id = request.args.get('track_id')
        list_id = request.args.get('playlist_id')

        playlist_ref = db.collection('playlists').document(list_id)
        songs_ref = playlist_ref.collection('songs')
        song_doc = songs_ref.document(track_id).get()
        if song_doc.exists:
            data = song_doc.to_dict()
            if session["sub"] not in data["downvote_subs"]: # if user has not already downvoted, add downvote
                songs_ref.document(track_id).update({"downvotes": firestore.Increment(1), "downvote_subs": firestore.ArrayUnion([session["sub"]])})
                if session["sub"] in data["upvote_subs"]:
                    songs_ref.document(track_id).update({"upvotes": firestore.Increment(-1), "upvote_subs": firestore.ArrayRemove([session["sub"]])})
                return jsonify({"message": "downvote added"}), 200
            else: # if user has already downvoted, remove downvote
                songs_ref.document(track_id).update({"downvotes": firestore.Increment(-1), "downvote_subs": firestore.ArrayRemove([session["sub"]])})
                return jsonify({"message": "downvote removed"}), 200
        else:
            return jsonify({"message": "Song not found"}), 400
    return jsonify({"message": "Missing data"}), 400

@app.route('/search', methods=["GET"]) # Song search
def search():
    try:
        search = request.args.get('q')
        data = spotify_data(search)
        return json.dumps(data.veri)
    except:
        pass

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
        flow.fetch_token(authorization_response=request.url)
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
        if not doc.exists: # Create user in database if not found
            db.collection("users").document(id_info["sub"]).set({"name": id_info["name"], "profile_picture_url": id_info["picture"], "playlists": []})

    return redirect("/spotify-login")

@app.route("/spotify-login")  # Login with Spotify
@login_required
def spotify_login():
    token_info = sp_cache_handler.get_cached_token()
    if token_info:
        print("Spotify token for", session["google_id"]["name"], "(" + session["google_id"]["sub"] + ")", "retreived from database")
        return redirect("/")
    return redirect(sp_oauth.get_authorize_url())

@app.route("/spotify-callback")  # Spotify OAuth callback
@login_required
def spotify_callback():
    sp_oauth.get_access_token(request.args.get('code'))
    print("Spotify token for", session["google_id"]["name"], "(" + session["google_id"]["sub"] + ")", "created")
    return redirect("/")
    
@app.route("/logout")  # Logout and clear session
def logout():
    session.clear()
    return redirect("/")
if __name__ == "__main__":
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host="0.0.0.0", port=80, debug=True)
