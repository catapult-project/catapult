# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from tvcm import module
from tvcm import strip_js_comments
from tvcm import parse_html_deps

def IsHTMLResourceTheModuleGivenConflictingResourceNames(
    js_resource, html_resource):
  return False

class HTMLModule(module.Module):
  def Parse(self):
    results = HTMLModuleParser().Parse(self.contents)
    # resolve the pathnames in results to be non-relative
    # prevent non-file links
    # prevent links outside of loader paths
    #
