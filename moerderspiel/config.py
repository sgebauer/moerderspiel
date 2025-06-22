import os
import os.path
import socket

CACHE_DIRECTORY = os.environ['CACHE_DIRECTORY']
STATE_DIRECTORY = os.environ['STATE_DIRECTORY']
BASE_URL = os.environ['BASE_URL']
DATABASE_URL = os.environ.get('DATABASE_URL', default=f"sqlite:///{os.path.join(STATE_DIRECTORY, 'moerderspiel.db')}")
SECRET_KEY = os.environ['SECRET_KEY']
WORDGEN_CORPUS = os.environ.get('WORDGEN_CORPUS', default='/usr/share/dict/ngerman')

# Redis configuration for task queue
REDIS_URL = os.environ.get('REDIS_URL', default='redis://localhost:6379/0')

# Admin configuration - optional, admin interface disabled if not set or empty
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
ADMIN_ENABLED = ADMIN_PASSWORD is not None and ADMIN_PASSWORD.strip() != ''

EMAIL_FROM = os.environ.get('EMAIL_FROM', default=None)
EMAIL_SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', default="127.0.0.1")
EMAIL_SMTP_PORT = os.environ.get('EMAIL_SMTP_PORT', default="25")
EMAIL_SMTP_USER = os.environ.get('EMAIL_SMTP_USER', default='')
EMAIL_SMTP_PASSWORD = os.environ.get('EMAIL_SMTP_PASSWORD', default='')
EMAIL_HELO_HOSTNAME = os.environ.get('EMAIL_HELO_HOSTNAME', default=socket.getfqdn())
