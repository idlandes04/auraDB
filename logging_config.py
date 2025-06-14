# FILE: logging_config.py

import logging
import logging.config
from config import LOG_PATH

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)-22s - %(levelname)-8s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': LOG_PATH,
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
            'level': 'INFO'
        }
    },
    'loggers': {
        '': { # Root logger
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True
        },
        # Quieten noisy third-party libraries
        'apscheduler': {
            'handlers': ['console', 'file'],
            'level': 'WARNING', 
            'propagate': False
        },
        'googleapiclient': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False
        },
        'google.auth.transport.requests': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False
        },
        'urllib3': {
             'handlers': ['console', 'file'],
             'level': 'WARNING',
             'propagate': False
        },
         'httpx': {
             'handlers': ['console', 'file'],
             'level': 'WARNING',
             'propagate': False
        }
    }
}

def setup_logging():
    """Applies the logging configuration."""
    logging.config.dictConfig(LOGGING_CONFIG)