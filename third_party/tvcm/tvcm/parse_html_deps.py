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
    self.has_decl = False
    self._html_content_chunks_without_links_and_script = []

  def AppendHTMLContent(self, chunk):
    self._html_content_chunks_without_links_and_script.append(chunk)

  @property
  def html_contents_without_links_and_script(self):
    return ''.join(self._html_content_chunks_without_links_and_script)


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

  def handle_decl(self, decl):
    assert self.current_results.has_decl == False, 'Only one doctype decl allowed'
    self.current_results.has_decl = True

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
      else:
        self.current_results.AppendHTMLContent(
          self.get_starttag_text())

    elif tag == 'script':
      for attr in attrs:
        if attr[0] == 'src':
          self.current_results.scripts_external.append(attr[1])
          return
      self.in_script = True

    elif tag == 'style':
      self.in_style = True
      self.current_results.AppendHTMLContent(
        self.get_starttag_text())

    else:
      self.current_results.AppendHTMLContent(
        self.get_starttag_text())

  def handle_entityref(self, name):
    self.current_results.AppendHTMLContent('&%s;' % name)

  def handle_charref(self, name):
    self.current_results.AppendHTMLContent('&#%s;' % name)

  def handle_startendtag(self, tag, attrs):
    self.current_results.AppendHTMLContent('%s' % self.get_starttag_text())

  def handle_endtag(self, tag):
    if tag == 'script':
      if self.in_script:
        self.current_results.scripts_inline.append(self.current_script)
        self.current_script = ""
        self.in_script = False

    elif tag == 'style':
      if self.in_style:
        self.in_style = False
      self.current_results.AppendHTMLContent('</style>')

    else:
      self.current_results.AppendHTMLContent("</%s>" % tag)

  def handle_data(self, data):
    if self.in_script:
      self.current_script += data

    elif self.in_style:
      result = re.match(r"\s*@import url\(([^\)]*)\)", data,
                        flags=re.IGNORECASE)
      if result:
        raise Exception("@import not yet supported")
      self.current_results.AppendHTMLContent(data)

    else:
      self.current_results.AppendHTMLContent(data)
