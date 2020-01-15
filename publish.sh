#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 ]]; then
  echo "usage: $0 <s3_bucket_name> <aws_account_name>"
  exit 1
fi

S3_BUCKET="${1}"
ACCOUNT_NAME="${2}"

aws s3 cp cloudwatch-loki-shipper.zip "s3://${S3_BUCKET}/cloudwatch-loki-shipper.zip" --profile "${ACCOUNT_NAME}"
