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
import csv
import gzip
import io
import logging
import sys
import sqlite3
from datetime import datetime, timedelta
from time import sleep

import requests
from plexapi.server import PlexServer
from imdbpie import Imdb
from tqdm import tqdm

from models import create_tables, Movie, Show, Episode, Season
from utils import omdb, db, tmdb, config, imdb, util

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
DEBUG_LEVEL = logging.DEBUG
THRESHOLD_SHORT = timedelta(days=1)
THRESHOLD_NORMAL = timedelta(days=14)


def fetch_imdb_ratings():
    """
    Load newest IMDb ratings into memory
    :return: a array of imdb ratings, key is IMDb ID, value is rating
    """
    response = requests.get("https://datasets.imdbws.com/title.ratings.tsv.gz")
    file = io.BytesIO(response.content)
    ratings = {}
    with gzip.open(file, mode='rt') as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        for line in reader:
            ratings[line[0]] = line[1]
    return ratings


def main(plex_id=None, force=False):
    logger = logging.getLogger("plex-imdb-updater")
    db.create_connection("db.sqlite")
    # Connect to the Plex server
    logger.info("Connecting to the Plex server at '{base_url}'...".format(base_url=PLEX_URL))
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
    except:
        logger.error("No Plex server found at: {base_url}".format(base_url=PLEX_URL))
        return

    libraries = []

    # Get list of movies from the Plex server
    for library_name in LIBRARY_NAMES:
        logger.info("Retrieving a list of movies/shows from the '{library}' library in Plex...".format(library=library_name))
        try:
            libraries.append(plex.library.section(library_name))
        except:
            logger.warning("The '{library}' library does not exist in Plex.".format(library=library_name))
            continue

    if not DRY_RUN:
        conn_db = sqlite3.connect(PLEX_DATABASE_FILE)
        conn_db.isolation_level = None
        database = conn_db.cursor()
    else:
        database = None

    success = 0
    created = 0
    failed = 0

    # fetching ratings from IMDb dataset
    logger.info("Fetching latest ratings from IMDb")
    imdb_ratings = fetch_imdb_ratings()
    logger.info("Done fetching latest ratings from IMDb")

    for library in libraries:
        pbar = tqdm(library.all(), postfix=["", ""])
        pbar.set_description("Processing " + library.title)
        for plex_object in pbar:
            pbar.postfix[0] = plex_object.title
            pbar.postfix[1] = "Processing"
            # first do a check if we specified a plex id
            if plex_id is not None and str(plex_object.ratingKey) != plex_id:
                continue
            # check if movie or show library
            if plex_object.TYPE is "movie":
                is_movie_library = True
            else:
                is_movie_library = False

            # resolve plex object to right identifiers
            imdb_id, tmdb_id, tvdb_id = resolve_ids(is_movie_library, plex_object, force, pbar)

            # if no imdb_id is found for plex guid, reset all ratings
            if not imdb_id:
                logger.debug("Missing IMDB ID. Skipping media object '{pm.title}'.".format(pm=plex_object))
                if not DRY_RUN:
                    db.reset_rating(database, plex_object)
                    db.set_locked_fields(database, plex_object)
                failed = failed + 1
                continue

            # Check if rating is in IMDb
            rating = None
            if imdb_id in imdb_ratings:
                rating = imdb_ratings[imdb_id]

            # reset in database if nothing could be fetched
            if rating is None and not DRY_RUN:
                logger.warning("Media not found in fetched IMDB ratings. Skipping '{pm.title} ({imdb_id})'.".format(
                    pm=plex_object, imdb_id=imdb_id))
                if not DRY_RUN:
                    db.reset_rating(database, plex_object)
                    db.set_locked_fields(database, plex_object)
                failed = failed + 1
                continue
            else:
                logger.debug("Updating ratings for '{title}'".format(title=plex_object.title))
                if is_movie_library:
                    # do update in local library for future reference
                    db_movie = Movie.select().where(Movie.plex_id == plex_object.ratingKey)
                    if db_movie.exists():
                        db.update_db_rating(db_movie.get(), plex_object.title, rating, imdb_id,
                                            plex_object.originallyAvailableAt)
                        success = success + 1
                    else:
                        Movie.create(
                            title=plex_object.title,
                            plex_id=plex_object.ratingKey,
                            imdb_id=imdb_id,
                            rating=rating,
                            tmdb_id=tmdb_id,
                            release_date=plex_object.originallyAvailableAt
                        )
                        created = created + 1
                else:
                    # do update in local library for future reference
                    db_show = Show.select().where(Show.plex_id == plex_object.ratingKey)
                    if db_show.exists():
                        db.update_db_rating(db_show.get(), plex_object.title, rating, imdb_id,
                                            plex_object.originallyAvailableAt, tmdb_id)
                        success = success + 1
                    else:
                        Show.create(
                            title=plex_object.title,
                            plex_id=plex_object.ratingKey,
                            imdb_id=imdb_id,
                            rating=rating,
                            release_date=plex_object.originallyAvailableAt,
                            tvdb_id=tvdb_id
                        )
                        created = created + 1

                if not DRY_RUN:
                    # if not dry run, do a update in Plex' DB
                    db.set_rating_and_imdb_image(database, plex_object, rating)
                    db.set_locked_fields(database, plex_object)
            # now try to fetch seasons
            if not is_movie_library:
                for season in plex_object.seasons():
                    # don't do anything with specials
                    if season.index is 0:
                        logger.debug("Skipping specials")
                        continue
                    # check if enabled in settings
                    db_season = Season.select().where(Season.plex_id == plex_object.ratingKey
                                                      and Season.number == season.index)
                    if EPISODE_RATINGS and util.check_media_needs_update(db_season, None, False):
                        logger.debug("Getting episodes for {p.title} for season {season}".format(
                            p=plex_object, season=season.index))
                        # First update all episodes from the season
                        imdb_episodes = imdb.get_season_from_imdb(imdb_id, season.index)
                        for episode in season.episodes():
                            update_success = update_episode_rating(database, episode, imdb_ratings, imdb_episodes,
                                                                   plex_object, season)
                            if update_success:
                                success = success + 1
                            else:
                                failed = failed + 1
            if not DRY_RUN:
                conn_db.commit()
    if not DRY_RUN:
        database.close()
    logger.info("Finished updating. {created} created, {success} updated and {failed} failed".format(created=created,
                                                                                                     success=success,
                                                                                                     failed=failed))


def update_episode_rating(database, episode, imdb_ratings, imdb_episodes, plex_object, season):
    """
    Update the episode rating if it is outdated
    :param database: connection to the Plex DB
    :param episode: the episode object from Plex
    :param imdb_ratings: all fetched IMDb ratings
    :param imdb_episodes: the IMDB key/value ratings
    :param plex_object: the parent plex object
    :param season: the season from which this episode is beloning to
    :return: True if updated, False if not
    """
    db_episode = Episode.select().where(Episode.plex_id == episode.ratingKey)
    if not db_episode.exists():
        if update_imdb_episode_rating(database, episode, imdb_ratings, imdb_episodes, plex_object, season):
            logger.debug("Created episode '{e.title}' '{e.index}' with new ratings".format(e=episode))
            return True
        else:
            return False
    else:
        if update_imdb_episode_rating(database, episode, imdb_ratings, imdb_episodes, plex_object, season, db_episode):
            logger.debug("Update episode '{e.title}' '{e.index}' with new ratings".format(e=episode))
            return True
        else:
            return False
    return False


def update_imdb_episode_rating(database, episode, imdb_ratings, imdb_episodes, plex_object, season, db_episode=None):
    """
    Update episode rating from IMDB
    :param database: connection to the database
    :param episode: the episode object from plex
    :param imdb_ratings: the ratings from imdb by imdb id
    :param plex_object: the plex object from the parent show
    :param season: the season of this episode
    :param exists: whether the media already exists in local db
    :return: true if update succeeds, false if not
    """
    if db_episode is not None:
        if db_episode.get().imdb_id in imdb_ratings:
            db.update_db_rating(db_episode.get(), episode.title, imdb_ratings[db_episode.get().imdb_id],
                                db_episode.get().imdb_id, episode.originallyAvailableAt)
            if not DRY_RUN:
                db.set_rating_and_imdb_image(database, episode,
                                             imdb_ratings[db_episode.get().imdb_id])
                db.set_locked_fields(database, episode)
            return True
        else:
            if episode.index not in imdb_episodes:
                if not DRY_RUN:
                    db.reset_rating(database, episode)
                    db.set_locked_fields(database, episode)
                logger.debug("Episode '{e.title}' '{e.index}' has no rating available".format(
                    e=episode))
                return False
            else:
                logger.debug("{title} is fetched from IMDb but not in IMDb dataset".format(title=episode.title))
                db.update_db_rating(db_episode.get(), episode.title, imdb_episodes[episode.index]["rating"],
                                    imdb_episodes[episode.index]["imdb_id"], episode.originallyAvailableAt)
                if not DRY_RUN:
                    db.set_rating_and_imdb_image(database, episode,
                                                 imdb_episodes[episode.index]["rating"])
                    db.set_locked_fields(database, episode)
                return True
    else:
        # check if episode index is there and it's in the map with imdb ratings
        if episode.index in imdb_episodes and imdb_episodes[episode.index]["imdb_id"] in imdb_ratings:
            Episode.create(
                parent_plex_id=plex_object.ratingKey,
                plex_id=episode.ratingKey,
                imdb_id=imdb_episodes[episode.index]["imdb_id"],
                title=episode.title,
                season=season.index,
                episode=episode.index,
                release_date=episode.originallyAvailableAt,
                rating=imdb_ratings[imdb_episodes[episode.index]["imdb_id"]]
            )
            if not DRY_RUN:
                db.set_rating_and_imdb_image(database, episode,
                                             imdb_ratings[imdb_episodes[episode.index]["imdb_id"]])
                db.set_locked_fields(database, episode)
            return True
        elif episode.index in imdb_episodes:
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
            if not DRY_RUN:
                db.set_rating_and_imdb_image(database, episode,
                                             imdb_episodes[episode.index]["rating"])
                db.set_locked_fields(database, episode)
            return True
        else:
            # could not resolve. Create episode object without rating
            Episode.create(
                parent_plex_id=plex_object.ratingKey,
                plex_id=episode.ratingKey,
                title=episode.title,
                season=season.index,
                episode=episode.index,
                release_date=episode.originallyAvailableAt
            )
            if not DRY_RUN:
                db.reset_rating(database, episode)
                db.set_locked_fields(database, episode)
            return False


def resolve_ids(is_movie, plex_object, force, pbar=None):
    """
    Method to resolve ID from a Plex GUID
    :param is_movie_library: whether given GUID is a movie
    :param plex_object: the plex object containing the GUID
    :param force: if forced update we want to resolve it again
    :param pbar: the progress bar object
    :return:
    """
    tmdb_id = None
    tvdb_id = None
    # first try to resolve via Plex ID if fetched earlier
    if plex_object.TYPE is "movie" and not force:
        db_movie = Movie.select().where(Movie.plex_id == plex_object.ratingKey)
        if db_movie.exists():
            imdb_id = db_movie.get().imdb_id
            tmdb_id = db_movie.get().tmdb_id
            logger.debug("Resolved via existing db entry")
            return imdb_id, tmdb_id, tvdb_id
    elif not force:
        db_show = Show.select().where(Show.plex_id == plex_object.ratingKey)
        if db_show.exists():
            imdb_id = db_show.get().imdb_id
            tmdb_id = db_show.get().tmdb_id
            tvdb_id = db_show.get().tvdb_id
            logger.debug("Resolved via existing db entry")
            return imdb_id, tmdb_id, tvdb_id
    # if not yet resolved it's a new item
    if 'imdb://' in plex_object.guid:
        imdb_id = plex_object.guid.split('imdb://')[1].split('?')[0]
    elif 'themoviedb://' in plex_object.guid:
        tmdb_id = plex_object.guid.split('themoviedb://')[1].split('?')[0]
        imdb_id = tmdb.get_imdb_id_from_tmdb(tmdb_id, is_movie, pbar)
    elif 'thetvdb://' in plex_object.guid:
        tvdb_id = plex_object.guid.split('thetvdb://')[1].split('?')[0]
        imdb_id = tmdb.get_imdb_id_from_tmdb_by_tvdb(tvdb_id, pbar)
    else:
        imdb_id = None
    return imdb_id, tmdb_id, tvdb_id


def should_update_media(type, plex_object):
    """
    Whether given plex media object rating should be updated
    :param type: the type of media
    :param plex_object: the plex object containing rating and ratingKey
    :return: True if should be updated, False if not
    """
    if type is "movie":
        db_movie = Movie.select().where(Movie.plex_id == plex_object.ratingKey)
        if db_movie.exists():
            if util.check_media_needs_update(db_movie, plex_object):
                return True
        else:
            return True
    elif type is "show":
        # getting show and episodes from show
        db_show = Show.select().where(Show.plex_id == plex_object.ratingKey)
        db_episodes = Episode.select().where(Episode.parent_plex_id == plex_object.ratingKey)
        if db_show.exists():
            if util.check_media_needs_update(db_show, plex_object):
                return True
            # if show doesn't need update, maybe a single episode need one
            for episode in db_episodes:
                if util.check_media_needs_update(episode, plex_object, check_rating=False):
                    return True
        else:
            return True
    elif type is "episode":
        db_episode = Episode.select().where(Episode.plex_id == plex_object.ratingKey)
        if db_episode.exists():
            if util.check_media_needs_update(db_episode, plex_object):
                return True
        else:
            return True
    return False


if __name__ == "__main__":
    logger = logging.getLogger("plex-imdb-updater")
    logger.setLevel(DEBUG_LEVEL)
    logger.addHandler(logging.FileHandler("plex-imdb-updater.log"))
    logger.addHandler(logging.StreamHandler(sys.stdout))
    create_tables()
    # you can run the script for one movie/show when giving the plex id
    if len(sys.argv) > 1:
        logger.info("Getting rating for single item")
        main(sys.argv[1], force=True)
    else:
        main()
