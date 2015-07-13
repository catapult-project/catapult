# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys

from tvcm import module
from tvcm import strip_js_comments
from tvcm import html_generation_controller


def _InitBeautifulSoup():
  tvcm_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
  bs_path = os.path.join(tvcm_path, 'third_party', 'beautifulsoup')
  if bs_path in sys.path:
    return
  sys.path.insert(0, bs_path)


_InitBeautifulSoup()
import BeautifulSoup
import polymer_soup


class InlineScript(object):
  def __init__(self, soup):
    if not soup:
      raise module.DepsException('InlineScript created without soup')
    self._soup = soup
    self._stripped_contents = None
    self._open_tags = None

  @property
  def contents(self):
    #TODO(nednguyen): change other places to use unicode() instead of str().
    return unicode(self._soup.string)

  @property
  def stripped_contents(self):
    if not self._stripped_contents:
      self._stripped_contents = strip_js_comments.StripJSComments(
          self.contents)
    return self._stripped_contents

  @property
  def open_tags(self):
    if self._open_tags:
      return self._open_tags
    open_tags = []
    cur = self._soup.parent
    while cur:
      if isinstance(cur, BeautifulSoup.BeautifulSoup):
        break

      open_tags.append(_Tag(cur.name, cur.attrs))
      cur = cur.parent

    open_tags.reverse()
    assert open_tags[-1].tag == 'script'
    del open_tags[-1]

    self._open_tags = open_tags
    return self._open_tags


def _IsDoctype(x):
  if not isinstance(x, BeautifulSoup.Declaration):
    return False
  return x == 'DOCTYPE html' or x == 'DOCTYPE HTML'


class HTMLModuleParserResults(object):
  def __init__(self, html):
    self._soup = polymer_soup.PolymerSoup(html)
    self._inline_scripts = None

  @property
  def has_decl(self):
    decls = [x for x in self._soup.contents
             if _IsDoctype(x)]
    return len(decls) == 1

  @property
  def scripts_external(self):
    tags = self._soup.findAll('script', src=True)
    return [t['src'] for t in tags]

  @property
  def inline_scripts(self):
    if not self._inline_scripts:
      tags = self._soup.findAll('script', src=None)
      self._inline_scripts = [InlineScript(t.string) for t in tags]
    return self._inline_scripts

  @property
  def imports(self):
    tags = self._soup.findAll('link', rel='import')
    return [t['href'] for t in tags]

  @property
  def stylesheets(self):
    tags = self._soup.findAll('link', rel='stylesheet')
    return [t['href'] for t in tags]

  @property
  def inline_stylesheets(self):
    tags = self._soup.findAll('style')
    return [str(t.string) for t in tags]

  def YieldHTMLInPieces(self, controller, minify=False):
    yield self.GenerateHTML(controller, minify)

  def GenerateHTML(self, controller, minify=False):
    soup = polymer_soup.PolymerSoup(str(self._soup))

    # Remove declaration.
    for x in soup.contents:
      if isinstance(x, BeautifulSoup.Declaration):
        if _IsDoctype(x):
          x.extract()

    # Remove all imports.
    imports = soup.findAll('link', rel='import')
    for imp in imports:
      imp.extract()

    # Remove all script links.
    scripts_external = soup.findAll('script', src=True)
    for script in scripts_external:
      script.extract()

    # Remove all in-line scripts.
    scripts_external = soup.findAll('script', src=None)
    for script in scripts_external:
      script.extract()

    # Process all in-line styles.
    inline_styles = soup.findAll('style')
    for style in inline_styles:
      html = controller.GetHTMLForInlineStylesheet(str(style.string))
      if html:
        ns = BeautifulSoup.Tag(soup, 'style')
        ns.append(BeautifulSoup.NavigableString(html))
        style.replaceWith(ns)
      else:
        style.extract()

    # Rewrite all external stylesheet hrefs or remove, as needed.
    stylesheet_links = soup.findAll('link', rel='stylesheet')
    for stylesheet_link in stylesheet_links:
      html = controller.GetHTMLForStylesheetHRef(stylesheet_link['href'])
      if html:
        tmp = polymer_soup.PolymerSoup(html).findChildren()
        assert len(tmp) == 1
        stylesheet_link.replaceWith(tmp[0])
      else:
        stylesheet_link.extract()

    # Remove comments if minifying.
    if minify:
      comments = soup.findAll(
          text=lambda text: isinstance(text, BeautifulSoup.Comment))
      for comment in comments:
        comment.extract()

    # We are done.
    return str(soup).strip()

  @property
  def html_contents_without_links_and_script(self):
    return self.GenerateHTML(
        html_generation_controller.HTMLGenerationController())


class _Tag(object):

  def __init__(self, tag, attrs):
    self.tag = tag
    self.attrs = attrs

  def __repr__(self):
    attr_string = ' '.join(['%s="%s"' % (x[0], x[1]) for x in self.attrs])
    return '<%s %s>' % (self.tag, attr_string)


class HTMLModuleParser():

  def Parse(self, html):
    if html is None:
      html = ''
    else:
      if html.find('< /script>') != -1:
        raise Exception('Escape script tags with <\/script>')

    return HTMLModuleParserResults(html)
