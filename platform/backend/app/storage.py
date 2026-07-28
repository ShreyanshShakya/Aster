from io import BytesIO

import boto3

from app.core.config import get_settings


def put_text(key: str, body: str, content_type: str) -> str:
    settings = get_settings()
    client = storage_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.minio_bucket)
    client.upload_fileobj(BytesIO(body.encode("utf-8")), settings.minio_bucket, key, ExtraArgs={"ContentType": content_type})
    return key


def storage_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
    )


def get_artifact(key: str):
    settings = get_settings()
    return storage_client().get_object(Bucket=settings.minio_bucket, Key=key)
