#!/bin/bash

set -eu


CWD="$(dirname "$0")/.."
cd $CWD

packageBinary() {
  ARCH=${1:-aws}

  BUILD_NAME=tip
  PACKAGE_PATH=$CWD/dist/
  DOCKER_IMAGE="trend_of_ip-build-for-$ARCH"
  ZIP_NAME="$BUILD_NAME-for-$ARCH.zip"

  rm -Rf $PACKAGE_PATH
  mkdir -p $PACKAGE_PATH

  docker build -f builds/$ARCH/Dockerfile --compress --target build -t tsutorm/$DOCKER_IMAGE .
  docker run  --name $DOCKER_IMAGE -it tsutorm/$DOCKER_IMAGE /app/dist/tip -h
  docker cp $DOCKER_IMAGE:/app/dist/tip $PACKAGE_PATH
  docker rm $DOCKER_IMAGE

  # Package
  zip -9 -D "$PACKAGE_PATH$ZIP_NAME" "$PACKAGE_PATH$BUILD_NAME"

  echo "done."
}

if [ ! -z "$1" ]; then
  packageBinary "$1"
else
  packageBinary aws
fi
