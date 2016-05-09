#!/usr/bin/env python
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Inject javascript into html page source code."""

import logging
import os
import re
import util
import third_party.jsmin as jsmin

DOCTYPE_RE = re.compile(r'^.{,256}?(<!--.*-->)?.{,256}?<!doctype html>',
                        re.IGNORECASE | re.DOTALL)
HTML_RE = re.compile(r'^.{,256}?(<!--.*-->)?.{,256}?<html.*?>',
                     re.IGNORECASE | re.DOTALL)
HEAD_RE = re.compile(r'^.{,256}?(<!--.*-->)?.{,256}?<head.*?>',
                     re.IGNORECASE | re.DOTALL)


def GetInjectScript(scripts):
  """Loads |scripts| from disk and returns a string of their content."""
  lines = []
  if scripts:
    if not isinstance(scripts, list):
      scripts = scripts.split(',')
    for script in scripts:
      if os.path.exists(script):
        with open(script) as f:
          lines.extend(f.read())
      elif util.resource_exists(script):
        lines.extend(util.resource_string(script))
      else:
        raise Exception('Script does not exist: %s', script)

  return jsmin.jsmin(''.join(lines), quote_chars="'\"`")


def InjectScript(content, content_type, script_to_inject):
  """Inject |script_to_inject| into |content| if |content_type| is 'text/html'.

  Inject |script_to_inject| into |content| immediately after <head>, <html> or
  <!doctype html>, if one of them is found. Otherwise, inject at the beginning.

  Returns:
    content, already_injected
    |content| is the new content if script is injected, otherwise the original.
    |already_injected| indicates if |script_to_inject| is already in |content|.
  """
  already_injected = False
  if content_type and content_type == 'text/html':
    already_injected = not content or script_to_inject in content
    if not already_injected:
      def InsertScriptAfter(matchobj):
        return '%s<script>%s</script>' % (matchobj.group(0), script_to_inject)

      content, is_injected = HEAD_RE.subn(InsertScriptAfter, content, 1)
      if not is_injected:
        content, is_injected = HTML_RE.subn(InsertScriptAfter, content, 1)
      if not is_injected:
        content, is_injected = DOCTYPE_RE.subn(InsertScriptAfter, content, 1)
      if not is_injected:
        content = '<script>%s</script>%s' % (script_to_inject, content)
        logging.warning('Inject at the very beginning, because no tag of '
                        '<head>, <html> or <!doctype html> is found.')
  return content, already_injected
