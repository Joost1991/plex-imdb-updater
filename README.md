# Plex IMDB rating updater
## Overview
This script updates movies and tv shows with recent IMDB ratings. It fetches the ratings 
either directly via IMDBPie or it's fetches it via OMDB. It directly edits the values in the
database of Plex.

To make sure Plex doesn't overwrite the ratings the rating field is set as a locked field.

Officially Plex doesn't support IMDB ratings for TV Shows, but with the script you can fetch IMDB ratings
for TV shows as well. Full support on the web app, but some apps for devices don't show the IMDB icon next to
the rating since it's not officially supported.

## Installation
Checkout the project, create a virtualenv and download dependencies via `requirements.txt`. 
Optional you can set your own TMDb and/or OMDB api keys to increase matching and speed up the matching . After
that you can simply run the project by executing the `update_imdb_ratings.py`. 

Don't forget to turn set `DRY_RUN` to `True` when you want to commit the ratings to the Plex DB.

To make sure you'll get up-to-date ratings you can setup a cronjob to run this script.
