# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from tvcm import strip_js_comments
from tvcm import js_presubmit_checker
from tvcm import css_presubmit_checker


class PresubmitChecker(object):
  def __init__(self, input_api, output_api):
    self.input_api = input_api
    self.output_api = output_api

  def RunChecks(self):
    results = []
    def IsResource(maybe_resource):
      f = maybe_resource.AbsoluteLocalPath()
      if not f.endswith(('.css', '.html', '.js')):
        return False
      if f.endswith('js'):
        with open(f) as f:
          contents = f.read()
        return 'tvcm' in contents
      return True

    results.extend(css_presubmit_checker.CSSChecker(
      self.input_api, self.output_api,
      file_filter=IsResource).RunChecks())
    results.extend(js_presubmit_checker.JSChecker(
      self.input_api, self.output_api,
      file_filter=IsResource).RunChecks())
    return results
