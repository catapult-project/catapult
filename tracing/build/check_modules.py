# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import sys
import os

tracing_path = os.path.abspath(os.path.join(os.path.dirname(__file__),
    '..', '..'))
if tracing_path not in sys.path:
  sys.path.append(tracing_path)

from tracing import tracing_project

def CheckModules():
  p = tracing_project.TracingProject()
  try:
    p.CalcLoadSequenceForAllModules()
  except Exception, ex:
    return str(ex)
  return []

if __name__ == '__main__':
  print GypCheck()
