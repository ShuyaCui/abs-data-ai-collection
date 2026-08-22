#!/bin/sh
set -eu

docker build --memory 6g --platform linux/amd64 --tag npl-ppstructure:local --file docker/Dockerfile.ppstructure .
