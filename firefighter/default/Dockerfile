# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM gcr.io/google_appengine/python-compat

# The Python standard runtime is based on Debian Wheezy. Use Stretch to get SciPy 0.16.
RUN echo "deb http://gce_debian_mirror.storage.googleapis.com stretch main" >> /etc/apt/sources.list
RUN apt-get update && apt-get install -y -t stretch python-numpy python-scipy

ADD . /app
