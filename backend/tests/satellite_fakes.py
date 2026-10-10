"""Test-only conditional S3 transport; application behavior stays real."""
import hashlib
import io
import json
from botocore.exceptions import ClientError


class MemoryS3:
    def __init__(self):
        self.objects = {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        body, etag = self.objects[Key]
        return {'Body': io.BytesIO(body), 'ETag': etag}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None, **kwargs):
        current = self.objects.get(Key)
        if (IfNoneMatch == '*' and current) or (IfMatch and (not current or current[1] != IfMatch)):
            raise ClientError({'Error': {'Code': 'PreconditionFailed'}}, 'PutObject')
        etag = '"'+hashlib.sha256(Body).hexdigest()+'"'
        self.objects[Key] = (Body, etag)
        return {'ETag': etag}

    def body(self, key):
        return json.loads(self.objects[key][0])
