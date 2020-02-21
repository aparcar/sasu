from os import getenv

class Config(object):
    DEBUG = False
    TESTING = False


class ProductionConfig(Config):
    STORE_URL = "https://images.aparcar.org"
    STORE_PATH = "/var/cache/asu/store/"


class DevelopmentConfig(Config):
    STORE_URL = "http://localhost:5000"
    STORE_PATH = getenv("STORE_PTH", "./store")
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
