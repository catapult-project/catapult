# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

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
