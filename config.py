import os
from pathlib import Path

current_dir = Path(__file__).resolve().parent
logs_dir = current_dir / "logs"
logs_dir.mkdir(exist_ok=True)

LOGGER_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "console": {
            '()': 'colorlog.ColoredFormatter',
            "format": "%(log_color)s[%(asctime)s:%(msecs)03d] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
            'datefmt': '%Y-%m-%d %H:%M:%S',
            "log_colors": {
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red,bg_white',
            },
        },
        "file": {
            "format": "[%(asctime)s:%(msecs)03d] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
            'datefmt': '%Y-%m-%d %H:%M:%S',
        }
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": os.getenv('LOG_LEVEL'),
            "formatter": "console",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": os.getenv('LOG_LEVEL'),
            "formatter": "file",
            "filename": os.path.join(logs_dir, "megadl.log")
        }

    },
    "loggers": {
        "": {
            "handlers": [os.getenv('LOG_DESTINATION')],
            "level": os.getenv('LOG_LEVEL'),
            "propagate": False,
        }
    },
}