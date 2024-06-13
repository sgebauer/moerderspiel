import os

CACHE_DIRECTORY = os.environ['CACHE_DIRECTORY']
STATE_DIRECTORY = os.environ['STATE_DIRECTORY']
BASE_URL = os.environ['BASE_URL']
DATABASE_URL = os.environ.get('DATABASE_URL', default=f"sqlite:///{STATE_DIRECTORY}/moerderspiel.db")
