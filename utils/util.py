import logging
from datetime import datetime, timedelta

from update_imdb_ratings import THRESHOLD_SHORT, THRESHOLD_NORMAL


logger = logging.getLogger("plex-imdb-updater")


def is_short_treshold(release_date):
    """
    Whether it is short or long threshold. Looks at the given date and checks if
    the release date is no longer than 14 days old.
    :param release_date: the release date to check
    :return: true if not older than 15 days
    """
    if release_date is not None and release_date > datetime.now() - timedelta(days=14):
        return True
    else:
        return False


def check_media_needs_update(db_media_object, plex_object, check_rating=True):
    """
    Check whether a media needs to be updated based on last update time and rating
    :param db_media_object: the local DB object
    :param plex_object: the plex DB object
    :param check_rating: whether to check for rating. Default is True
    :return: True if update is required, False if not
    """
    if is_short_treshold(db_media_object.get().release_date):
        if db_media_object.get().last_update < datetime.now() - THRESHOLD_SHORT:
            logger.debug("Update {title} because last update short threshold".format(title=db_media_object.get().title))
            return True
        # if exists in local DB but not in Plex DB, it's not properly updated or updated from the outside
        elif check_rating and db_media_object.get().rating != plex_object.rating:
            logger.debug("Update {title} because rating doesn't match Plex".format(title=db_media_object.get().title))
            return True
    else:
        if db_media_object.get().last_update < datetime.now() - THRESHOLD_NORMAL:
            logger.debug("Update {title} because last update long threshold".format(title=db_media_object.get().title))
            return True
        # if exists in local DB but not in Plex DB, it's not properly updated or updated from the outside
        elif check_rating and db_media_object.get().rating != plex_object.rating:
            logger.debug("Update {title} because rating doesn't match Plex".format(title=db_media_object.get().title))
            return True
    return False
