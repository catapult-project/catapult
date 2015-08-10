# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class UnsupportedConfigFormatError(ValueError):
  def __init__(self, config_type, config_file):
    if not config_type:
      message = ('The json file at %s is unsupported by the dependency_manager '
                 'due to no specified config type' % config_file)
    else:
      message = ('The json file at %s has config type %s, which is unsupported '
                 'by the dependency manager.' % (config_file, config_type))
    super(UnsupportedConfigFormatError, self).__init__(message)


class EmptyConfigError(ValueError):
  def __init__(self, file_path):
    super(EmptyConfigError, self).__init__('Empty config at %s.' % file_path)


class ConfigConflictError(Exception):
  def __init__(self, config_files, conflict):
    super(ConfigConflictError, self).__init__(
        'Multiple definitions of %s found in given config files: %s .'
        'Only overrides of local_path are allowed.' % (config_files, conflict))


class FileNotFoundError(Exception):
  def __init__(self, file_path):
    super(FileNotFoundError, self).__init__('No file found at %s' % file_path)


class NoPathFoundError(FileNotFoundError):
  def __init__(self, dependency, platform, arch):
    super(NoPathFoundError, self).__init__(
        'No file could be found locally, and no file to download from cloud '
        'storage for %s on platform %s and arch %s' % (dependency, platform,
                                                       arch))


class DependencyManager(object):
  def __init__(self, config_files):
    pass

  def FetchPath(self, dependency, platform, arch):
    """Find the given dependency in the locations given in configs.

    Return a path to the appropriate executable for |dependency|,
    downloading from cloud storage if needed, or None if it cannot be found.
    """
    raise NotImplementedError

  def LocalPath(self, dependency, platform, arch):
    """Get a local version of the dependency from locations given in configs.

    Return a local path to |dependency|, or None if an executable cannot be
    found. Will not download the executable.
    """
    raise NotImplementedError

  def UpdateCloudStorageDependency(
      self, dependency, platform, arch, version=None):
    """Update the cloud storage hash and the version for the given dependency.
    """
    raise NotImplementedError

  def GetVersion(self, dependency, platform, arch):
    """Return the Version information for the given dependency.
    """
    raise NotImplementedError

  def _UpdateDependencies(self, config_file):
    raise NotImplementedError

  def _GetDependencyInfo(self, dependency, platform, arch):
    raise NotImplementedError

  @staticmethod
  def _LocalPath(dependency_info):
    raise NotImplementedError

  @staticmethod
  def _CloudStoragePath(dependency_info):
    raise NotImplementedError

