# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import httplib
import optparse
import json
import os
import re
import sys
import subprocess
import tempfile
import urllib
import StringIO

from tvcm import js_utils
from tvcm import module as module_module
from tvcm import html_generation_controller


srcdir = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                      "..", "..", "..", "src"))

html_warning_message = """


<!--
WARNING: This file is auto generated.

         Do not edit directly.
-->
"""

js_warning_message = """
// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/* WARNING: This file is auto generated.
 *
 * Do not edit directly.
 */
"""

css_warning_message = """
/* Copyright (c) 2014 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file. */

/* WARNING: This file is auto-generated.
 *
 * Do not edit directly.
 */
"""

def _MinifyJS(input_js):
  # Define the parameters for the POST request and encode them in
  # a URL-safe format.
  params = urllib.urlencode([
    ('js_code', input_js),
    ('language', 'ECMASCRIPT5'),
    ('compilation_level', 'SIMPLE_OPTIMIZATIONS'),
    ('output_format', 'json'),
    ('output_info', 'errors'),
    ('output_info', 'compiled_code'),
  ])

  # Always use the following value for the Content-type header.
  headers = { "Content-type": "application/x-www-form-urlencoded" }
  conn = httplib.HTTPConnection('closure-compiler.appspot.com')
  conn.request('POST', '/compile', params, headers)
  response = conn.getresponse()
  data = response.read()
  conn.close

  if response.status != 200:
    raise Exception("error returned from JS compile service: %d" % response.status)

  result = json.loads(data)
  if 'errors' in result:
    errors = []
    for e in result['errors']:
      filenum = int(e['file'][6:])
      filename = 'flat_script.js'
      lineno = e['lineno']
      charno = e['charno']
      err = e['error']
      errors.append('%s:%d:%d: %s' % (filename, lineno, charno, err))
    raise Exception('Failed to generate %s. Reason: %s' % (output_js_file,
                                                           '\n'.join(errors)))

  return result['compiledCode']

def GenerateJS(load_sequence,
               use_include_tags_for_scripts=False,
               dir_for_include_tag_root=None,
               minify=False):
  f = StringIO.StringIO()
  GenerateJSToFile(f,
                   load_sequence,
                   use_include_tags_for_scripts,
                   dir_for_include_tag_root,
                   minify)
  return f.getvalue()

def GenerateJSToFile(f,
                     load_sequence,
                     use_include_tags_for_scripts=False,
                     dir_for_include_tag_root=None,
                     minify=False):
  if use_include_tags_for_scripts and dir_for_include_tag_root == None:
    raise Exception('Must provide dir_for_include_tag_root')

  f.write(js_warning_message)
  f.write('\n')

  loader = load_sequence[0].loader

  polymer_script = loader.LoadRawScript('components/polymer/polymer.js')
  f.write(polymer_script.contents)

  f.write('\n')
  f.write("window._TV_IS_COMPILED = true;\n")

  if not minify:
    flatten_to_file = f
  else:
    flatten_to_file = StringIO.StringIO()


  for module in load_sequence:
    module.AppendJSContentsToFile(flatten_to_file,
                                  use_include_tags_for_scripts,
                                  dir_for_include_tag_root)

  if not minify:
    return

  minified_js = _MinifyJS(flatten_to_file.getvalue())
  f.write(minified_js)
  f.write('\n')


class ExtraScript(object):
  def __init__(self, script_id=None, text_content=None, content_type=None):
    if script_id != None:
      assert script_id[0] != '#'
    self.script_id = script_id
    self.text_content = text_content
    self.content_type = content_type

  def WriteToFile(self, output_file):
    attrs = []
    if self.script_id:
      attrs.append('id="%s"' % self.script_id)
    if self.content_type:
      attrs.append('content-type="%s"' % self.content_type)

    if len(attrs) > 0:
      output_file.write('<script %s>\n' % ' '.join(attrs))
    else:
      output_file.write('<script>\n')
    if self.text_content:
      output_file.write(self.text_content)
    output_file.write('</script>\n')


_have_printed_yui_missing_warning = False

def _MinifyCSS(css_text):
  with tempfile.NamedTemporaryFile() as f:
    yuic_args = ['yui-compressor', '--type', 'css', '-o', f.name]
    try:
      p = subprocess.Popen(yuic_args, stdin=subprocess.PIPE)
    except OSError:
      global _have_printed_yui_missing_warning
      if not _have_printed_yui_missing_warning:
        _have_printed_yui_missing_warning = True
        sys.stderr.write(
            'yui-compressor missing. CSS minification will be skipped.\n')
      return css_text
    p.communicate(input=css_text)
    if p.wait() != 0:
      raise Exception('Failed to generate %s.' % output_css_file)
    with open(f.name, 'r') as f2:
      return f2.read()


def GenerateStandaloneHTMLAsString(*args, **kwargs):
  f = StringIO.StringIO()
  GenerateStandaloneHTMLToFile(f, *args, **kwargs)
  return f.getvalue()


def GenerateStandaloneHTMLToFile(output_file,
                                 load_sequence,
                                 title=None,
                                 flattened_js_url=None,
                                 extra_scripts=None,
                                 minify=False):
  extra_scripts = extra_scripts or []

  output_file.write("""<!DOCTYPE HTML>
<html>
  <head i18n-values="dir:textdirection;">
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  """)
  if title:
    output_file.write("""  <title>%s</title>
""" % title)

  loader = load_sequence[0].loader

  written_style_sheets = set()

  class HTMLGenerationController(html_generation_controller.HTMLGenerationController):
    def __init__(self, module):
      self.module = module
    def GetHTMLForStylesheetHRef(self, href):
      resource = self.module.HRefToResource(
          href, '<link rel="stylesheet" href="%s">' % href)
      style_sheet = loader.LoadStyleSheet(resource.name)

      if style_sheet in written_style_sheets:
        return None
      written_style_sheets.add(style_sheet)

      text = style_sheet.contents_with_inlined_images
      if minify:
        text = _MinifyCSS(text)
      return "<style>\n%s\n</style>" % text

  for module in load_sequence:
    ctl = HTMLGenerationController(module)
    module.AppendHTMLContentsToFile(output_file, ctl, minify=minify)

  if flattened_js_url:
    output_file.write('<script src="%s"></script>\n' % flattened_js_url)
  else:
    output_file.write('<script>\n')
    output_file.write(GenerateJS(load_sequence, minify=minify))
    output_file.write('</script>\n')

  for extra_script in extra_scripts:
    extra_script.WriteToFile(output_file)

  output_file.write("""</head>
<body>
""")

  output_file.write("""</body>
</html>
""")
