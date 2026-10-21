#!/bin/bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRES_SECONDS" >&2
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILE="$(basename "$URL")"

mkdir -p books
curl -fsSL "$URL" -o "books/$FILE"

if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET" > /dev/null
fi

aws s3 cp "books/$FILE" "s3://$BUCKET/$FILE" --content-type "text/plain; charset=utf-8" --only-show-errors
aws s3 presign "s3://$BUCKET/$FILE" --expires-in "$EXPIRES"
