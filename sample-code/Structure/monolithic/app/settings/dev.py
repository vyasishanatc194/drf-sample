# -*- coding: utf-8 -*-

from .app import *  # noqa: F403, F401
from .base import *  # noqa: F403, F401
from .packages.auth import *  # noqa: F403, F401
from .packages.email import *  # noqa: F403, F401
from .packages.logger import *  # noqa: F403, F401
from .packages.push import *  # noqa: F403, F401
from .packages.rest import *  # noqa: F403, F401
from .packages.slack import *  # noqa: F403, F401
from .packages.swagger import *  # noqa: F403, F401
from .secrets import *  # noqa: F403, F401

logger = logging.getLogger("django.debuglogger")

DEBUG = True


################################################################
# COMMON BLOCK FOR ENV FILE
################################################################
def get_env_variable(var_name):
    try:
        return os.environ[var_name]
    except KeyError:
        from django.core.exceptions import ImproperlyConfigured

        error_msg = f"Set the {var_name} environment variable"
        raise ImproperlyConfigured(error_msg)


ENV = get_env_variable("ENV")
ACCOUNT_ALIAS = os.environ.get("ACCOUNT_ALIAS", None)
ENV_ALIAS = ENV if ACCOUNT_ALIAS is None else f"{ENV}_{ACCOUNT_ALIAS}"

# make sure to include this on each environment
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

BASE_DIR = Path(__file__).resolve().parent.parent


logger.debug(f"CURRENT ENVIRONMENT: {ENV}")
logger.debug(f"Base DIR: {BASE_DIR}")
################################################################
# END - COMMON BLOCK FOR ENV FILE
################################################################

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "mmd",
        "USER": DB_USERNAME,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,  # Or an IP Address that your DB is hosted on
        "PORT": "3306",
        "CONN_MAX_AGE": 60 * 5,
        "OPTIONS": {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1, read_rnd_buffer_size=256000",
            "charset": "utf8mb4",
        },
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_unicode_ci"},
    }
}


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:6379",
        "OPTIONS": {
            # https://github.com/jazzband/django-redis/issues/208
            "CLIENT_CLASS": "core.redis_client.CustomRedisCluster",
            "IGNORE_EXCEPTION": True,  # needed for redis is only cache
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_CLASS": "rediscluster.connection.ClusterConnectionPool",
            "CONNECTION_POOL_KWARGS": {
                "skip_full_coverage_check": True  # AWS ElasticCache has disabled CONFIG commands
            },
        },
        # 'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}


# this only for development
STATICFILES_DIRS = [os.path.join(BASE_DIR, "../static")]

# if you don't already have this in settings
DEFAULT_FROM_EMAIL = "server@exammple.com"

# AWS
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", None)
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", None)

# Storages
# should end with slash
STATIC_URL = "https://dev-kokospapamedia.example.co.kr/"
AWS_STORAGE_BUCKET_NAME = S3_BUCKET
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.ap-northeast-2.amazonaws.com"
CORS_ORIGIN_ALLOW_ALL = True
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = "public-read"

MIDDLEWARE.extend(["django.middleware.csrf.CsrfViewMiddleware"])

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "core.authentication.MMDJWTAuthentication",
    "rest_framework.authentication.SessionAuthentication",
)

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://localhost:3000$"]
INSTALLED_APPS.append("rest_framework_simplejwt.token_blacklist")
REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
