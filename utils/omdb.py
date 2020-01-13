import time

import omdb

from utils import config

OMDB_REQUEST_COUNT = 0  # DO NOT CHANGE


def get_imdb_rating_from_omdb(imdb_id):
    """
    Getting IMDB rating for imdb_id from OMDB
    :param imdb_id: the imdb_id of the rating
    :return: the whole object from OMDB including the rating
    """
    global OMDB_REQUEST_COUNT

    if not config.OMDB_API_KEY:
        return None
    else:
        omdb.set_default("apikey", config.OMDB_API_KEY)

    # Wait 10 seconds for the TMDb rate limit
    if OMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0

    try:
        media = omdb.imdbid(imdb_id, timeout=5)
    except:
        print("Error getting rating from OMDB. Trying again in few seconds")
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0
        return get_imdb_rating_from_omdb(imdb_id)

    OMDB_REQUEST_COUNT += 1

    # checking if there really is a rating and rating is not N/A
    if media is not None and 'imdb_rating' in media and media["imdb_rating"] != str('N/A'):
        return media
    else:
        return None


def get_season_from_omdb(imdb_id, season):
    """
    Getting specific season for IMDB id, including the ratings for each episode
    :param imdb_id: the IMDB item for which the items should be fetched
    :param season: the season for which to fetch episodes
    :return: a pair episode/rating
    """
    global OMDB_REQUEST_COUNT

    if not config.OMDB_API_KEY:
        return None
    else:
        omdb.set_default("apikey", config.OMDB_API_KEY)

    # Wait 10 seconds for the TMDb rate limit
    if OMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0

    try:
        season = omdb.imdbid(imdb_id, season=season)
    except:
        print("Error getting rating from OMDB. Trying again in few seconds")
        time.sleep(10)
        OMDB_REQUEST_COUNT = 0
        return get_season_from_omdb(imdb_id, season)

    OMDB_REQUEST_COUNT += 1

    # checking if there really is a rating and rating is not N/A
    if season is not None and "episodes" in season:
        episodes = {}
        for episode in season["episodes"]:
            episodes[episode["episode"]] = episode["imdb_rating"]
        return episodes
    else:
        return None
