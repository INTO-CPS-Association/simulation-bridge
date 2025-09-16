#!/bin/bash

VERSION=$2
REPOSITORY="registry.gitlab.com/dt-trustworthiness/physical-twin-emulator"

if [[ ! "$VERSION" ]];
	then
		echo "Missing parameter VERSION."
		echo " Usage $0 <VERSION>."
		echo "Example: $0 1.0"
		exit 1
fi

echo "Pushing to registry $REPOSITORY version $VERSION"
docker push $REPOSITORY:$VERSION
