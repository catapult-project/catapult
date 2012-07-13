# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import sys
import os
import re

class DepsException(Exception):
  pass

"""
The core of this script is the calc_load_sequence function. In total, this
walks over the provided javascript files and figures out their dependencies
using the module definitions provided in each file. This allows us to, for
example, have a pair of modules
   base.defineModule('foo').dependsOn('bar')...
and
   base.defineModule('bar').dependsOn('baz')...

calc_load_sequence(['foo']) will tell yield
   [Module('baz'), Module('bar'), Module('foo')]
which is, based on the dependencies, the correct sequence in which to load
those modules.
"""

class ResourceFinder(object):
  """Helper code for finding a module given a name and a currently active module.

  The dependency resolution code in Module.resolve will find bits of code in the
  actual javascript that says things defineModule('foo').dependsOn('bar'). This
  code is responsible for figuring out what filename corresponds to 'bar' given
  a Module('foo').
  """
  def __init__(self):
    pass

  def _find_and_load(self, current_module, requested_name, extension):
    assert current_module.filename
    cwd = os.path.dirname(current_module.filename)
    pathy_name = requested_name.replace(".", os.sep)
    filename = os.path.join(cwd, pathy_name + extension)
    filename = os.path.normpath(filename)

    if not os.path.exists(filename):
      return None, None

    f = open(filename, 'r')
    contents = f.read()
    f.close()

    return filename, contents

  def find_and_load_module(self, current_module, requested_module_name):
    return self._find_and_load(current_module, requested_module_name, ".js")

  def find_and_load_style_sheet(self,
                                current_module, requested_style_sheet_name):
    return self._find_and_load(
      current_module, requested_style_sheet_name, ".css")


class StyleSheet(object):
  """Represents a stylesheet resource referenced by a module via the
  base.defineModule().stylesheet(xxx) directive."""
  def __init__(self, name, filename, contents):
    self.name = name
    self.filename = filename
    self.contents = contents

  def __repr__(self):
    return "StyleSheet(%s)" % self.name

class Module(object):
  """Represents a javascript module. It can either be directly requested, e.g.
  passed in by name to calc_load_sequence, or created by being referenced a
  module via the base.defineModule().dependsOn(xxx) directive.

  Interesting properties on this object are:

  - filename: the file of the actual module
  - contents: the actual text contents of the module
  - style_sheets: StyleSheet objects that this module relies on for styling
    information.
  - dependent_modules: other modules that this module needs in order to run
  """
  def __init__(self, name = None):
    self.name = name
    self.filename = None
    self.contents = None

    self.dependent_module_names = []
    self.dependent_modules = []
    self.style_sheet_names = []
    self.style_sheets = []

  def __repr__(self):
    return "Module(%s)" % self.name

  def load_and_parse(self, module_filename,
                     module_contents = None,
                     decl_required = True):
    if not module_contents:
      f = open(module_filename, 'r')
      self.contents = f.read()
      f.close()
    else:
      self.contents = module_contents
    self.filename = module_filename
    self.parse_definition_(self.contents, decl_required)

  def resolve(self, all_resources, resource_finder):
    if "scripts" not in all_resources:
      all_resources["scripts"] = {}
    if "style_sheets" not in all_resources:
      all_resources["style_sheets"] = {}

    assert self.filename

    for name in self.dependent_module_names:
      if name in all_resources["scripts"]:
        assert all_resources["scripts"][name].contents
        self.dependent_modules.append(all_resources["scripts"][name])
        continue

      filename, contents = resource_finder.find_and_load_module(self, name)
      if not filename:
        raise DepsException("Could not find a file for module %s" % name)

      module = Module(name)
      all_resources["scripts"][name] = module
      self.dependent_modules.append(module)
      module.load_and_parse(filename, contents)
      module.resolve(all_resources, resource_finder)

    for name in self.style_sheet_names:
      if name in all_resources["style_sheets"]:
        assert all_resources["style_sheets"][name].contents
        self.style_sheets.append(all_resources["scripts"][name])
        continue

      filename, contents = resource_finder.find_and_load_style_sheet(self, name)
      if not filename:
        raise DepsException("Could not find a file for stylesheet %s" % name)

      style_sheet = StyleSheet(name, filename, contents)
      all_resources["style_sheets"][name] = style_sheet
      self.style_sheets.append(style_sheet)

  def compute_load_sequence_recursive(self, load_sequence, already_loaded_set):
    for dependent_module in self.dependent_modules:
      dependent_module.compute_load_sequence_recursive(load_sequence,
                                                       already_loaded_set)
    if self.name not in already_loaded_set:
      already_loaded_set.add(self.name)
      load_sequence.append(self)

  def parse_definition_(self, text, decl_required = True):
    if not decl_required and not self.name:
      raise Exception("Module.name must be set for decl_required to be false.")

    m = re.search("""base\s*\.\s*defineModule\((["'])(.+?)\\1\)""",
                  text, re.DOTALL)
    familiar_name = self.filename or self.name
    if not m:
      if decl_required:
        raise DepsExceptions(
          "For %s expected base.defineModule, but none found." % familiar_name)
      return

    if self.name:
      if self.name != m.group(2):
        raise DepsException(
          "For %s, base.defineModule(...) must be base.defineModule(%s)" %
          (familiar_name, self.name))
    else:
      self.name = m.group(2)

    rest = text[m.end():]

    stylesheet_regex = """\s*\.\s*stylesheet\((["'])(.+?)\\1\)"""

    got_stylesheet = False

    # Look for a stylesheet.
    m = re.match(stylesheet_regex, rest, re.DOTALL)
    if m:
      self.style_sheet_names.append(m.group(2))
      rest = rest[m.end():]
      got_stylesheet = True

    # Look for dependsOn.
    m = re.match("""\s*\.\s*dependsOn\((.*?)\)""", rest, re.DOTALL)
    if m:
      deps = re.split(",\s*", m.group(1))
      deps = [x for x in deps if len(x)]
      def stripquotes(x):
        n = re.match("""(["'])(.+)\\1""", x)
        assert n
        return n.group(2)
      sdeps = [stripquotes(x) for x in deps]
      self.dependent_module_names.extend(sdeps)
      rest = rest[m.end():]

    # Look for a stylesheet if it wasn't found before.
    if not got_stylesheet:
      m = re.match(stylesheet_regex, rest, re.DOTALL)
      if m:
        self.style_sheet_names.append(m.group(2))
        rest = rest[m.end():]
        got_stylesheet = True



def calc_load_sequence(filenames):
  """Given a list of starting javascript files, figure out all the Module
  objects that need to be loaded to satisfiy their dependencies.

  The javascript files shoud specify their dependencies in a format that is
  textually equivalent to base.js' defineModule syntax, namely:

    base.defineModule(moudleName)
          .dependsOn(module1, module2, ...)
          .stylesheet(stylesheet)
          .exportsTo(namespace, exportsFn)
          .runWhenLoaded(fn);

  The output of this function is an array of Module objects ordered by
  dependency.
  """

  all_resources = {}
  all_resources["scripts"] = {}
  toplevel_modules = []
  resource_finder = ResourceFinder()
  for filename in filenames:
    assert os.path.exists(filename)
    name  = os.path.splitext(os.path.basename(filename))[0]

    if name in all_resources["scripts"]:
      sys.stderr.write(
        "Warning: %s was brought in already, probably via dependencies." % name)
      continue

    module = Module(name)
    module.load_and_parse(filename, decl_required = False)
    all_resources["scripts"][module.name] = module
    toplevel_modules.append(module)
    module.resolve(all_resources, resource_finder)

  already_loaded_set = set()
  load_sequence = []
  for module in toplevel_modules:
    module.compute_load_sequence_recursive(load_sequence, already_loaded_set)
  return load_sequence
