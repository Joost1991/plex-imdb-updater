# -*- coding: utf-8 -*-

# ------------------------------------------------------------------------------
#
#             Plex movie and tv shows ratings script inspired on
#             script by /u/SwiftPanda16, extended by /u/Toastjuh
#
#                         *** Use at your own risk! ***
#   *** I am not responsible for damages to your Plex server or libraries. ***
#
# ------------------------------------------------------------------------------

# Requires: plexapi, imdbpie, omdb

import sys
import sqlite3
from plexapi.server import PlexServer
from imdbpie import Imdb
from utils import omdb, db, tmdb


# EDIT SETTINGS ###
# Plex settings
PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = ''
LIBRARY_NAMES = []
PLEX_DATABASE_FILE = "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"

# Updater settings
EPISODE_RATINGS = True  # Whether to fetch episode ratings
EPISODE_RATINGS_SOURCE = "imdb"  # How to fetch the episode ratings. Via OMDB or directly from IMDB
DRY_RUN = False  # Dry run without modifying the database (True or False)

# API Keys
# Optional: The Movie Database details ###
# To enable fetching TVDB and TMDB items ###
TMDB_API_KEY = ''
# Optional: The Open Movie Database details ###
# Enter your OMDIB API key.
# Scraping IMDb can be very slow process. This speeds up the process by getting the IMDB rating directly from OMDB
OMDB_API_KEY = ''


def main(plex_id=None):
    global TMDB_API_KEY
    global OMDB_API_KEY

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
    database = conn_db.cursor()

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
                imdb_id = tmdb.get_imdb_id_from_tmdb(tmdb_id, is_movie_library)
            elif 'thetvdb://' in plex_object.guid:
                tvdb_id = plex_object.guid.split('thetvdb://')[1].split('?')[0]
                imdb_id = tmdb.get_imdb_id_from_tmdb_by_tvdb(tvdb_id)

            else:
                imdb_id = None

            if not imdb_id:
                print("Missing IMDB ID. Skipping media object '{pm.title}'.".format(pm=plex_object))
                db.reset_rating(database, plex_object)
                db.set_locked_fields(database, plex_object)
                failed = failed + 1
                continue

            print("Getting ratings for imdb id '{imdb_id}'".format(imdb_id=imdb_id))
            rating = None
            if OMDB_API_KEY:
                imdb_movie = omdb.get_imdb_rating_from_omdb(imdb_id)
                if imdb_movie is not None:
                    print("{im}\t{pm.title}\tOMDB".format(pm=plex_object, im=imdb_movie["imdb_rating"]))
                    rating = imdb_movie["imdb_rating"]
                    # now try to fetch seasons
                    if not is_movie_library:
                        for season in plex_object.seasons():
                            # don't do anything with specials
                            if season.index is 0:
                                print("Skipping specials")
                                continue
                            if EPISODE_RATINGS:
                                print("Getting episodes for {p.title} for season {season}".format(p=plex_object,
                                                                                                  season=season.index))
                                if EPISODE_RATINGS_SOURCE is "imdb":
                                    imdb_episodes = tmdb.get_season_from_imdb(imdb, imdb_id, season.index)
                                    print(imdb_episodes)
                                    for episode in season.episodes():
                                        if episode.index in imdb_episodes:
                                            if imdb_episodes[episode.index] == 'N/A':
                                                db.reset_rating(database, episode)
                                                db.set_locked_fields(database, episode)
                                                failed = failed + 1
                                            else:
                                                db.set_rating_and_imdb_image(database, episode,
                                                                             imdb_episodes[episode.index])
                                                db.set_locked_fields(database, episode)
                                                success = success + 1
                                                print("Update episode '{e.title}' '{e.index}' with new ratings".format(
                                                    e=episode))
                                        else:
                                            db.reset_rating(database, episode)
                                            db.set_locked_fields(database, episode)
                                            failed = failed + 1
                                            print("Episode '{e.title}' '{e.index}' not in OMDB. Cannot update".format(
                                                e=episode))
                                elif EPISODE_RATINGS_SOURCE is "omdb":
                                    episodes_metadata = omdb.get_season_from_omdb(imdb_id, season.index)
                                    for episode in season.episodes():
                                        if str(episode.index) in episodes_metadata:
                                            if episodes_metadata[str(episode.index)] == 'N/A':
                                                db.reset_rating(database, episode)
                                                db.set_locked_fields(database, episode)
                                                failed = failed + 1
                                            else:
                                                db.set_rating_and_imdb_image(database, episode,
                                                                             episodes_metadata[str(episode.index)])
                                                db.set_locked_fields(database, episode)
                                                success = success + 1
                                                print("Update episode '{e.title}' '{e.index}' with new ratings".format(
                                                    e=episode))
                                        else:
                                            db.reset_rating(database, episode)
                                            db.set_locked_fields(database, episode)
                                            failed = failed + 1
                                            print("Episode '{e.title}' '{e.index}' not in OMDB. Cannot update".format(
                                                e=episode))
                if imdb_movie is None and imdb.title_exists(imdb_id):
                    imdb_movie = imdb.get_title_ratings(imdb_id)
                    print(imdb_movie)
                    if imdb_movie is not None and "rating" in imdb_movie:
                        print("{im}\t{pm.title}".format(pm=plex_object, im=imdb_movie["rating"]))
                        rating = imdb_movie["rating"]
            if rating is None:
                print("Media not found on IMDB. Skipping '{pm.title} ({imdb_id})'.".format(pm=plex_object,
                                                                                           imdb_id=imdb_id))
                db.reset_rating(database, plex_object)
                db.set_locked_fields(database, plex_object)
                failed = failed + 1
                continue

            if not DRY_RUN:
                db.set_rating_and_imdb_image(database, plex_object, rating)
                db.set_locked_fields(database, plex_object)
                success = success + 1

    conn_db.commit()
    database.close()


if __name__ == "__main__":
    # you can run the script for one movie/show when giving the plex id
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
    print("Done.")
