import datetime
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
import requests
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3

#tmdb
import tmdbsimple as tmdb
tmdb.API_KEY = 'bab3e0fcb6b0519d5d23a13251765ef6'
tmdb.REQUESTS_TIMEOUT = 5 
tmdb.REQUESTS_SESSION = requests.Session()

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

conn = sqlite3.connect("filmmate.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
db = conn.cursor()

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
        rows = db.execute("SELECT * FROM users WHERE username = ?",  (username,)).fetchall()
        print(rows)
        if rows:
           return "already exists bro" 
        
        hash = generate_password_hash(password)
        
        db.execute("INSERT INTO users (username, hash) VALUES (?,?)", (username, hash) )
        conn.commit()
        
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
        
        # user_password = db.get(username, None)
        rows = db.execute("SELECT id, hash FROM users WHERE username = ?",  (username,))
        # https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query#comment91011721_41920171
        result = [dict(row) for row in rows.fetchall()]
        
        if not result:
            return "Wrong username or password"
        
        if not check_password_hash(result[0]["hash"], password):
            return "Wrong username or password"
        
        session["user_id"] = result[0]["id"]
        session["username"] = username
        
        return redirect("/dashboard")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    
    return redirect("/")

@app.route("/dashboard")
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
    
    rows = db.execute("SELECT movie_id FROM movie_watchlist WHERE user_id = ? AND movie_id = ?", (session['user_id'], id))
    result = rows.fetchall()
    
    onwatchlist = None
    if result:
        onwatchlist = True
    
    # ratings
    rows = db.execute("SELECT * FROM ratings WHERE rated_item_id = ?", (id,))
    result = rows.fetchall()
    
    ratings = []

    for res in result:
        rating = {}
        rating["username"] = get_username(res["user_id"])
        rating["rating"] = res["rating_value"]
        rating["timestamp"] = res["created_at"]
        ratings.append(rating)
    
    return render_template("movie.html", movie=dict, similar=similar, onwatchlist=onwatchlist, ratings=ratings)

def get_username(user_id):
    
    rows = db.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    result = rows.fetchall()
        
    return result[0]["username"]
    

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
def rate_movie(id):
    if not id:
        return 'bruh'
    
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
    
    try:
        db.execute("INSERT INTO ratings (user_id, rated_item_id, rating_value) VALUES (?,?,?)", (session["user_id"], id, actual_rating))
    except sqlite3.IntegrityError:
        db.execute("UPDATE ratings SET (rating_value) = ? WHERE user_id = ?", (actual_rating, session["user_id"]))
    
    conn.commit()

    return redirect(request.referrer)

@app.route("/watchlist/movies/<id>", methods=["POST"])
def add_to_movie_watchlist(id):
    if not id:
        return 'bruh'
    
    try:
        db.execute("INSERT INTO movie_watchlist (user_id, movie_id) VALUES (?,?)", (session["user_id"], id))
        conn.commit()
    except sqlite3.IntegrityError:
        db.execute("DELETE FROM movie_watchlist WHERE user_id = ? AND movie_id = ?", (session["user_id"], id))
        conn.commit()
    
    return redirect(request.referrer)

@app.route('/users/<username>/watchlist')
def watchlist(username):
    if not username:
        return 'bruh'

    rows = db.execute("SELECT id FROM users WHERE username = ?",  (username,))
    row = rows.fetchall()
    
    rows = db.execute("SELECT movie_id FROM movie_watchlist WHERE user_id = ?", (row[0]['id'],))
    results = rows.fetchall()
    
    if not results:
        return render_template("watchlist.html", watchlist=None)
    
    arr = []
    for id in results:
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
def search():
    q = request.args.get('query', None)
    page = request.args.get('page', 1)
    
    res = tmdb.Search.movie(tmdb.Search(),query=q, page=page)
    print(res['total_pages'])
    return render_template("search.html", results=res['results'], current_page=res['page'], total_page=res['total_pages'])
