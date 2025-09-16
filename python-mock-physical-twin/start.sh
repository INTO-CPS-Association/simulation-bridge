#!/bin/bash

# Running Interactive
#docker run -it --entrypoint /bin/bash registry.gitlab.com/carmony-project/carmony-http-api:0.1 -s

docker run --name=physical_twin_emulator \
    -p 5555:5555 \
    --restart always \
    -d registry.gitlab.com/piconem-university/projects/digital-twin/physical-twin-emulator:0.1