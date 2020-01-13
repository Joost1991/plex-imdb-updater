import json
import logging
import time

from utils import config

import requests

TMDB_REQUEST_COUNT = 0  # DO NOT CHANGE


# Setup overrides, manually specify a imdb id for tvdb ids
tvdb_overrides = {}
with open("tvdb-imdb.txt") as overrides:
    for line in overrides:
        tvdb, imdb = line.partition("=")[::2]
        tvdb_overrides[tvdb.strip()] = str(imdb)


def get_imdb_id_from_tmdb(tmdb_id, is_movie=True):
    global TMDB_REQUEST_COUNT

    if not config.TMDB_API_KEY:
        return None

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {"api_key": config.TMDB_API_KEY}
    logging.debug("Fetching IMDB id from TMDB {tmdb_id}".format(tmdb_id=tmdb_id))
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
        logging.info("Got an override for {tvdb_id}".format(tvdb_id=tvdb_id))
        return tvdb_overrides[tvdb_id].rstrip()

    if not config.TMDB_API_KEY:
        return None

    # Wait 10 seconds for the TMDb rate limit
    if TMDB_REQUEST_COUNT >= 30:
        time.sleep(10)
        TMDB_REQUEST_COUNT = 0

    params = {"api_key": config.TMDB_API_KEY}

    url = "https://api.themoviedb.org/3/find/{tvdb_id}?external_source=tvdb_id".format(tvdb_id=tvdb_id)
    logging.debug("Fetching from TMDB with tvdb {tvdb_id}".format(tvdb_id=tvdb_id))
    r = requests.get(url, params=params)

    TMDB_REQUEST_COUNT += 1
    if r.status_code == 200:
        media_object = json.loads(r.text)

        # check if we did find TV results from TMDB
        if len(media_object["tv_results"]) == 0:
            logging.debug("Found no tv results based on tvdb id")
            return None

        # if we have found a TMDB id, we know need to get the IMDB id
        url = "https://api.themoviedb.org/3/tv/{tv_id}/external_ids".format(tv_id=media_object["tv_results"][0]["id"])
        logging.debug("Fetching external IMDB id from TMDB {tv_id}".format(tv_id=media_object["tv_results"][0]["id"]))
        r = requests.get(url, params=params)

        if r.status_code == 200:
            media_object = json.loads(r.text)
            if media_object['imdb_id'] is not None and media_object['imdb_id'] is not "":
                return media_object['imdb_id']
            else:
                return None
        return None
    else:
        logging.debug("Did not find by tvdb")
        return None
