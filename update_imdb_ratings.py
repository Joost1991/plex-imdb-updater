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
from datetime import datetime, timedelta
from plexapi.server import PlexServer
from imdbpie import Imdb
from models import create_tables, Movie, Show, Episode
from utils import omdb, db, tmdb, config, imdb

# EDIT SETTINGS ###
# Plex settings
PLEX_URL = 'http://localhost:32400'
PLEX_TOKEN = ''
LIBRARY_NAMES = []
PLEX_DATABASE_FILE = "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Plug-in Support/Databases/com.plexapp.plugins.library.db"

# Updater settings
EPISODE_RATINGS = True  # Whether to fetch episode ratings
EPISODE_RATINGS_SOURCE = "imdb"  # How to fetch the episode ratings. Via OMDB or directly from IMDB
DRY_RUN = True  # Dry run without modifying the database (True or False)


def main(plex_id=None):
    db.create_connection("db.sqlite")
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

    if not DRY_RUN:
        conn_db = sqlite3.connect(PLEX_DATABASE_FILE)
        database = conn_db.cursor()
    else:
        database = None

    success = 0
    failed = 0

    for library in libraries:
        print("Processing " + library.title)
        for plex_object in library.all():
            # check if movie or show library
            if plex_object.TYPE is "movie":
                is_movie_library = True
                if not should_update_media(plex_object.TYPE, plex_object.ratingKey):
                    continue
            else:
                is_movie_library = False
            # first do a check if we specified a plex id
            if plex_id is not None and plex_object.key not in "/library/metadata/" + plex_id:
                continue

            # resolve plex object to right identifiers
            imdb_id, tmdb_id, tvdb_id = resolve_ids(is_movie_library, plex_object.guid)

            # if no imdb_id is found for plex guid, reset all ratings
            if not imdb_id:
                print("Missing IMDB ID. Skipping media object '{pm.title}'.".format(pm=plex_object))
                if not DRY_RUN:
                    db.reset_rating(database, plex_object)
                    db.set_locked_fields(database, plex_object)
                failed = failed + 1
                continue

            print("Getting ratings for imdb id '{imdb_id}'".format(imdb_id=imdb_id))
            rating = None
            if config.OMDB_API_KEY:
                if should_update_media(plex_object.TYPE, plex_object.ratingKey):
                    imdb_object = omdb.get_imdb_rating_from_omdb(imdb_id)
                    if imdb_object is not None:
                        print("{im}\t{pm.title}\tOMDB".format(pm=plex_object, im=imdb_object["imdb_rating"]))
                        rating = imdb_object["imdb_rating"]

                    if imdb_object is None and imdb.title_exists(imdb_id):
                        imdb_object = imdb.get_title_ratings(imdb_id)
                        if imdb_object is not None and "rating" in imdb_object:
                            print("{im}\t{pm.title}".format(pm=plex_object, im=imdb_object["rating"]))
                            rating = imdb_object["rating"]

                    if rating is None and not DRY_RUN:
                        print("Media not found on IMDB. Skipping '{pm.title} ({imdb_id})'.".format(pm=plex_object,
                                                                                                   imdb_id=imdb_id))
                        if not DRY_RUN:
                            db.reset_rating(database, plex_object)
                            db.set_locked_fields(database, plex_object)
                        failed = failed + 1
                        continue

                    if is_movie_library:
                        db_movie = Movie.select().where(Movie.plex_id == plex_object.ratingKey)
                        if db_movie.exists():
                            Movie.save(
                                title=plex_object.title,
                                plex_id=plex_object.ratingKey,
                                imdb_id=imdb_id,
                                rating=rating,
                                tmdb_id=tmdb_id,
                                release_date=plex_object.originallyAvailableAt,
                                last_update=datetime.now()
                            )
                        else:
                            Movie.create(
                                title=plex_object.title,
                                plex_id=plex_object.ratingKey,
                                imdb_id=imdb_id,
                                rating=rating,
                                tmdb_id=tmdb_id,
                                release_date=plex_object.originallyAvailableAt
                            )
                    else:
                        db_show = Show.select().where(Show.plex_id == plex_object.ratingKey)
                        if db_show.exists():
                            Show.save(
                                title=plex_object.title,
                                plex_id=plex_object.ratingKey,
                                imdb_id=imdb_id,
                                rating=rating,
                                tvdb_id=tvdb_id,
                                release_date=plex_object.originallyAvailableAt,
                                last_update=datetime.now()
                            )
                        else:
                            Show.create(
                                title=plex_object.title,
                                plex_id=plex_object.ratingKey,
                                imdb_id=imdb_id,
                                rating=rating,
                                release_date=plex_object.originallyAvailableAt,
                                tvdb_id=tvdb_id
                            )

                    if not DRY_RUN:
                        db.set_rating_and_imdb_image(database, plex_object, rating)
                        db.set_locked_fields(database, plex_object)
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
                            imdb_episodes = None
                            for episode in season.episodes():
                                db_episode = Episode.select().where(Episode.plex_id == episode.ratingKey)
                                if not db_episode.exists():
                                    if imdb_episodes is None:
                                        imdb_episodes = imdb.get_season_from_imdb(imdb_id, season.index)
                                    if update_imdb_episode_rating(database, episode,
                                                                  imdb_episodes, plex_object, season, False):
                                        print("Created episode '{e.title}' '{e.index}' "
                                              "with new ratings".format(e=episode))
                                        success = success + 1
                                    else:
                                        failed = failed + 1
                                else:
                                    # check if we need to update this item
                                    if db_episode.get().last_update > datetime.now() - timedelta(days=-7):
                                        if imdb_episodes is None:
                                            imdb_episodes = imdb.get_season_from_imdb(imdb_id, season.index)
                                        if update_imdb_episode_rating(database, episode,
                                                                      imdb_episodes, plex_object,
                                                                      season):
                                            print("Update episode '{e.title}' '{e.index}' "
                                                  "with new ratings".format(e=episode))
                                            success = success + 1
                                        else:
                                            failed = failed + 1

        # commit the changes after each library
        if not DRY_RUN:
            conn_db.commit()
    if not DRY_RUN:
        database.close()
    print("Finished updating. {success} updated and {failed} failed".format(success=success, failed=failed))


def update_imdb_episode_rating(database, episode, imdb_episodes, plex_object, season, exists=True):
    """
    Update episode rating from IMDB
    :param database: connection to the database
    :param episode: the episode object from plex
    :param imdb_episodes: the episode ratings from imdb
    :param plex_object: the plex object from the parent show
    :param season: the season of this episode
    :param exists: whether the media already exists in local db
    :return: true if update succeeds, false if not
    """
    if episode.index in imdb_episodes:
        if imdb_episodes[episode.index] == 'N/A':
            if not DRY_RUN:
                db.reset_rating(database, episode)
                db.set_locked_fields(database, episode)
            print("Episode '{e.title}' '{e.index}' has no rating available".format(
                e=episode))
            return False
        else:
            if not DRY_RUN:
                db.set_rating_and_imdb_image(database, episode,
                                             imdb_episodes[episode.index]["rating"])
                db.set_locked_fields(database, episode)
            # create episode in database
            if not exists:
                Episode.create(
                    parent_plex_id=plex_object.ratingKey,
                    plex_id=episode.ratingKey,
                    imdb_id=imdb_episodes[episode.index]["imdb_id"],
                    title=episode.title,
                    season=season.index,
                    episode=episode.index,
                    release_date=episode.originallyAvailableAt,
                    rating=imdb_episodes[episode.index]["rating"]
                )
            else:
                Episode.save(
                    parent_plex_id=plex_object.ratingKey,
                    plex_id=episode.ratingKey,
                    imdb_id=imdb_episodes[episode.index]["imdb_id"],
                    title=episode.title,
                    season=season.index,
                    episode=episode.index,
                    release_date=episode.originallyAvailableAt,
                    rating=imdb_episodes[episode.index]["rating"]
                )
            return True
    else:
        if not DRY_RUN:
            db.reset_rating(database, episode)
            db.set_locked_fields(database, episode)
        print("Episode '{e.title}' '{e.index}' not found. Cannot update".format(
            e=episode))
        if not exists:
            Episode.create(
                parent_plex_id=plex_object.ratingKey,
                plex_id=episode.ratingKey,
                title=episode.title,
                season=season.index,
                episode=episode.index,
                release_date=episode.originallyAvailableAt
            )
        else:
            Episode.save(
                parent_plex_id=plex_object.ratingKey,
                plex_id=episode.ratingKey,
                title=episode.title,
                season=season.index,
                episode=episode.index,
                release_date=episode.originallyAvailableAt,
            )
        return False
    return False


def should_update_media(type, plex_id):
    """
    Whether given plex media object rating should be updated
    :param type: the type of media
    :param plex_id: the plex id
    :return: True if should be updated, False if not
    """
    if type is "movie":
        db_movie = Movie.select().where(Movie.plex_id == plex_id)
        if db_movie.exists():
            if db_movie.get().last_update > datetime.now() - timedelta(days=-7):
                return True
        else:
            return True
    elif type is "show":
        db_show = Show.select().where(Show.plex_id == plex_id)
        if db_show.exists():
            if db_show.get().last_update > datetime.now() - timedelta(days=-7):
                return True
        else:
            return True
    elif type is "episode":
        db_episode = Episode.select().where(Episode.plex_id == plex_id)
        if db_episode.exists():
            if db_episode.get().last_update > datetime.now() - timedelta(days=-7):
                return True
        else:
            return True
    return False


def resolve_ids(is_movie, guid):
    """
    Method to resolve ID from a Plex GUID
    :param is_movie_library: whether given GUID is a movie
    :param plex_object: the plex object containing the GUID
    :return:
    """
    tmdb_id = None
    tvdb_id = None
    if 'imdb://' in guid:
        imdb_id = guid.split('imdb://')[1].split('?')[0]
    elif 'themoviedb://' in guid:
        tmdb_id = guid.split('themoviedb://')[1].split('?')[0]
        imdb_id = tmdb.get_imdb_id_from_tmdb(tmdb_id, is_movie)
    elif 'thetvdb://' in guid:
        tvdb_id = guid.split('thetvdb://')[1].split('?')[0]
        imdb_id = tmdb.get_imdb_id_from_tmdb_by_tvdb(tvdb_id)
    else:
        imdb_id = None
    return imdb_id, tmdb_id, tvdb_id


if __name__ == "__main__":
    create_tables()
    # you can run the script for one movie/show when giving the plex id
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
    print("Done.")
