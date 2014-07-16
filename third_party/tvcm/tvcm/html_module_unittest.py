# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest

from tvcm import fake_fs
from tvcm import generate
from tvcm import html_module
from tvcm import module
from tvcm import parse_html_deps
from tvcm import project as project_module
from tvcm import resource
from tvcm import resource_loader as resource_loader
from tvcm import strip_js_comments

class ResourceWithFakeContents(resource.Resource):
  def __init__(self, toplevel_dir, absolute_path, fake_contents):
    """A resource with explicitly provided contents.

    If the resource does not exist, then pass fake_contents=None. This will
    cause accessing the resource contents to raise an exception mimicking the
    behavior of regular resources."""
    super(ResourceWithFakeContents, self).__init__(toplevel_dir, absolute_path)
    self._fake_contents = fake_contents

  @property
  def contents(self):
    if self._fake_contents == None:
      raise Exception('File not found')
    return self._fake_contents

class FakeLoader(object):
  def __init__(self, source_paths, initial_filenames_and_contents=None):
    self._source_paths = source_paths
    self._file_contents = {}
    if initial_filenames_and_contents:
      for k,v in initial_filenames_and_contents.iteritems():
        self._file_contents[k] = v

  def FindResourceGivenAbsolutePath(self, absolute_path):
    candidate_paths = []
    for source_path in self._source_paths:
      if absolute_path.startswith(source_path):
        candidate_paths.append(source_path)
    if len(candidate_paths) == 0:
      return None

    # Sort by length. Longest match wins.
    candidate_paths.sort(lambda x, y: len(x) - len(y))
    longest_candidate = candidate_paths[-1]

    return ResourceWithFakeContents(longest_candidate, absolute_path,
                                    self._file_contents.get(absolute_path, None))

  def FindResourceGivenRelativePath(self, relative_path):
    absolute_path = None
    for script_path in self._source_paths:
      absolute_path = os.path.join(script_path, relative_path)
      if absolute_path in self._file_contents:
        return ResourceWithFakeContents(script_path, absolute_path,
                                        self._file_contents[absolute_path])
    return None


class ParseTests(unittest.TestCase):
  def testMissingDocType(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = False

    file_contents = {}

    def DoIt():
      html_module.Parse(FakeLoader(["/tmp"], file_contents),
                        "a.b.start",
                        "/tmp/a/b/",
                        parse_results)
    self.assertRaises(Exception, DoIt)

  def testValidExternalScriptReferenceToModule(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_external.append('../foo.js')

    file_contents = {}
    file_contents['/tmp/a/foo.js'] = """
'use strict';
tvcm.exportTo('foo', function() {
});"""

    metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer', 'a.foo'], metadata.dependent_module_names)


  def testValidExternalScriptReferenceToRawScript(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_external.append('../foo.js')

    file_contents = {}
    file_contents['/tmp/a/foo.js'] = """
'i am just some raw script';
"""

    metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer'], metadata.dependent_module_names)
    self.assertEquals(['a/foo.js'], metadata.dependent_raw_script_relative_paths)


  def testExternalScriptReferenceToModuleOutsideScriptPath(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_external.append('/foo.js')

    file_contents = {}
    file_contents['/foo.js'] = ''

    def DoIt():
      html_module.Parse(FakeLoader(["/tmp"], file_contents),
                        "a.b.start",
                        "/tmp/a/b/",
                        parse_results)
    self.assertRaises(Exception, DoIt)

  def testExternalScriptReferenceToFileThatDoesntExist(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_external.append('/foo.js')

    file_contents = {}

    def DoIt():
      html_module.Parse(FakeLoader(["/tmp"], file_contents),
                        "a.b.start",
                        "/tmp/a/b/",
                        parse_results)
    self.assertRaises(Exception, DoIt)

  def testTVCMRequiresInsideInlineScriptTags(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_inline.append("""
    'use strict';
    tvcm.require('a.foo');
    tvcm.requireRawScript('a/raw.js');
    tvcm.requireStylesheet('a.bar');
    tvcm.requireTemplate('a.foo');
    """)

    file_contents = {}
    file_contents['/tmp/a/foo.js'] = """
"""
    file_contents['/tmp/a/raw.js'] = """
"""
    file_contents['/tmp/a/bar.css'] = """
"""
    file_contents['/tmp/a/foo.html'] = """
"""
    metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer', 'a.foo'], metadata.dependent_module_names)
    self.assertEquals(['a/raw.js'], metadata.dependent_raw_script_relative_paths)
    self.assertEquals(['a.bar'], metadata.style_sheet_names)
    self.assertEquals(['a.foo'], metadata.html_template_names)

  def testInlineScriptWithoutStrictNote(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_inline.append("""
console.log('Logging without strict mode is no fun.');
""")

    file_contents = {}
    def DoIt():
      metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                   "a.b.start",
                                   "/tmp/a/b/",
                                   parse_results)
    self.assertRaises(Exception, DoIt)

  def testValidImportOfModule(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.imports.append('../foo.html')

    file_contents = {}
    file_contents['/tmp/a/foo.html'] = """
"""

    metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer', 'a.foo'], metadata.dependent_module_names)

  def testStyleSheetImport(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.stylesheets.append('../foo.css')

    file_contents = {}
    file_contents['/tmp/a/foo.css'] = """
"""
    metadata = html_module.Parse(FakeLoader(["/tmp"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer'], metadata.dependent_module_names)
    self.assertEquals(['a.foo'], metadata.style_sheet_names)

  def testUsingAbsoluteHref(self):
    parse_results = parse_html_deps.HTMLModuleParserResults()
    parse_results.has_decl = True
    parse_results.scripts_external.append('/foo.js')

    file_contents = {}
    file_contents['/src/foo.js'] = """
'use strict';
tvcm.requireRawScript('b.c');
tvcm.exportTo('foo', function() {
});"""

    metadata = html_module.Parse(FakeLoader(["/tmp", "/src"], file_contents),
                                 "a.b.start",
                                 "/tmp/a/b/",
                                 parse_results)
    self.assertEquals(['tvcm', 'tvcm.polymer', 'foo'], metadata.dependent_module_names)


class HTMLModuleTests(unittest.TestCase):
  def testBasic(self):
    file_contents = {}
    file_contents['/tmp/a/b/start.html'] = """
<!DOCTYPE html>
<link rel="import" href="/widget.html">
<link rel="stylesheet" href="../common.css">
<script src="/raw_script.js"></script>
<script src="../old_tvcm_component_1.js"></script>
<polymer-element name="start">
  <template>
  </template>
  <script>
    'use strict';
    tvcm.require("a.old_tvcm_component_3");
    console.log('inline script for start.html got written');
  </script>
</polymer-element>
"""
    file_contents['/tvcm/tvcm/__init__.js'] = """
'use strict';
tvcm.exportTo('a', function() {
});
"""
    file_contents['/tvcm/tvcm/polymer.js'] = """
'use strict';
tvcm.exportTo('a', function() {
});
"""
    file_contents['/components/widget.html'] = """
<!DOCTYPE html>
<widget name="widget.html"></widget>
<script>
'use strict';
console.log('inline script for widget.html');
</script>
"""
    file_contents['/tmp/a/common.css'] = """
/* /tmp/a/common.css was written */
"""
    file_contents['/raw/raw_script.js'] = """
console.log('/raw/raw_script.js was written');
"""
    file_contents['/tmp/a/old_tvcm_component_1.js'] = """
'use strict';
tvcm.require('a.old_tvcm_component_2')
console.log('/tmp/a/old_tvcm_component_1.js was written');
tvcm.exportTo('a', function() {
});
"""
    file_contents['/tmp/a/old_tvcm_component_2.js'] = """
'use strict';
console.log('/tmp/a/old_tvcm_component_2.js was written');
tvcm.exportTo('a', function() {
});
"""
    file_contents['/tmp/a/old_tvcm_component_3.js'] = """
'use strict';
console.log('/tmp/a/old_tvcm_component_3.js was written');
tvcm.exportTo('a', function() {
});
"""
    with fake_fs.FakeFS(file_contents):
      project = project_module.Project(['/tvcm/', '/tmp/', '/components/', '/raw/'],
                                       include_tvcm_paths=False)
      loader = resource_loader.ResourceLoader(project)
      a_b_start_module = loader.LoadModule(module_name='a.b.start')
      load_sequence = project.CalcLoadSequenceForModules([a_b_start_module])

      # Check load sequence names.
      load_sequence_names = [x.name for x in load_sequence]
      self.assertEquals(['tvcm', 'tvcm.polymer',
                         'a.old_tvcm_component_2', 'a.old_tvcm_component_1',
                         'widget',
                         'a.old_tvcm_component_3',
                         'a.b.start'], load_sequence_names)


      # Check module_deps on a_b_start_module
      def HasDependentModule(module, name):
        return [x for x in module.dependent_modules
                if x.name == name]
      assert HasDependentModule(a_b_start_module, 'a.old_tvcm_component_1')

      # Check JS generation.
      js = generate.GenerateJS(load_sequence)
      assert 'inline script for start.html' in js
      assert 'inline script for widget.html' in js
      assert '/raw/raw_script.js' in js
      assert '/tmp/a/old_tvcm_component_1.js' in js
      assert '/tmp/a/old_tvcm_component_2.js' in js
      assert '/tmp/a/old_tvcm_component_3.js' in js

      # Check HTML generation.
      html = generate.GenerateStandaloneHTMLAsString(load_sequence, title='',
                                                     flattened_js_url="/blah.js")
      assert '<polymer-element name="start">' in html
      assert 'inline script for widget.html' not in html
      assert 'common.css' in html
