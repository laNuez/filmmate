# FilmMate	
Video Demo: https://youtu.be/0MDI3J4Gi1w

FilmMate is a web application that allows users to keep track of movies they have watched, get recommendations, maintain a watchlist, rate movies and view their ratings and watchlist at any time, gaining insights into their movie watchlist habits.

## Features
- **Movie Search**: `/search` FilmMate includes a movie search feature that allows users to search movies.
- **Movie Details**: `/movies/<id>` When a user clicks on a movie, they are taken to a details page where it shows, description, release date, ratings of users and a "More like this" list.
- **User Ratings**: `/rate/movies/<id>` FilmMate allows users to rate movies on a scale of 1 to 4.
- **User Profiles**: `/users/<username>/` Users can view theirs and others user's profiles, profile have a recently added to the watchlist and recently rated movies sections, along with a graph that shows their total watch time.
## Project structure
The project is structured into a main `app.py` file that contains all the endpoints. Most of these endpoints interact with the Supabase library to perform CRUD (Create, Read, Update, Delete) operations. Additionally, there is a `templates` folder which holds all the HTML templates.


## Design choices
- **Fron-end**: I considered using a JavaScript framework such as React or Svelte, but ultimately decided to use none, as the project would not require much interactivity client side, due to all the logic happening on the backend.
- **Back-end**: Flask, easy choice. I could have made it using Astro but I wanted to get out of my comfort zone that is JavaScript.
- **Machine Learning**: Initially I wanted to use a collaborative filtering machine learning algorithm, to serve recommendations. After some research and prototypes I realized it wouldn’t be feasible as I lacked the time to optimize such feature, not to mention the lack of current datasets.
-- **Database**: I started using SQLite but quickly realize I didn't have anywhere to host the database, I then switched to Supabase, an alternative to Firebase with features as auth, PostgreSQL, functions, storage and real-time. For this project I only used the database as I didn’t want to rely too much on a platform.

## Other
### Interactive
I used JavaScript to sprinkle some functionality on `cover.html` to switch the image of a cover based on the selection of a user. 
### Styles
I used a combination of classes from Bulma and inline styles and took advantage of some modern web features like media-queries to do something responsive.

## Documentation
https://supabase.com/docs/reference/python/start
https://developer.themoviedb.org/reference/intro/getting-started
https://bulma.io/documentation/

Based on the design of Taste.io and TMDB
