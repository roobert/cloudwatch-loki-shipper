#!/usr/bin/env python

import os
import gzip
import json
import base64
import requests
from urllib.parse import urljoin
from string import Template
from collections import namedtuple


def _decode_log_data(event):
    compressed_payload = base64.b64decode(event["awslogs"]["data"])
    decoded_payload = json.loads(gzip.decompress(compressed_payload))
    return decoded_payload


def _is_json(message):
    if not message.startswith("{"):
        print(f"warning: skipping - log entry is not JSON!")
        return True


def _stream_labels(log_labels, embedded_json):
    stream_labels = {}
    for label in log_labels:
        if label not in embedded_json:
            print(f"stream label not found: {label}")
            continue
        stream_labels[label] = embedded_json[label]
    return stream_labels


def _template_variables(log_template_variables, embedded_json):
    template_variables = {}
    for variable in log_template_variables:
        if variable not in embedded_json:
            print(f"template variable not found: {variable}")
            continue
        template_variables[variable] = embedded_json[variable]
    return template_variables


def _streams(config, cloudwatch_event):
    log_data = _decode_log_data(cloudwatch_event)
    streams = {"streams": []}
    stream_labels = {"logGroup": log_data["logGroup"]}

    for log_entry in log_data["logEvents"]:
        print(f"log entry: {log_entry}")
        if _is_json(log_entry["message"]):
            continue

        if config.log_labels:
            embedded_json = json.loads(log_entry["message"])
            stream_labels.update(_stream_labels(config.log_labels, embedded_json))
            print(f"stream labels: {stream_labels}")
            template_variables = _template_variables(
                config.log_template_variables, embedded_json
            )
            print(f"template variables: {template_variables}")
            message = Template(config.log_template).substitute(**template_variables)
        else:
            message = log_entry["message"]

        timestamp = str(log_entry["timestamp"] * 1000000)
        stream_value = [timestamp, message]

        # for simplicities sake during labelling, create a new stream for every log line
        stream = {"stream": stream_labels, "values": [stream_value]}
        streams["streams"].append(stream)
        print(f"processed log entry: {stream_value}, log labels: {stream_labels}")

    return streams


def _loki_push(config, stream_data):
    print(f"sending request to: {config.loki_endpoint}, payload: {stream_data}")
    response = requests.post(config.loki_endpoint, json=stream_data)

    if response.status_code != 204:
        print(f"request failed: {response.text}")


def _environment_config():
    if ("LOG_TEMPLATE" in os.environ) and not ("LOG_LABELS" in os.environ):
        print("ignoring LOG_TEMPLATE since no LOG_LABELS are set")

    config = namedtuple("Config", "loki_endpoint log_labels log_template")
    config.loki_endpoint = urljoin(
        os.environ.get("LOKI_ENDPOINT", "http://localhost:3100"), "/loki/api/v1/push"
    )
    config.log_labels = os.environ.get("LOG_LABELS", "").split(",")
    config.log_template = os.environ.get("LOG_TEMPLATE", "$message")
    config.log_template_variables = os.environ.get(
        "LOG_TEMPLATE_VARIABLES", "message"
    ).split(",")
    return config


def lambda_handler(cloudwatch_event, context):
    print("executing lambda: cloudwatch-loki-shipper")
    config = _environment_config()
    streams = _streams(config, cloudwatch_event)
    _loki_push(config, streams)
    print("lambda processing complete")
