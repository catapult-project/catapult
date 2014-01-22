# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""ResourceFinder is a helper class for finding resources given their name."""

import os
from tvcm import module

class ResolvedFile(object):
  """Represents a file path with a known absolute path."""
  def __init__(self, toplevel_dir, absolute_path):
    self.toplevel_dir = toplevel_dir
    self.absolute_path = absolute_path

  @property
  def relative_path(self):
    """The path to the file from the top-level directory"""
    return os.path.relpath(self.absolute_path, self.toplevel_dir)


class ResourceFinder(object):
  """Helper class for finding a module given a name and current module.

  The dependency resolution code in Module.resolve will find bits of code in the
  actual javascript that says things require('bar'). This
  code is responsible for figuring out what filename corresponds to 'bar' given
  a Module('foo').
  """
  def __init__(self, search_paths):
    assert isinstance(search_paths, list)
    self._search_paths = [os.path.abspath(path) for path in search_paths]

  @property
  def search_paths(self):
    """A list of base directories to search for modules under."""
    return self._search_paths

  def resolve(self, some_path):
    """Returns a ResolvedFile for the given path.

    Args:
      some_path: A relative or absolute path to a file.

    Returns:
      A (path, contents) pair.
    """
    if os.path.isabs(some_path):
      return self.resolve_absolute(some_path)
    else:
      return self.resolve_relative(some_path)

  def resolve_absolute(self, absolute_path):
    """Returns a ResolvedFile for the given absolute path."""
    for search_path in self._search_paths:
      if absolute_path.startswith(search_path):
        return ResolvedFile(search_path, absolute_path)
    return None

  def resolve_relative(self, relative_path):
    """Returns a ResolvedFile for the given relative path."""
    absolute_path = None
    for search_path in self._search_paths:
      absolute_path = os.path.join(search_path, relative_path)
      if os.path.exists(absolute_path):
        return ResolvedFile(search_path, absolute_path)
    return None


  # The current_module argument isn't directly used, but a field is checked.
  # pylint: disable=W0613
  def _find_and_load(self, current_module, requested_name, extension):
    """Searches for a file and reads its contents.

    Args:
      current_module: The Module that is requiring this resource.
      requested_name: The name of the resource that was requested.
      extension: The extension for this requested resource.

    Returns:
      A (path, contents) pair.
    """
    assert current_module.filename
    pathy_name = requested_name.replace('.', os.sep)
    filename = pathy_name + extension

    resolved = self.resolve_relative(filename)
    if not resolved:
      return None, None
    return _read_file(resolved.absolute_path)

  def find_and_load_module(self, current_module, requested_module_name):
    """Finds a module javascript file and returns a (path, contents) pair."""
    js_candidate, js_candidate_contents = self._find_and_load(current_module, requested_module_name, '.js')
    html_candidate, html_candidate_contents = self._find_and_load(current_module, requested_module_name, '.html')
    if js_candidate and html_candidate:
      if module.Module.html_contents_is_polymer_module(html_candidate_contents):
        return html_candidate, html_candidate_contents
      return js_candidate, js_candidate_contents
    elif js_candidate:
      return js_candidate, js_candidate_contents
    return html_candidate, html_candidate_contents

  def find_and_load_raw_script(self, current_module, filename):
    """Finds a raw javascript file and returns a (path, contents) pair."""
    resolved = self.resolve_relative(filename)
    if not resolved:
      return None, None
    return _read_file(resolved.absolute_path)

  def find_and_load_style_sheet(self,
                                current_module, requested_style_sheet_name):
    """Finds a stylesheet file and returns a (path, contents) pair."""
    return self._find_and_load(
      current_module, requested_style_sheet_name, '.css')

  def find_and_load_html_template(self,
                                  current_module, requested_html_template_name):
    """Finds a html template file and returns a (path, contents) pair."""
    return self._find_and_load(
      current_module, requested_html_template_name, '.html')

def _read_file(absolute_path):
  """Reads a file and returns a (path, contents) pair.

  Args:
    absolute_path: Absolute path to a file.

  Raises:
    Exception: The given file doesn't exist.
    IOError: There was a problem opening or reading the file.
  """
  if not os.path.exists(absolute_path):
    raise Exception('%s not found.' % absolute_path)
  f = open(absolute_path, 'r')
  contents = f.read()
  f.close()
  return absolute_path, contents
