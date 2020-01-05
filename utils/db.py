import sqlite3


def set_rating_and_imdb_image(db, plex_object, rating):
    """
    Set the rating and the use of IMDB rating image in extra_data
    :param db: the database in which to change the values
    :param plex_object: the plex object for which to set rating image
    :param rating: the rating which to set
    :return:
    """
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
    """
    Lock the fields for a specific Plex object so automatic metadata updater cannot override rating
    :param db: the database in which to change the values
    :param plex_object: the plex object for which to lock rating field
    :return:
    """
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
    """
    Method to reset the ratings for a plex object
    :param db: the database in which to change the values
    :param plex_object: the plex object for which to reset the rating
    :return:
    """
    db_execute(db, "UPDATE metadata_items SET rating = null WHERE id = ?", [plex_object.ratingKey])


def db_execute(db, query, args):
    try:
        return db.execute(query, args)
    except sqlite3.OperationalError as e:
        print("Database Error: {}".format(e))
    except sqlite3.DatabaseError as e:
        print("Database Error: {}".format(e))

    return None