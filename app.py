import datetime
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
import requests
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

# supa
import os
from supabase import create_client, Client
from supabase.client import ClientOptions

url = "https://bkfmmzqhbrrkhytyjrul.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrZm1tenFoYnJya2h5dHlqcnVsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTc3MDY3ODYsImV4cCI6MjAzMzI4Mjc4Nn0.jpkTshBGvMiPitAvG54VxFH90d_Cv8fMw1VcEtKiVj0"
supabase: Client = create_client(url, key,
  options=ClientOptions(
    postgrest_client_timeout=10,
    storage_client_timeout=10,
    schema="public",
  ))

#tmdb
import tmdbsimple as tmdb
tmdb.API_KEY = 'bab3e0fcb6b0519d5d23a13251765ef6'
tmdb.REQUESTS_TIMEOUT = 5 
tmdb.REQUESTS_SESSION = requests.Session()

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.route("/")
def index():
    if session.get("user_id", None):
        return redirect("/dashboard")
    
    return render_template("index.html")

@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or not confirmation:
            return "bruh"
        
        if password != confirmation:
            return "bruh"
        
        # check if already exists
        rows = supabase.table('users').select('*').eq('username', username).execute()
        if rows.data:
           return "already exists bro" 
        
        hash = generate_password_hash(password)
        
        data, count = supabase.table('users').insert({"username": username, "hash": hash}).execute()

        return redirect("/login")
        
        
    
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    
    session.clear()
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if not username or not password:
            return "bruh"
        
        data, count = supabase.table('users').select('id, hash').eq('username', username).execute()
        
        if not data[1]:
            return 'Wrong username or password'

        if not check_password_hash(data[1][0]["hash"], password):
            return "Wrong username or password"
        
        session["user_id"] = data[1][0]["id"]
        session["username"] = username
        
        return redirect("/dashboard")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    movies = tmdb.Trending("movie")
    response = movies.info()
    movies_list = []
    for movie in response["results"]:
        dict = {}
        dict["id"] = movie["id"]
        dict["title"] = movie["title"]
        dict["backdrop_path"] = "https://image.tmdb.org/t/p/w500/{}".format(movie["backdrop_path"])

        movies_list.append(dict)
    
    # popular = tmdb.Movies.popular(tmdb.Movies())
    # print(popular)
    # popular_list = []
    # for entry in popular["results"]:
    #     dict = {}
    #     dict["id"] = entry["id"]
    #     dict["title"] = entry["title"]
    #     dict["backdrop_path"] = "https://image.tmdb.org/t/p/w500/{}".format(entry["backdrop_path"])    
        
    #     popular_list.append(dict)
    
    return render_template("dashboard.html", movies=movies_list)

@app.route("/movies/<id>")
@login_required
def movies(id):
    if not id:
        return 'bruh'
    
    data = tmdb.Movies(id)
    response = data.info(append_to_response="credits,images")

    img = None
    if response['images']['backdrops']:
        img = response['images']['backdrops'][0]
    dict = {}
    
        
    if img:
        dict['backdrop'] = "https://image.tmdb.org/t/p/original/{}".format(img['file_path'])
    else:
        dict['backdrop'] = None
    
    dict["genres"] = response["genres"]
    dict["release_date"] = response["release_date"]
    dict["runtime"] = response["runtime"]
    dict["overview"] = response["overview"]
    dict["original_title"] = response["original_title"]
    dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])
    dict["cast"] = response["credits"]["cast"][:5]
    dict["id"] = response["id"]
    dict["director"] = 'unknown'
    a = response["credits"]["crew"]
    for x in a:
        if x['job'] == 'Director':
            dict["director"] = x['name']
            break
        
    arr = []
    a = response["credits"]["crew"]
    for x in a:
        if x['job'] == 'Screenplay':
            arr.append(x['name'])

    if not arr:
        arr.append('unknown')
        
    dict["writters"] = arr
    
    date_str = response["release_date"]
    date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    dict['formatted_date'] = date_obj.strftime('%B %d, %Y')
    
    similar = get_similar_movies(data)
    
    data, count = supabase.from_('movie_watchlist').select('movie_id').eq('user_id', session['user_id']).eq('movie_id', id).execute()

    onwatchlist = False
    if data[1]:
        onwatchlist = True
    
    # ratings
    data, count = supabase.from_('ratings').select('*').eq('rated_item_id', id).execute()
    
    ratings = []
    
    for res in data[1]:
        rating = {}
        rating["username"] = get_username(res["user_id"])
        rating["rating"] = res["rating_value"]
        rating["rating_text"] = get_rating_text(res["rating_value"])
        rating["timestamp"] = res["created_at"]
        ratings.append(rating)

    # current rating for the current user
    data, count = supabase.from_('ratings').select('rating_value').eq('user_id', session["user_id"]).eq('rated_item_id', id).execute()
    current_rating = get_rating_text(data[1][0]["rating_value"]) if data[1] else None
    
    return render_template("movie.html", movie=dict, similar=similar, onwatchlist=onwatchlist, ratings=ratings, current_rating=current_rating)

def get_rating_text(rating: int):
    match rating:
        case 1:
            return "awful"
        case 2:
            return "meh"    
        case 3:
            return "good"
        case 4:
            return "amazing"
        case _:
            return 'none'

def get_username(user_id):
    
    data, count = supabase.from_('users').select('username').eq('id', user_id).execute()

    return data[1][0]["username"]

def get_similar_movies(self):
    movies = tmdb.Movies.recommendations(self)
    
    arr = []

    res = movies["results"][:8]
    for movie in res:
        dict = {}
        if movie['backdrop_path']:
            dict['backdrop_path'] = "https://image.tmdb.org/t/p/w500/{}".format(movie["backdrop_path"])
        else:
            dict['backdrop_path'] = None
            
        dict['id'] = movie['id']
        dict['title'] = movie['title']
        dict['overview'] = movie['overview']
        arr.append(dict)
        
    return arr

@app.route("/rate/movies/<id>", methods=["POST"])
@login_required
def rate_movie(id):
    if not id:
        return 'bruh'
    
    clear = request.form.get('clear')
    if clear == 'true':
        data, count = supabase.table('ratings').delete().eq('user_id', session["user_id"]).eq('rated_item_id', id).execute()
        return redirect(request.referrer)
        
    rating = request.form.get('rating')
    
    if not rating:
        return 'bruh'    

    actual_rating = None
    
    match rating:
        case "awful":
            actual_rating = 1
        case "meh":
            actual_rating = 2    
        case "good":
            actual_rating = 3
        case "amazing":
            actual_rating = 4
    
    if not actual_rating:
        return 'bruh'
    
    data, count = supabase.table('ratings').upsert({'user_id': session["user_id"], 'rated_item_id': id, 'rating_value': actual_rating}).execute()

    # remove from watchlist if it exists
    try:
        data, count = supabase.table('movie_watchlist').delete().eq('user_id', session["user_id"]).eq('movie_id', id).execute()
    except:
        ""
    
    return redirect(request.referrer)

@app.route("/watchlist/movies/<id>", methods=["POST"])
@login_required
def add_to_movie_watchlist(id):
    if not id:
        return 'bruh'
    
    try:
        data, count = supabase.table('movie_watchlist').insert({'user_id': session["user_id"], 'movie_id': id}).execute()
    except:
        data, count = supabase.table('movie_watchlist').delete().eq('user_id', session["user_id"]).eq('movie_id', id).execute()
    
    return redirect(request.referrer)

@app.route('/users/<username>/watchlist')
@login_required
def watchlist(username):
    if not username:
        return 'bruh'

    data, count = supabase.from_('users').select('id').eq('username', username).execute()
    data, count = supabase.from_('movie_watchlist').select('movie_id').eq('user_id', data[1][0]["id"]).execute()
    
    if not data[1]:
        return render_template("watchlist.html", watchlist=None)
    
    arr = []
    for id in data[1]:
        data = tmdb.Movies(id['movie_id'])
        response = data.info()
        arr.append(response)
    
    new_arr = []
    
    for movie in arr:
        dict = {}
        dict["id"] = movie["id"]
        dict["title"] = movie["title"]
        dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(movie["poster_path"])
        new_arr.append(dict)
    
    return render_template("watchlist.html", watchlist=new_arr)

@app.route("/search")
@login_required    
def search():
    q = request.args.get('query', None)
    page = request.args.get('page', 1)
    
    res = tmdb.Search.movie(tmdb.Search(),query=q, page=page)
    print(res['total_pages'])
    return render_template("search.html", results=res['results'], current_page=res['page'], total_page=res['total_pages'])

@app.route("/users/<username>/rated")
def rated(username):
    data, count = supabase.from_('users').select('id').eq('username', username).execute()
    user_id = data[1][0]["id"]
    data, count = supabase.from_('ratings').select('rated_item_id').eq('user_id', user_id).execute()

    movie_list = []
    for id in data[1]:
        dict = {}
        data = tmdb.Movies(id["rated_item_id"])
        response = data.info(append_to_response="images")
        dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])
        dict["title"] = response["title"]
        dict["id"] = response["id"]
        movie_list.append(dict)
    
    return render_template('rated.html', movies=movie_list)
    