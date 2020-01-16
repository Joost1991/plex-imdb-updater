from datetime import datetime, timedelta


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
