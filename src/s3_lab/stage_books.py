#!/usr/bin/env python3
"""Stage Project Gutenberg books in a public S3 bucket."""

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Return (list_file, index_path, bucket) from the command line."""
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py BOOK_LIST INDEX_HTML BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download the books in list_file to dest_dir and return their paths."""
    os.makedirs(dest_dir, exist_ok=True)
    with open(list_file) as f:
        urls = [line.strip() for line in f if line.strip()]

    paths = []
    for url in urls:
        path = os.path.join(dest_dir, url.split("/")[-1])
        if os.path.exists(path):
            paths.append(path)
            continue
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
            paths.append(path)
            log.info(f"Downloaded {path}")
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")
        time.sleep(1)

    log.info(f"{len(paths)} books available")
    return paths


def create_bucket(bucket):
    """Create the bucket unless it exists. Return True if it exists afterwards."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket exists: {bucket}")
        return True
    except ClientError:
        pass
    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket: {e}")
        return False


def make_public(bucket):
    """Turn off Block Public Access and attach a public-read policy."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
            }
        ],
    }
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Made bucket public: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload the files as plain text and return how many succeeded."""
    count = 0
    for path in file_paths:
        try:
            s3.upload_file(
                path,
                bucket,
                os.path.basename(path),
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            count += 1
        except (ClientError, FileNotFoundError) as e:
            log.error(f"Error uploading {path}: {e}")
    log.info(f"Uploaded {count} of {len(file_paths)} books")
    return count


def upload_index(bucket, index_path):
    """Upload the index page as HTML. Return True on success."""
    try:
        s3.upload_file(index_path, bucket, "index.html", ExtraArgs={"ContentType": "text/html"})
        log.info("Uploaded index.html")
        return True
    except (ClientError, FileNotFoundError) as e:
        log.error(f"Error uploading {index_path}: {e}")
        return False


def main():
    """Download the books and stage them in a public bucket."""
    list_file, index_path, bucket = parse_args()

    paths = download_books(list_file, "books")
    if not paths or not create_bucket(bucket) or not make_public(bucket):
        sys.exit(1)

    count = upload_files(bucket, paths)
    if count == len(paths) and upload_index(bucket, index_path):
        log.info("Success")
    else:
        log.error("Finished with errors")
    log.info(f"https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
