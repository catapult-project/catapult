# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import fnmatch
import imp
import logging
import modulefinder
import optparse
import os
import sys
import zipfile

from telemetry import benchmark
from telemetry.core import command_line
from telemetry.core import discover
from telemetry.core import util
from telemetry.util import bootstrap
from telemetry.util import cloud_storage
from telemetry.util import path_set

DEPS_FILE = 'bootstrap_deps'


def _InDirectory(subdirectory, directory):
  subdirectory = os.path.realpath(subdirectory)
  directory = os.path.realpath(directory)
  common_prefix = os.path.commonprefix([subdirectory, directory])
  return common_prefix == directory


def FindBootstrapDependencies(base_dir):
  deps_file = os.path.join(base_dir, DEPS_FILE)
  if not os.path.exists(deps_file):
    return []
  deps_paths = bootstrap.ListAllDepsPaths(deps_file)
  return set(
      os.path.realpath(os.path.join(util.GetChromiumSrcDir(), os.pardir, path))
      for path in deps_paths)


def FindPythonDependencies(module_path):
  logging.info('Finding Python dependencies of %s' % module_path)

  # Load the module to inherit its sys.path modifications.
  imp.load_source(
      os.path.splitext(os.path.basename(module_path))[0], module_path)

  # Analyze the module for its imports.
  finder = modulefinder.ModuleFinder()
  finder.run_script(module_path)

  # Filter for only imports in Chromium.
  for module in finder.modules.itervalues():
    # If it's an __init__.py, module.__path__ gives the package's folder.
    module_path = module.__path__[0] if module.__path__ else module.__file__
    if not module_path:
      continue

    module_path = os.path.realpath(module_path)
    if not _InDirectory(module_path, util.GetChromiumSrcDir()):
      continue

    yield module_path


def FindPageSetDependencies(base_dir):
  logging.info('Finding page sets in %s' % base_dir)

  # Add base_dir to path so our imports relative to base_dir will work.
  sys.path.append(base_dir)
  tests = discover.DiscoverClasses(base_dir, base_dir, benchmark.Benchmark,
                                   index_by_class_name=True)

  for test_class in tests.itervalues():
    test_obj = test_class()

    # Ensure the test's default options are set if needed.
    parser = optparse.OptionParser()
    test_obj.AddCommandLineArgs(parser)
    options = optparse.Values()
    for k, v in parser.get_default_values().__dict__.iteritems():
      options.ensure_value(k, v)

    # Page set paths are relative to their runner script, not relative to us.
    util.GetBaseDir = lambda: base_dir
    # TODO: Loading the page set will automatically download its Cloud Storage
    # deps. This is really expensive, and we don't want to do this by default.
    page_set = test_obj.CreatePageSet(options)

    # Add all of its serving_dirs as dependencies.
    for serving_dir in page_set.serving_dirs:
      yield serving_dir
    for page in page_set:
      if page.is_file:
        yield page.serving_dir


def FindExcludedFiles(files, options):
  def MatchesConditions(path, conditions):
    for condition in conditions:
      if condition(path):
        return True
    return False

  # Define some filters for files.
  def IsHidden(path):
    for pathname_component in path.split(os.sep):
      if pathname_component.startswith('.'):
        return True
    return False
  def IsPyc(path):
    return os.path.splitext(path)[1] == '.pyc'
  def IsInCloudStorage(path):
    return os.path.exists(path + '.sha1')
  def MatchesExcludeOptions(path):
    for pattern in options.exclude:
      if (fnmatch.fnmatch(path, pattern) or
          fnmatch.fnmatch(os.path.basename(path), pattern)):
        return True
    return False

  # Collect filters we're going to use to exclude files.
  exclude_conditions = [
      IsHidden,
      IsPyc,
      IsInCloudStorage,
      MatchesExcludeOptions,
  ]

  # Check all the files against the filters.
  for path in files:
    if MatchesConditions(path, exclude_conditions):
      yield path


def FindDependencies(paths, options):
  # Verify arguments.
  for path in paths:
    if not os.path.exists(path):
      raise ValueError('Path does not exist: %s' % path)

  dependencies = path_set.PathSet()

  # Including __init__.py will include Telemetry and its dependencies.
  # If the user doesn't pass any arguments, we just have Telemetry.
  dependencies |= FindPythonDependencies(os.path.realpath(
    os.path.join(util.GetTelemetryDir(), 'telemetry', '__init__.py')))
  dependencies |= FindBootstrapDependencies(util.GetTelemetryDir())

  # Add dependencies.
  for path in paths:
    base_dir = os.path.dirname(os.path.realpath(path))

    dependencies.add(base_dir)
    dependencies |= FindBootstrapDependencies(base_dir)
    dependencies |= FindPythonDependencies(path)
    if options.include_page_set_data:
      dependencies |= FindPageSetDependencies(base_dir)

  # Remove excluded files.
  dependencies -= FindExcludedFiles(set(dependencies), options)

  return dependencies


def ZipDependencies(paths, dependencies, options):
  base_dir = os.path.dirname(os.path.realpath(util.GetChromiumSrcDir()))

  with zipfile.ZipFile(options.zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
    # Add dependencies to archive.
    for path in dependencies:
      path_in_archive = os.path.join(
          'telemetry', os.path.relpath(path, base_dir))
      zip_file.write(path, path_in_archive)

    # Add symlinks to executable paths, for ease of use.
    for path in paths:
      link_info = zipfile.ZipInfo(
          os.path.join('telemetry', os.path.basename(path)))
      link_info.create_system = 3  # Unix attributes.
      # 010 is regular file, 0111 is the permission bits rwxrwxrwx.
      link_info.external_attr = 0100777 << 16  # Octal.

      relative_path = os.path.relpath(path, base_dir)
      link_script = (
          '#!/usr/bin/env python\n\n'
          'import os\n'
          'import sys\n\n\n'
          'script = os.path.join(os.path.dirname(__file__), \'%s\')\n'
          'os.execv(sys.executable, [sys.executable, script] + sys.argv[1:])'
        % relative_path)

      zip_file.writestr(link_info, link_script)

    # Add gsutil to the archive, if it's available. The gsutil in
    # depot_tools is modified to allow authentication using prodaccess.
    # TODO: If there's a gsutil in telemetry/third_party/, bootstrap_deps
    # will include it. Then there will be two copies of gsutil at the same
    # location in the archive. This can be confusing for users.
    gsutil_path = os.path.realpath(cloud_storage.FindGsutil())
    if cloud_storage.SupportsProdaccess(gsutil_path):
      gsutil_base_dir = os.path.join(os.path.dirname(gsutil_path), os.pardir)
      gsutil_dependencies = path_set.PathSet()
      gsutil_dependencies.add(os.path.dirname(gsutil_path))
      # Also add modules from depot_tools that are needed by gsutil.
      gsutil_dependencies.add(os.path.join(gsutil_base_dir, 'boto'))
      gsutil_dependencies.add(os.path.join(gsutil_base_dir, 'fancy_urllib'))
      gsutil_dependencies.add(os.path.join(gsutil_base_dir, 'retry_decorator'))
      gsutil_dependencies -= FindExcludedFiles(
          set(gsutil_dependencies), options)

      # Also add upload.py to the archive from depot_tools, if it is available.
      # This allows us to post patches without requiring a full depot_tools
      # install. There's no real point in including upload.py if we do not
      # also have gsutil, which is why this is inside the gsutil block.
      gsutil_dependencies.add(os.path.join(gsutil_base_dir, 'upload.py'))

      for path in gsutil_dependencies:
        path_in_archive = os.path.join(
            'telemetry', os.path.relpath(util.GetTelemetryDir(), base_dir),
            'third_party', os.path.relpath(path, gsutil_base_dir))
        zip_file.write(path, path_in_archive)


class FindDependenciesCommand(command_line.OptparseCommand):
  """Prints all dependencies"""

  @classmethod
  def AddCommandLineArgs(cls, parser):
    parser.add_option(
        '-v', '--verbose', action='count', dest='verbosity',
        help='Increase verbosity level (repeat as needed).')

    parser.add_option(
        '-p', '--include-page-set-data', action='store_true', default=False,
        help='Scan tests for page set data and include them.')

    parser.add_option(
        '-e', '--exclude', action='append', default=[],
        help='Exclude paths matching EXCLUDE. Can be used multiple times.')

    parser.add_option(
        '-z', '--zip',
        help='Store files in a zip archive at ZIP.')

  @classmethod
  def ProcessCommandLineArgs(cls, parser, args):
    if args.verbosity >= 2:
      logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbosity:
      logging.getLogger().setLevel(logging.INFO)
    else:
      logging.getLogger().setLevel(logging.WARNING)

  def Run(self, args):
    paths = args.positional_args
    dependencies = FindDependencies(paths, args)
    if args.zip:
      ZipDependencies(paths, dependencies, args)
      print 'Zip archive written to %s.' % args.zip
    else:
      print '\n'.join(sorted(dependencies))
    return 0
