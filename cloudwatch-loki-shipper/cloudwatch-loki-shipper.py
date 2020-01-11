#!/usr/bin/env python

import os
import gzip
import json
import base64
import requests
from urllib.parse import urljoin


def _decode_log_data(event):
    compressed_payload = base64.b64decode(event["awslogs"]["data"])
    decoded_payload = json.loads(gzip.decompress(compressed_payload))
    return decoded_payload


def _stream_data(cloudwatch_event):
    log_data = _decode_log_data(cloudwatch_event)
    stream_labels = {"logGroup": log_data["logGroup"]}
    stream_entries = []

    for log_entry in log_data["logEvents"]:
        print(f"log entry: {log_entry}")
        if not log_entry["message"].startswith("{"):
            print(f"warning: skipping - log entry is not JSON!")
            continue

        stream_value = [str(log_entry["timestamp"] * 1000000), log_entry["message"]]
        stream_entries.append(stream_value)
        print(f"processed log entry: {stream_value}")

    return stream_entries, stream_labels


def _loki_push(loki_endpoint, stream_data):
    print(f"sending request to: {loki_endpoint}, payload: {stream_data}")
    response = requests.post(loki_endpoint, json=stream_data)

    if response.status_code != 204:
        print(f"request failed: {response.text}")


def lambda_handler(loki_endpoint, cloudwatch_event, context):
    print("lambda firing!")
    loki_endpoint = urljoin(
        os.environ.get("LOKI_ENDPOINT", "http://localhost:3100"), "/loki/api/v1/push"
    )

    stream_entries, stream_labels = _stream_data(cloudwatch_event)

    _loki_push(
        loki_endpoint,
        {"streams": [{"stream": stream_labels, "values": stream_entries}]},
    )
    print("lambda processing complete!")
