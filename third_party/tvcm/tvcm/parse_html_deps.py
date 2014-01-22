# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from HTMLParser import HTMLParser

class HTMLModuleParserResults(object):
  def __init__(self):
    self.scripts_external = []
    self.scripts_inline = []
    self.stylesheets = []
    self.imports = []

class HTMLModuleParser(HTMLParser):
  def __init__(self):
    HTMLParser.__init__(self)
    self.current_results = None
    self.current_script = ""
    self.in_script = False
    self.in_style = False

  def Parse(self, html):
    results = HTMLModuleParserResults()
    if html is None or len(html) == 0:
      return results
    self.current_results = results
    self.feed(html)
    self.current_results = None
    return results

  def handle_starttag(self, tag, attrs):
    if tag == 'link':
      is_stylesheet = False
      is_import = False
      href = None
      for attr in attrs:
        if attr[0] == 'rel' and attr[1] == 'stylesheet':
          is_stylesheet = True
        elif attr[0] == 'rel' and attr[1] == 'import':
          is_import = True
        elif attr[0] == 'href':
          href = attr[1]

      if is_stylesheet:
        self.current_results.stylesheets.append(href)
      elif is_import:
        self.current_results.imports.append(href)

    elif tag == 'script':
      for attr in attrs:
        if attr[0] == 'src':
          self.current_results.scripts_external.append(attr[1])
          return
      self.in_script = True

    elif tag == 'style':
      self.in_style = True

  def handle_endtag(self, tag):
    if tag == 'script' and self.in_script:
      self.current_results.scripts_inline.append(self.current_script)
      self.current_script = ""
      self.in_script = False

    elif tag == 'style' and self.in_style:
      self.in_style = False

  def handle_data(self, data):
    if self.in_script:
      self.current_script += data
    elif self.in_style:
      result = re.match(r"\s*@import url\(([^\)]*)\)", data,
                        flags=re.IGNORECASE)
      if result:
        self.current_results.stylesheets.append(result.group(1))
