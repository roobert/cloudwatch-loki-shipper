#!/usr/bin/env python

import os
import gzip
import json
import base64
import requests
from urllib.parse import urljoin
from string import Template
from collections import namedtuple


def _is_json(message):
    if message.startswith("{"):
        return True


def _decode_log_data(event):
    compressed_payload = base64.b64decode(event["awslogs"]["data"])
    decoded_payload = json.loads(gzip.decompress(compressed_payload))
    return decoded_payload


def _stream_labels(log_labels, nested_json):
    stream_labels = {}
    for label in log_labels:
        if label not in nested_json:
            print(f"stream label not found: {label}")
            continue
        stream_labels[label] = nested_json[label]
    return stream_labels


def _template_variables(log_template_variables, nested_json):
    template_variables = {}
    for variable in log_template_variables:
        if variable not in nested_json:
            print(f"template variable not found: {variable}")
            continue
        template_variables[variable] = nested_json[variable]
    return template_variables


def _template_message(nested_json, config, stream_labels):
    template_variables = _template_variables(config.log_template_variables, nested_json)
    print(f"template variables: {template_variables}")
    message = Template(config.log_template).substitute(**template_variables)
    return message, stream_labels


def _json_message(nested_json, config, stream_labels):
    # Convert JSON string into a formatted log message based on template supplied by LOG_TEMPLATE
    if config.log_template:
        message, stream_labels = _template_message(nested_json, config, stream_labels)
    else:
        # If no log template set then just use the entire string as the log message
        message = str(nested_json)
    return message


def _loki_push(config, stream_data):
    print(f"sending request to: {config.loki_endpoint}, payload: {stream_data}")
    response = requests.post(config.loki_endpoint, json=stream_data)
    if response.status_code != 204:
        print(f"request failed: {response.text}")


def _environment_config():
    if ("LOG_TEMPLATE" in os.environ) and not ("LOG_LABELS" in os.environ):
        print("ignoring LOG_TEMPLATE since no LOG_LABELS are set")
    config = namedtuple(
        "Config",
        "loki_endpoint log_labels log_template log_template_variables log_ignore_non_json",
    )
    config.loki_endpoint = urljoin(
        os.environ.get("LOKI_ENDPOINT", "http://localhost:3100"), "/loki/api/v1/push"
    )
    config.log_labels = os.environ.get("LOG_LABELS", "").split(",")
    config.log_template = os.environ.get("LOG_TEMPLATE", "$message")
    config.log_template_variables = os.environ.get(
        "LOG_TEMPLATE_VARIABLES", "message"
    ).split(",")
    config.log_ignore_non_json = os.environ.get("LOG_IGNORE_NON_JSON", False)
    return config


def _streams(config, cloudwatch_event):
    log_data = _decode_log_data(cloudwatch_event)
    streams = {"streams": []}
    stream_labels = {"logGroup": log_data["logGroup"]}

    for log_entry in log_data["logEvents"]:
        print(f"log entry: {log_entry}")

        if _is_json["message"]:
            # If the application message is in JSON format then we can do
            # more interesting things with it than just log the message as-is
            nested_json = json.loads(log_entry["message"])

            # Lookup any label values from the nested json object and set them
            # as stream labels, if specified with LOG_LABELS
            if config.log_labels:
                stream_labels.update(_stream_labels(config.log_labels, nested_json))
                print(f"stream labels: {stream_labels}")

            message = _json_message(nested_json, config, stream_labels)
        elif config.log_ignore_non_json:
            # It can be useful to ignore log lines not in JSON format when expecting
            # log lines in JSON format - for example, when dealing with java apps
            # which can have a logback configuration which dumps stack traces to console
            # at the same time as writing them out as JSON
            print(f"warning: skipping non-JSON log entry!")
            continue
        else:
            # If not a JSON log then just pass through the entire message as the log line
            message = log_entry["message"]

        timestamp = str(log_entry["timestamp"] * 1000000)
        stream_value = [timestamp, message]

        # For simplicities sake during labelling, create a new stream for every log line
        # rather than batching up the log lines. This is because labels are per set of
        # streams however log lines can have different label values
        stream = {"stream": stream_labels, "values": [stream_value]}
        streams["streams"].append(stream)
        print(f"processed log entry: {stream_value}, log labels: {stream_labels}")

    return streams


def lambda_handler(cloudwatch_event, context):
    print("executing lambda: cloudwatch-loki-shipper")
    config = _environment_config()
    streams = _streams(config, cloudwatch_event)
    _loki_push(config, streams)
    print("lambda processing complete")
