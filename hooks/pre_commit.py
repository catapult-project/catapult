# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys

from trace_viewer import trace_viewer_project

def Main(args):
  tvp = trace_viewer_project.TraceViewerProject()
  # TODO(nduca): Add pre-commit checks here.