import datetime

from peewee import SqliteDatabase, Model, IntegerField, CharField, DateTimeField, DoubleField

DATABASE = 'db.sqlite'

# create a peewee database instance -- our models will use this database to
# persist information
database = SqliteDatabase(DATABASE)


# model definitions -- the standard "pattern" is to define a base model class
# that specifies which database to use.  then, any subclasses will automatically
# use the correct storage. for more information, see:
# http://charlesleifer.com/docs/peewee/peewee/models.html#model-api-smells-like-django
class BaseModel(Model):
    plex_id = IntegerField(primary_key=True, unique=True)
    title = CharField()
    imdb_id = CharField(null=True)
    tmdb_id = IntegerField(null=True)
    rating = DoubleField(null=True)
    last_update = DateTimeField(default=datetime.datetime.now)
    release_date = DateTimeField(null=True)

    class Meta:
        database = database


class Show(BaseModel):
    tvdb_id = IntegerField(null=True)


class Season(BaseModel):
    number = IntegerField()


class Episode(BaseModel):
    parent_plex_id = IntegerField()
    episode = IntegerField()
    season = IntegerField()


class Movie(BaseModel):
    tmdb_id = IntegerField(null=True)


# simple utility function to create tables
def create_tables():
    with database:
        database.create_tables([Show, Season, Movie, Episode])