"""Private R2 transport for TUF. Supply a read-only boto3 S3 client.

No credentials are read, logged or shipped by this module. Provision a dedicated
device read-only credential separately; never pass the publisher credential to
an installed Aether client.
"""
from urllib.parse import unquote, urlsplit

from tuf.api.exceptions import DownloadError, DownloadHTTPError
from tuf.ngclient.fetcher import FetcherInterface

from repository import safe_target


class R2Fetcher(FetcherInterface):
    def __init__(self, s3_client, bucket: str, prefix: str, base_url: str):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Expected a plain HTTPS repository URL")
        if not parsed.netloc or parsed.path not in ("", "/"):
            raise ValueError("Repository URL must have a host and no path")
        self.client, self.bucket = s3_client, bucket
        self.prefix = safe_target(prefix.rstrip("/")) + "/"
        self.host = parsed.netloc

    def _fetch(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != self.host or parsed.query or parsed.fragment:
            raise DownloadError("Unapproved repository URL")
        path = unquote(parsed.path).lstrip("/")
        try:
            safe_target(path)
        except ValueError:
            raise DownloadError("Unsafe repository path") from None
        if not path.startswith(("metadata/", "targets/")):
            raise DownloadError("Unapproved repository path")
        body = None
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.prefix + path)
            body = response["Body"]
            for chunk in body.iter_chunks(chunk_size=65536):
                if chunk:
                    yield chunk
        except Exception as error:
            status = getattr(error, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status is not None:
                raise DownloadHTTPError("Private update storage request failed", status) from None
            if isinstance(error, DownloadError):
                raise
            raise DownloadError("Private update storage request failed") from None
        finally:
            if body is not None:
                body.close()
