# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from HTMLParser import HTMLParser

from tvcm import module


CHUNK_TEXT_OP = 'text-op'
CHUNK_SCRIPT_OP = 'script-op'
CHUNK_STYLESHEET_OP = 'stylesheet-op'


class _Chunk(object):
  def __init__(self, op, data):
    self.op = op
    self.data = data

class InlineScript(object):
  def __init__(self, contents, open_tags):
    self.contents = contents
    self.open_tags = open_tags

class HTMLModuleParserResults(object):
  def __init__(self):
    self.scripts_external = []
    self.inline_scripts = []
    self.stylesheets = []
    self.imports = []
    self.has_decl = False
    self._chunks = []

  def AppendHTMLContent(self, text):
    self._chunks.append(_Chunk(CHUNK_TEXT_OP, text))

  def AppendHTMLScriptSplicePoint(self, href):
    self._chunks.append(_Chunk(CHUNK_SCRIPT_OP, href))

  def AppendHTMLStylesheetSplicePoint(self, href):
    self._chunks.append(_Chunk(CHUNK_STYLESHEET_OP, href))

  def GenerateHTML(self, controller):
    return ''.join(list(self.YieldHTMLInPieces(controller)))

  def YieldHTMLInPieces(self, controller):
    for chunk in self._chunks:
      if chunk.op == CHUNK_TEXT_OP:
        yield chunk.data
      elif chunk.op == CHUNK_SCRIPT_OP:
        html = controller.GetHTMLForScriptHRef(chunk.data)
        if html:
          yield html
      elif chunk.op == CHUNK_STYLESHEET_OP:
        html = controller.GetHTMLForStylesheetHRef(chunk.data)
        if html:
          yield html
      else:
        raise NotImplementedError()

  @property
  def html_contents_without_links_and_script(self):
    return self.GenerateHTML(module.HTMLGenerationController())

_SELF_CLOSING_TAGS = ('link', 'p', 'meta')

class _Tag(object):
  def __init__(self, tag, attrs):
    self.tag = tag
    self.attrs = attrs

class HTMLModuleParser(HTMLParser):
  def __init__(self):
    HTMLParser.__init__(self)
    self.current_results = None
    self.current_inline_script = None
    self.in_style = False
    self.open_tags = []

  def Parse(self, html):
    results = HTMLModuleParserResults()
    if html is None or len(html) == 0:
      return results
    if html.find('< /script>') != -1:
      raise Exception('Escape script tags with <\/script>')
    self.current_results = results
    self.feed(html)
    self.current_results = None
    if len(self.open_tags):
      raise Exception('There were open tags: %s' % ','.join(self.open_tags))
    return results

  def handle_decl(self, decl):
    assert self.current_results.has_decl == False, 'Only one doctype decl allowed'
    self.current_results.has_decl = True

  def handle_starttag(self, tag, attrs):
    if tag == 'br':
      raise Exception('Must use <br/>')

    if tag not in _SELF_CLOSING_TAGS:
      self.open_tags.append(_Tag(tag, self.get_starttag_text()))

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
        self.current_results.AppendHTMLStylesheetSplicePoint(href)
        self.current_results.stylesheets.append(href)
      elif is_import:
        self.current_results.imports.append(href)
      else:
        self.current_results.AppendHTMLContent(
          self.get_starttag_text())

    elif tag == 'script':
      had_src = False
      for attr in attrs:
        if attr[0] == 'src':
          self.current_results.scripts_external.append(attr[1])
          self.current_results.AppendHTMLScriptSplicePoint(attr[1])
          had_src = True
      if had_src == False:
        assert self.current_inline_script == None
        self.current_inline_script = InlineScript(
            '',
            list(self.open_tags[:-1]))

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
    if (tag == 'script'):
      raise Exception('Script must have explicit close tag')
    self.current_results.AppendHTMLContent('%s' % self.get_starttag_text())

  def handle_endtag(self, tag):
    if tag not in _SELF_CLOSING_TAGS:
      if len(self.open_tags) == 0:
        raise Exception('got </%s> with no previous open tag' % tag)

      if self.open_tags[-1].tag != tag:
        raise Exception('Expected </%s> but got </%s>' % (
            self.open_tags[-1].tag, tag))
      self.open_tags.pop()

    if tag == 'script':
      if self.current_inline_script:
        self.current_results.inline_scripts.append(
            self.current_inline_script)
        self.current_inline_script = None

    elif tag == 'style':
      if self.in_style:
        self.in_style = False
      self.current_results.AppendHTMLContent('</style>')

    else:
      self.current_results.AppendHTMLContent("</%s>" % tag)

  def handle_data(self, data):
    if self.current_inline_script:
      self.current_inline_script.contents += data

    elif self.in_style:
      result = re.match(r"\s*@import url\(([^\)]*)\)", data,
                        flags=re.IGNORECASE)
      if result:
        raise Exception("@import not yet supported")
      self.current_results.AppendHTMLContent(data)

    else:
      self.current_results.AppendHTMLContent(data)
