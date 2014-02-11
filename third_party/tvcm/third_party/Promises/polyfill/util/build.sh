#!/bin/bash

# Copyright 2012:
#      Alex Russell <slightlyoff@chromium.org>
#
# Use of this source code is governed under the Apache License, Version 2.0
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Run it through uglify.
python post.py ../src/Promise.js > ../bin/Promise.min.js
