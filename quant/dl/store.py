"""Cloudflare R2(S3 호환) 파일 보관: 시세는 종목마다 parquet 하나. 키는 GitHub Secrets(R2_ACCESS_KEY_ID·R2_SECRET_ACCESS_KEY·R2_ENDPOINT·R2_BUCKET)에서만 읽는다."""
from __future__ import annotations

import io
import json
import os

import pandas as pd

PREFIX = "dl/"
ENV = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET")


def configured(env=os.environ) -> bool:
    return all(env.get(k) for k in ENV)


class R2:
    def __init__(self, client=None, bucket: str | None = None):
        if client is None:
            import boto3
            client = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
        self.c, self.bucket = client, bucket or os.environ["R2_BUCKET"]

    def put(self, name: str, data: bytes) -> None:
        self.c.put_object(Bucket=self.bucket, Key=PREFIX + name, Body=data)

    def get(self, name: str) -> bytes | None:
        try:
            return self.c.get_object(Bucket=self.bucket, Key=PREFIX + name)["Body"].read()
        except Exception as e:  # noqa: BLE001 — 없는 파일
            if "NoSuchKey" in type(e).__name__ or "NoSuchKey" in str(e) or "404" in str(e):
                return None
            raise

    def put_json(self, name: str, obj) -> None:
        self.put(name, json.dumps(obj, ensure_ascii=False, indent=1).encode())

    def get_json(self, name: str, default=None):
        b = self.get(name)
        return json.loads(b) if b else default

    def put_frame(self, name: str, df: pd.DataFrame) -> None:
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        self.put(name, buf.getvalue())

    def get_frame(self, name: str) -> pd.DataFrame | None:
        b = self.get(name)
        return pd.read_parquet(io.BytesIO(b)) if b else None
