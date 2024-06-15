import os
import os.path

CACHE_DIRECTORY = os.environ['CACHE_DIRECTORY']
STATE_DIRECTORY = os.environ['STATE_DIRECTORY']
BASE_URL = os.environ['BASE_URL']
DATABASE_URL = os.environ.get('DATABASE_URL', default=f"sqlite:///{os.path.join(STATE_DIRECTORY, 'moerderspiel.db')}")
