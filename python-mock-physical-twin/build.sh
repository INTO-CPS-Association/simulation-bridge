#!/bin/bash

VERSION=$1
REPOSITORY="registry.gitlab.com/dt-trustworthiness/physical-twin-emulator"

if [[ ! "$VERSION" ]];
	then
		echo "Missing parameter VERSION."
		echo " Usage $0 <VERSION>."
		echo "Example: $0 1.0"
		exit 1
fi

echo "Building $REPOSITORY version $VERSION"
docker build -t $REPOSITORY:$VERSION .
