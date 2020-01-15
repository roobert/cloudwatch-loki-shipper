#!/usr/bin/env bash

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_DIR=${PROJECT_ROOT}
SHIPPER_DIR=${PROJECT_ROOT}/cloudwatch-loki-shipper

deactivate  > /dev/null 2>&1

if [ -d "venv" ]; then
  rm -rf venv
fi

python3 -m venv venv

. venv/bin/activate
pip3 install -r requirements.txt

PACKAGE_DIR=$(find ${PROJECT_ROOT}/venv -name "site-packages")

cd "${PACKAGE_DIR}"
zip -r9 "${TARGET_DIR}/cloudwatch-loki-shipper.zip" .

cd "${SHIPPER_DIR}"
zip -g "${TARGET_DIR}/cloudwatch-loki-shipper.zip" cloudwatch-loki-shipper.py
