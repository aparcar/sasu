class Config(object):
    DEBUG = False
    TESTING = False


class ProductionConfig(Config):
    STORE_URL = "https://firmware.aparcar.org"


class DevelopmentConfig(Config):
    STORE_URL = "http://localhost:5000"
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
