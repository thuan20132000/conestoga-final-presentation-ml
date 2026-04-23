from storages.backends.s3boto3 import S3Boto3Storage

from .settings import MEDIA_LOCATION, STATICFILES_LOCATION


class StaticStorage(S3Boto3Storage):
    location = STATICFILES_LOCATION
    query_string_auth = False


class MediaStorage(S3Boto3Storage):
    location = MEDIA_LOCATION
    file_overwrite = False
