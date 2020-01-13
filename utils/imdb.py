import logging

from imdbpie import Imdb

imdb = None
logger = logging.getLogger(__name__)


def get_season_from_imdb(imdb_id, season):
    """
    Getting season ratings from IMDB, rating each episodes individually
    :param imdb_id: the imdb_id of the show
    :param season: which season of the show to fetch ratings for
    :return: a pair, episode number/rating
    """
    global imdb
    if imdb is None:
        imdb = Imdb()
    season = imdb.get_title_episodes_detailed(imdb_id, season=season)

    # checking if there really is a rating and rating is not N/A
    if season is not None and "episodes" in season:
        episodes = {}
        for episode in season["episodes"]:
            if 'id' in episode:
                imdb_id = episode["id"].replace('/', '').replace('title', '')
            else:
                imdb_id = None
            episodes[episode["episodeNumber"]] = {"rating": episode["rating"], "imdb_id": imdb_id}
        return episodes
    else:
        return None


def title_exists(imdb_id):
    global imdb
    if imdb is None:
        imdb = Imdb()

    return imdb.title_exists(imdb_id)


def get_title_ratings(imdb_id):
    global imdb
    if imdb is None:
        imdb=Imdb()

    return imdb.get_title_ratings(imdb_id)
