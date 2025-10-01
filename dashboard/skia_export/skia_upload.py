# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Entry-point for the pipeline to export Chromeperf data to Skia Perf.

This script initializes and runs the Apache Beam pipeline defined in
skia_export.skia_pipeline. The pipeline reads Row entities from Datastore,
converts them to the Skia Perf JSON format, and uploads them to the
appropriate Google Cloud Storage buckets.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import logging

from skia_export import skia_pipeline

if __name__ == '__main__':
  logging.getLogger().setLevel(logging.INFO)
  skia_pipeline.main()
