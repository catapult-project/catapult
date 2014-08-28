# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import sys

from tvcm import module
from tvcm import strip_js_comments
from tvcm import html_generation_controller


# Some versions of Python have a busted HTMLParser.
# For old python versions, use the version of HTMLParser in tvcm/third_party.
def _SetupImportsForHTMLParser():
  def IsPythonNewEnough():
    if sys.version_info.major > 2:
      return True
    if sys.version_info.minor > 7:
      return True
    if sys.version_info.micro >= 6:
      return True
    return False
  if IsPythonNewEnough():
    return
  basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
  path = os.path.join(basedir, 'third_party', 'Python-2.7.6-HTMLParser', 'Lib')
  if path not in sys.path:
    sys.path.insert(0, path)
_SetupImportsForHTMLParser()
from HTMLParser import HTMLParser


CHUNK_TEXT_OP = 'text-op'
CHUNK_SCRIPT_OP = 'script-op'
CHUNK_STYLESHEET_OP = 'stylesheet-op'
CHUNK_INLINE_STYLE_OP = 'inline-style-op'


class _Chunk(object):
  def __init__(self, op, data):
    self.op = op
    self.data = data


class InlineScript(object):
  def __init__(self, contents, open_tags):
    self.contents = contents
    self.open_tags = open_tags
    self._stripped_contents = None

  @property
  def stripped_contents(self):
    if not self._stripped_contents:
      self._stripped_contents = strip_js_comments.StripJSComments(
          self.contents)
    return self._stripped_contents


class HTMLModuleParserResults(object):
  def __init__(self):
    self.scripts_external = []
    self.inline_scripts = []
    self.stylesheets = []
    self.imports = []
    self.has_decl = False
    self._chunks = []

  @property
  def inline_stylesheets(self):
    return [x.data for x in self._chunks
            if x.op == CHUNK_INLINE_STYLE_OP]

  def AppendHTMLContent(self, text):
    self._chunks.append(_Chunk(CHUNK_TEXT_OP, text))

  def AppendHTMLInlineStyleContent(self, text):
    self._chunks.append(_Chunk(CHUNK_INLINE_STYLE_OP, text))

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
      elif chunk.op == CHUNK_INLINE_STYLE_OP:
        html = controller.GetHTMLForInlineStylesheet(chunk.data)
        if html:
          yield html
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
    return self.GenerateHTML(html_generation_controller.HTMLGenerationController())

_SELF_CLOSING_TAGS = ('link', 'p', 'meta')

class _Tag(object):
  def __init__(self, tag, attrs):
    self.tag = tag
    self.attrs = attrs

  def __repr__(self):
    attr_string = ' '.join(['%s="%s"' % (x[0], x[1]) for x in self.attrs])
    return '<%s %s>' % (self.tag, attr_string)

class HTMLModuleParser(HTMLParser):
  def __init__(self):
    HTMLParser.__init__(self)
    self.current_results = None
    self.current_inline_script = None
    self._current_inline_style_sheet_contents = None
    self.open_tags = []
    self = None

  def Parse(self, html):
    results = HTMLModuleParserResults()
    if html is None or len(html) == 0:
      return results
    if html.find('< /script>') != -1:
      raise Exception('Escape script tags with <\/script>')
    self.current_results = results
    try:
      self.feed(html)
    finally:
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
      self.open_tags.append(_Tag(tag, attrs))

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
      self._current_inline_style_sheet_contents = ''
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
      if self._current_inline_style_sheet_contents != None:
        self.current_results.AppendHTMLInlineStyleContent(
            self._current_inline_style_sheet_contents)
        self._current_inline_style_sheet_contents = None
      self.current_results.AppendHTMLContent('</style>')

    else:
      self.current_results.AppendHTMLContent("</%s>" % tag)

  def handle_data(self, data):
    if self.current_inline_script:
      self.current_inline_script.contents += data

    elif self._current_inline_style_sheet_contents != None:
      result = re.match(r"\s*@import url\(([^\)]*)\)", data,
                        flags=re.IGNORECASE)
      if result:
        raise Exception("@import not yet supported")
      self._current_inline_style_sheet_contents += data
    else:
      self.current_results.AppendHTMLContent(data)
