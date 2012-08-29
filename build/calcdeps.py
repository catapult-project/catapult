#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys

import generate_about_tracing_contents
import generate_deps_js_contents

def main(argv):
  if generate_deps_js_contents.main([argv[0]]):
    return 255
  if generate_about_tracing_contents.main([argv[0]]):
    return 255
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
