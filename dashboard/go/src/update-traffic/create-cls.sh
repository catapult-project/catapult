# Copyright 2023 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#!/bin/sh

git checkout main

declare -a services=("default"
                        "api"
                        "pinpoint"
                        "upload"
                        "upload-processing"
                        "skia-bridge"
                        "perf-issue-service")

for service in "${services[@]}"; do
    git branch -D $service
    git checkout -b $service -t origin/main
    git pull --ff
    go run update-traffic.go -checkout-base ../../../.. -service-id $service
    git commit -am "update chromeperf deployment for $service"
    git cl upload
done;