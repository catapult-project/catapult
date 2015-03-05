# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from trace_viewer import trace_viewer_project

def CheckModules():
  p = trace_viewer_project.TraceViewerProject()
  try:
    p.CalcLoadSequenceForAllModules()
  except Exception, ex:
    return str(ex)
  return []

if __name__ == '__main__':
  print GypCheck()
