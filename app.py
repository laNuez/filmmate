import datetime
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
import requests
from werkzeug.security import check_password_hash, generate_password_hash
import os
import re

from helpers import login_required

# supa
from supabase import create_client, Client
from supabase.client import ClientOptions

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY,
  options=ClientOptions(
    postgrest_client_timeout=10,
    storage_client_timeout=10,
    schema="public",
  ))

#tmdb
import tmdbsimple as tmdb
tmdb.API_KEY = os.getenv("TMDB_API_KEY")
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
    trending_movies = fetch_trending_movies()
    
    # popular_movies = fetch_popular_movies()

    recommendations = recommendations_from_users()
    recc_list = []
    for movie in recommendations:
        if not movie.get('id', None):
            continue
        
        data = tmdb.Movies(movie['id'])
        response = data.info(append_to_response="images")
        movie_dict = {}
        movie_dict["id"] = response["id"]
        movie_dict["title"] = response["title"]
        movie_dict["backdrop_path"] = "https://image.tmdb.org/t/p/w500/{}".format(response["backdrop_path"])

        recc_list.append(movie_dict)
    
    return render_template("dashboard.html", movies=trending_movies, recommendations=recc_list)

def fetch_popular_movies():
    movies = tmdb.Movies.popular(tmdb.Movies())
    movies_list = [
        {
            "id": movie["id"],
            "title": movie["title"],
            "backdrop_path": f"https://image.tmdb.org/t/p/w500/{movie['backdrop_path']}"
        }
        for movie in movies["results"]
    ]
    return movies_list

def fetch_trending_movies():
    movies = tmdb.Trending("movie").info()
    movies_list = [
    {
        "id": movie["id"],
        "title": movie["title"],
        "backdrop_path": f"https://image.tmdb.org/t/p/w500/{movie['backdrop_path']}"
    }
    for movie in movies["results"]
    ]
    return movies_list

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
    dict["title"] = response["title"]
    dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])
    dict["cast"] = response["credits"]["cast"][:5]
    dict["id"] = response["id"]
    dict["director"] = 'unknown'
    # i took the lambda from duckduckgo ai chat
    minutes_to_hour_minutes = lambda total_minutes: f"{total_minutes // 60} hr {total_minutes % 60} min"
    dict["runtime"] = minutes_to_hour_minutes(response["runtime"])
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
    year = date_str.split('-')[0]
    dict['year'] = year
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

def get_rating_int(rating: str):
    match rating:
        case 'awful':
            return 1
        case "meh":
            return 2   
        case "good":
            return 3
        case "amazing":
            return 4
        case _:
            return None
        
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
def watchlist(username):
    response = (
        supabase.table('users')
        .select('id, wallpaper, movie_watchlist(movie_id)')
        .eq('username', username)
        .execute()
    )
    if not response.data:
        return 'bruh'
    
    user_id = response.data[0]['id']
    wallpaper = response.data[0].get('wallpaper', None)
    watchlist = response.data[0]['movie_watchlist']
    watchlist_count = len(response.data[0]['movie_watchlist'])
    
    show_wallpaper = False
    if wallpaper:
        show_wallpaper = True
    
    hero_count = {"rated": 0, "watchlist": watchlist_count}
    
    arr = []
    for id in watchlist:
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
    
    data, count = supabase.from_('ratings').select('rated_item_id, rating_value', count='exact').eq('user_id', user_id).execute()
    hero_count["rated"] = count[1]
    
    return render_template("watchlist.html", watchlist=new_arr, username=username, hero_count=hero_count, wallpaper=wallpaper, show_wallpaper=show_wallpaper)

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
    query = (
        supabase.table('users')
        .select('wallpaper, ratings(rated_item_id, rating_value), movie_watchlist(movie_id)')
        .filter('username', 'eq', username)
    )
    
    sort_by_rating = request.args.get('list')
    if sort_by_rating:
        query = query.eq('ratings.rating_value', get_rating_int(sort_by_rating))
    
    response = query.execute()

    if not response.data:
        return 'bruh'
    
    wallpaper = response.data[0].get('wallpaper', None)
    rated_list = response.data[0]['ratings']
    watchlist_count = len(response.data[0]['movie_watchlist'])

    show_wallpaper = False
    if wallpaper:
        show_wallpaper = True
    
    hero_count = {"rated": len(rated_list), "watchlist": watchlist_count}
    
    movie_list = []
    for id in rated_list:
        dict = {}
        data = tmdb.Movies(id["rated_item_id"])
        response = data.info(append_to_response="images")
        dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])
        dict["title"] = response["title"]
        dict["id"] = response["id"]
        dict["rating"] = id["rating_value"]
        dict["rating_text"] = get_rating_text(id["rating_value"])
        movie_list.append(dict)
        
    return render_template('rated.html', movies=movie_list, username=username, sort=sort_by_rating, hero_count=hero_count, wallpaper=wallpaper, show_wallpaper=show_wallpaper)
    
@app.route('/users/<username>/')
def profile(username):
    
    # watchlist
    info = {
        "watchlist": [],
        "rated": [],
        "count": {
            "awful": 0,
            "meh": 0,
            "good": 0,
            "amazing": 0
        }
    }
    data, count = supabase.from_('users').select('id, wallpaper').eq('username', username).execute()
    wallpaper = data[1][0]["wallpaper"]
    show_wallpaper = False
    if wallpaper:
        show_wallpaper = True
    user_id = data[1][0]["id"]
    # rated
    data, count = supabase.from_('ratings').select('rated_item_id, rating_value').eq('user_id', user_id).order('created_at', desc=True ).execute()
    
    for id in data[1]:
        dict = {}
        data = tmdb.Movies(id["rated_item_id"])
        response = data.info(append_to_response="images")
        dict["id"] = response["id"]
        dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])

        rting = get_rating_text(id["rating_value"])
        info["count"][rting] = info["count"].get(rting) + 1
        info['runtime_minutes'] = info.get('runtime_minutes', 0) + response["runtime"]
        info["rated"].append(dict)
    
    # watchlist
    data, count = supabase.from_('movie_watchlist').select('movie_id').eq('user_id', user_id).order('created_at', desc=True ).execute()
    
    for id in data[1]:
        dict = {}
        data = tmdb.Movies(id["movie_id"])
        response = data.info(append_to_response="images")
        dict["id"] = response["id"]
        dict["poster_path"] = "https://image.tmdb.org/t/p/w300/{}".format(response["poster_path"])
        
        
        
        info["watchlist"].append(dict)

    # format runtime
    runtime_hours = info.get('runtime_minutes', 0) / 60
    info['runtime_hours'] = int(runtime_hours)
    info['runtime_days'] = format(runtime_hours / 24, '.2f')
    
    return render_template('profile.html', username=username, info=info, wallpaper=wallpaper, show_wallpaper=show_wallpaper)

@app.route('/wallpaper', methods=["POST"])
def wallpaper():

    url = request.form.get('url')
    
    if not url:
        return 'bruh'
    
    pattern = r'^\/[a-zA-Z0-9]+\.jpg$'
    if not bool(re.match(pattern, url)):
        return 'bruh'

    supabase.table('users').update({"wallpaper": url}).eq('id', session['user_id']).execute()
    return redirect(request.referrer)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/settings/cover')
def settings_cover():
    data, count = supabase.from_('ratings').select('rated_item_id', count='exact').eq('user_id', session['user_id']).eq('rating_value', 4).execute()
    d, c = supabase.from_('users').select('wallpaper').eq('id', session['user_id']).execute()
    current_bg = d[1][0]['wallpaper']
    
    movies = []

    for id in data[1]:
        dict = {}
        data = tmdb.Movies(id["rated_item_id"])
        response = data.info(append_to_response="images")
        dict["id"] = response["id"]
        dict["title"] = response["title"]
        dict['image'] = response['images']['backdrops'][0]["file_path"]
        movies.append(dict)

    return render_template('cover.html', movies=movies, current_bg=current_bg)

def recommendations_from_users():
    ratings, c = supabase.from_('ratings').select('rated_item_id, rating_value', count='exact').execute()

    rating_dict = {}
    for x in ratings[1]:
        
        item_id = x['rated_item_id']
        rating_value = x['rating_value']

        if item_id not in rating_dict:
            rating_dict[item_id] = {'total_rating': 0, 'count': 0}
        
        rating_dict[item_id]['total_rating'] += rating_value
        rating_dict[item_id]['count'] += 1

    to_print = []
    C = mean_vote_for_movies(ratings, c)
    for item_id, data in rating_dict.items():
        weighted_rating = calculate_weighted_rating(data['total_rating'], data['count'], C)
        to_print.append({'rating': weighted_rating, 'id': item_id})
        
    list_sorted = sorted(to_print, key=lambda x: x['rating'], reverse=True)
    return list_sorted[:8]

def calculate_weighted_rating(total_rating, count, C):
    m = 2
    
    R = total_rating / count
    
    weighted_rating = (count * R + m * C) / (count + m)
    return weighted_rating

def mean_vote_for_movies(r, c):
    total = 0
    for x in r[1]:
        total += x['rating_value']
    C = total / c[1]

    return C
