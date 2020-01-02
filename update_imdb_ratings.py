# -*- coding: utf-8 -*-

#------------------------------------------------------------------------------
#
#             Plex movie and tv shows ratings script inspired on
#             script by /u/SwiftPanda16, extended by /u/Toastjuh
#
#                         *** Use at your own risk! ***
#   *** I am not responsible for damages to your Plex server or libraries. ***
#
#------------------------------------------------------------------------------

# Requires: plexapi, imdbpie, omdb

import sys
import requests, json, sqlite3, re, time
import omdb
from plexapi.server import PlexServer
from imdbpie import Imdb


### EDIT SETTINGS ###

PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = '' # how to fetch this? https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
LIBRARY_NAMES = []
PLEX_DATABASE_FILE = "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db" # where to find this folder? https://support.plex.tv/articles/202915258-where-is-the-plex-media-server-data-directory-located/

DRY_RUN = True  # Dry run without modifying the database (True or False)

### Optional: The Movie Database details ###
# using this to find the IMDB id for tvdb guids #
TMDB_API_KEY = ''
### Optional: The Open Movie Database details ###
# Enter your OMDB API key.
# Scraping IMDb can be very slow process. This speeds up the process by
# getting the IMDB rating directly from OMDB
OMDB_API_KEY = ''

if OMDB_API_KEY:
    omdb.set_default('apikey', OMDB_API_KEY)

##### CODE BELOW #####

TMDB_REQUEST_COUNT = 0  # DO NOT CHANGE
OMDB_REQUEST_COUNT = 0  # DO NOT CHANGE


# Setup overrides, manually specify a imdb id for tvdb ids
tvdb_overrides = {}
with open("tvdb-imdb.txt") as tvdb_overrides:
    for line in tvdb_overrides:
        tvdb, imdb = line.partition("=")[::2]
        tvdb_overrides[tvdb.strip()] = str(imdb)


def get_imdb_id_from_tmdb(tmdb_id, is_movie=True):
    global TMDB_REQUEST_COUNT
    
    if not TMDB_API_KEY:
        return None
    
    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0
    
    params = {"api_key": TMDB_API_KEY}
    print("Fetching IMDB id from TMDB {tmdb_id}".format(tmdb_id=tmdb_id))
    if is_movie:
        url = "https://api.themoviedb.org/3/movie/{tmdb_id}".format(tmdb_id=tmdb_id)
    else:
        url = "https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids".format(tmdb_id=tmdb_id)

    r = requests.get(url, params=params)
    
    TMDB_REQUEST_COUNT += 1
    
    if r.status_code == 200:
        media = json.loads(r.text)
        return media['imdb_id']
    else:
        return None


def get_imdb_id_from_tmdb_by_tvdb(tvdb_id):
    global TMDB_REQUEST_COUNT

    if tvdb_id in tvdb_overrides:
        print("Got an override for {tvdb_id}".format(tvdb_id=tvdb_id))
        return tvdb_overrides[tvdb_id].rstrip()
    
    if not TMDB_API_KEY:
        return None
    
    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0
    
    params = {"api_key": TMDB_API_KEY}
    
    url = "https://api.themoviedb.org/3/find/{tvdb_id}?external_source=tvdb_id".format(tvdb_id=tvdb_id)
    print("Fetching from TMDB with tvdb {tvdb_id}".format(tvdb_id=tvdb_id))
    r = requests.get(url, params=params)
    
    TMDB_REQUEST_COUNT += 1
    if r.status_code == 200:
        media_object = json.loads(r.text)

        # check if we did find TV results from TMDB
        if len(media_object["tv_results"]) == 0:
            print("Found no tv results based on tvdb id")
            return None

        # if we have found a TMDB id, we know need to get the IMDB id
        url = "https://api.themoviedb.org/3/tv/{tv_id}/external_ids".format(tv_id=media_object["tv_results"][0]["id"])
        print("Fetching external IMDB id from TMDB {tv_id}".format(tv_id=media_object["tv_results"][0]["id"]))
        r = requests.get(url, params=params)

        if r.status_code == 200:
            media_object = json.loads(r.text)
            if media_object['imdb_id'] is not None and media_object['imdb_id'] is not "":
                return media_object['imdb_id']
            else:
                return None
        return None
    else:
        print("Did not find by tvdb")
        return None


def get_imdb_rating_from_omdb(imdb_id):
    global OMDB_REQUEST_COUNT
    
    if not OMDB_API_KEY:
        return None
    
    # Wait 10 seconds for the TMDb rate limit
    if OMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0
    
    try:
        movie = omdb.imdbid(imdb_id, timeout=5)
    except:
        print("Error getting rating from OMDB. Trying again in few seconds")
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0
        return get_imdb_rating_from_omdb(imdb_id)
    
    OMDB_REQUEST_COUNT += 1

    # checking if there really is a rating and rating is not N/A
    if movie is not None and 'imdb_rating' in movie and movie["imdb_rating"] is not "N/A":
        return movie
    else:
        return None


def set_imdb_image(db, plex_object, rating):
    # method to set rating image to IMDB
    db_execute(db, "UPDATE metadata_items SET rating = ? WHERE id = ?", [rating, plex_object.ratingKey])

    extra_data = db_execute(db, "SELECT extra_data FROM metadata_items WHERE id = ?", [plex_object.ratingKey]).fetchone()[0]
    if extra_data:
        extra_data = re.sub(r"at%3AratingImage=.+?&|at%3AaudienceRatingImage=.+?&", '', extra_data)
        
        db_execute(db, "UPDATE metadata_items SET extra_data = ? WHERE id = ?",
                    [extra_data, plex_object.ratingKey])

    # set rating image to IMDB
    db_execute(db, "UPDATE metadata_items SET extra_data = ? || extra_data WHERE id = ?",
                ['at%3AratingImage=imdb%3A%2F%2Fimage%2Erating&', plex_object.ratingKey])
    # remove trailing ampersands, since this will cause trouble in the front-end
    db_execute(db, "UPDATE metadata_items SET extra_data = trim(extra_data, '&') WHERE id = ?", [plex_object.ratingKey])


def set_locked_fields(db, plex_object):
    user_fields = db_execute(db, "SELECT user_fields FROM metadata_items WHERE id = ? AND user_fields NOT LIKE ?", [plex_object.ratingKey, '%lockedFields=%5%']).fetchone()
    # if set, we need to update the locked fields
    if user_fields is not None:
        print("Locking rating field")
        fields = user_fields[0].split(",")

        for field in fields:
            if "lockedFields" in field:
                # remove lockedFields value temporary
                user_fields = re.sub(r"lockedFields=.+?", '', user_fields[0])
                db_execute(db, "UPDATE metadata_items SET user_fields = ? WHERE id = ?",
                            [user_fields, plex_object.ratingKey])
                # append the rating field to locked fields
                locked_fields = field + "|5"
                db_execute(db, "UPDATE metadata_items SET user_fields = ? || user_fields WHERE id = ?",
                            [locked_fields, plex_object.ratingKey])

def reset_rating(db, plex_object):
    db_execute(db, "UPDATE metadata_items SET rating = null WHERE id = ?", [plex_object.ratingKey])


def main(plex_id=None):
    # Connect to the Plex server
    print("Connecting to the Plex server at '{base_url}'...".format(base_url=PLEX_URL))
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except:
        print("No Plex server found at: {base_url}".format(base_url=PLEX_URL))
        print("Exiting script.")
        return

    libraries = []

    # Get list of movies from the Plex server
    for library_name in LIBRARY_NAMES:
        print("Retrieving a list of movies/shows from the '{library}' library in Plex...".format(library=library_name))
        try:
            libraries.append(plex.library.section(library_name))
        except:
            print("The '{library}' library does not exist in Plex.".format(library=library_name))
            print("Exiting script.")
            return

    imdb = Imdb()
    conn_db = sqlite3.connect(PLEX_DATABASE_FILE)
    db = conn_db.cursor()

    success = 0
    failed = 0

    for library in libraries:
        print("Processing " + library.title)
        for plex_object in library.all():
            # check if movie or show library
            if plex_object.type is "movie":
                is_movie_library = True
            else:
                is_movie_library = False
            # first do a check if we specified a plex id
            if plex_id is not None and plex_object.key not in "/library/metadata/" + plex_id:
                continue
            if 'imdb://' in plex_object.guid:
                imdb_id = plex_object.guid.split('imdb://')[1].split('?')[0]
            elif 'themoviedb://' in plex_object.guid:
                tmdb_id = plex_object.guid.split('themoviedb://')[1].split('?')[0]
                imdb_id = get_imdb_id_from_tmdb(tmdb_id, is_movie_library)
            elif 'thetvdb://' in plex_object.guid:
                tvdb_id = plex_object.guid.split('thetvdb://')[1].split('?')[0]
                imdb_id = get_imdb_id_from_tmdb_by_tvdb(tvdb_id)

            else:
                imdb_id = None
                
            if not imdb_id:
                print("Missing IMDB ID. Skipping media object '{pm.title}'.".format(pm=plex_object))
                reset_rating(db, plex_object)
                set_locked_fields(db, plex_object)
                failed = failed + 1
                continue

            print("Getting ratings for imdb id '{imdb_id}'".format(imdb_id=imdb_id))
            rating = None
            if OMDB_API_KEY:
                imdb_movie = get_imdb_rating_from_omdb(imdb_id)
                if imdb_movie is not None:
                    print("{im}\t{pm.title}\tOMDB".format(pm=plex_object, im=imdb_movie["imdb_rating"]))
                    rating = imdb_movie["imdb_rating"]
            if imdb_movie is None and imdb.title_exists(imdb_id):
                imdb_movie = imdb.get_title_ratings(imdb_id)
                print(imdb_movie)
                if imdb_movie is not None and "rating" in imdb_movie:
                    print("{im}\t{pm.title}".format(pm=plex_object, im=imdb_movie["rating"]))
                    rating = imdb_movie["rating"]
            if rating is None:
                print("Media not found on IMDB. Skipping '{pm.title} ({imdb_id})'.".format(pm=plex_object, imdb_id=imdb_id))
                reset_rating(db, plex_object)
                set_locked_fields(db, plex_object)
                failed = failed + 1
                continue
        
            if not DRY_RUN:
                set_imdb_image(db, plex_object, rating)
                set_locked_fields(db, plex_object)
                success = success + 1
                    
    conn_db.commit()
    db.close()

    
def db_execute(db, query, args):
    try:
        return db.execute(query, args)
    except sqlite3.OperationalError as e:
        print("Database Error: {}".format(e))
    except sqlite3.DatabaseError as e:
        print("Database Error: {}".format(e))

    return None
            
if __name__ == "__main__":
    # you can run the script for one movie/show when giving the plex id
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
    print("Done.")