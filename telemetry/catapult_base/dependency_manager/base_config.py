# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os

from catapult_base.dependency_manager import dependency_info
from catapult_base.dependency_manager import exceptions


class BaseConfig(object):
  """A basic config class for use with the DependencyManager.

  Initiated with a json file in the following format:

            {  "config_type": "BaseConfig",
               "dependencies": {
                 "dep_name1": {
                   "cloud_storage_base_folder": "base_folder1",
                   "cloud_storage_bucket": "bucket1",
                   "file_info": {
                     "platform1": {
                        "cloud_storage_hash": "hash_for_platform1",
                        "download_path": "download_path111",
                        "version_in_cs": "1.11.1.11."
                        "local_paths": ["local_path1110", "local_path1111"]
                      },
                      "platform2": {
                        "cloud_storage_hash": "hash_for_platform2",
                        "download_path": "download_path2",
                        "local_paths": ["local_path20", "local_path21"]
                      },
                      ...
                   }
                 },
                 "dependency_name_2": {
                    ...
                 },
                  ...
              }
            }

    Required fields: "dependencies" and "config_type".
                     Note that config_type must be "BaseConfig"

    Assumptions:
        "cloud_storage_base_folder" is a top level folder in the given
          "cloud_storage_bucket" where all of the dependency files are stored
          at "dependency_name"_"cloud_storage_hash".

        "download_path" and all paths in "local_paths" are relative to the
          config file's location.

        All or none of the following cloud storage related fields must be
          included in each platform dictionary:
          "cloud_storage_hash", "download_path", "cs_remote_path"

        "version_in_cs" is an optional cloud storage field, but is dependent
          on the above cloud storage related fields.


    Also note that platform names are often of the form os_architechture.
    Ex: "win_AMD64"

    More information on the fields can be found in dependencies_info.py
  """
  def __init__(self, file_path, writable=False):
    """ Initialize a BaseConfig for the DependencyManager.

    Args:
        writable: False: This config will be used to lookup information.
                  True: This config will be used to update information.

        file_path: Path to a file containing a json dictionary in the expected
                   json format for this config class. Base format expected:

                   { "config_type": config_type,
                     "dependencies": dependencies_dict }

                   config_type: must match the return value of GetConfigType.
                   dependencies: A dictionary with the information needed to
                       create dependency_info instances for the given
                       dependencies.

                   See dependency_info.py for more information.
    """
    self._config_path = file_path
    self._writable = writable
    if not file_path:
      raise ValueError('Must supply config file path.')
    if not os.path.exists(file_path):
      if not writable:
        raise exceptions.EmptyConfigError(file_path)
      self._config_data = {}
      self.CreateEmptyConfig(file_path)
    else:
      with open(file_path, 'r') as f:
        config_data = json.load(f)
      if not config_data:
        raise exceptions.EmptyConfigError(file_path)
      config_type = config_data.pop('config_type', None)
      if config_type != self.GetConfigType():
        raise ValueError(
            'Supplied config_type (%s) is not the expected type (%s) in file '
            '%s' % (config_type, self.GetConfigType(), file_path))
      self._config_data = config_data.get('dependencies', {})

  def IterDependencyInfo(self):
    """ Yields a DependencyInfo for each dependency/platform pair.

    Raises:
        ReadWriteError: If called when the config is writable.
        ValueError: If any of the dependencies contain partial information for
            downloading from cloud_storage. (See dependency_info.py)
    """
    if self._writable:
      raise exceptions.ReadWriteError(
          'Trying to read dependency info from a  writable config. File for '
          'config: %s' % self._config_path)
    for dep in self._config_data:

      base_path = os.path.dirname(self._config_path)
      dependency_dict = self._config_data.get(dep, {})
      platforms_dict = dependency_dict.get('file_info')
      cs_bucket = dependency_dict.get('cloud_storage_bucket', None)
      cs_base_folder = dependency_dict.get('cloud_storage_base_folder', '')
      for platform in platforms_dict:
        platform_info = platforms_dict.get(platform)
        local_paths = platform_info.get('local_paths', [])
        if local_paths:
          paths = []
          for path in local_paths:
            path = self._FormatPath(path)
            paths.append(os.path.abspath(os.path.join(base_path, path)))
          local_paths = paths

        download_path = platform_info.get('download_path', None)
        if download_path:
          download_path = self._FormatPath(download_path)
          download_path = os.path.abspath(
              os.path.join(base_path, download_path))

        cs_remote_path = None
        cs_hash = platform_info.get('cloud_storage_hash', None)
        if cs_hash:
          cs_remote_file = '%s_%s' % (dep, cs_hash)
          cs_remote_path = cs_remote_file if not cs_base_folder else (
              '%s/%s' % (cs_base_folder, cs_remote_file))

        version_in_cs = platform_info.get('version_in_cs', None)

        if download_path or cs_remote_path or cs_hash or version_in_cs:
          dep_info = dependency_info.DependencyInfo(
              dep, platform, self._config_path, cs_bucket=cs_bucket,
              cs_remote_path=cs_remote_path, download_path=download_path,
              cs_hash=cs_hash, version_in_cs=version_in_cs,
              local_paths=local_paths)
        else:
          dep_info = dependency_info.DependencyInfo(
              dep, platform, self._config_path, local_paths=local_paths)
        yield dep_info

  @classmethod
  def CreateEmptyConfig(cls, file_path):
    """Create an empty BaseConfig json dict and write it out to |file_path|.

    Raises:
        ValueError: If the path already exists.
    """
    if os.path.exists(file_path):
      raise ValueError('File already exists, and would be overwritten.')
    json_dict = {'config_type': cls.GetConfigType(),
                 'dependencies': {}}
    with open(file_path, 'w') as outfile:
      json.dump(json_dict, outfile, indent=2, sort_keys=True)
    return json_dict

  @classmethod
  def GetConfigType(cls):
    return 'BaseConfig'

  @property
  def config_path(self):
    return self._config_path

  def UpdateCloudStorageDependency(
      self, dependency, platform, dependency_path, version=None):
    """Update the cloud storage hash and the version for the given dependency.
    """
    # TODO(aiolos): Only allow the config to be updated if writable is True to
    # avoid data changing underneath the dependency manager.
    raise NotImplementedError

  def GetVersion(self, dependency, platform):
    """Return the Version information for the given dependency."""
    if not self._config_data(dependency):
      raise ValueError('Dependency %s is not in config.' % dependency)
    if not self.config_data[dependency].get(platform):
      raise ValueError('Dependency %s has no information for platform %s in '
                       'this config.' % (dependency, platform))
    return self._config_data[dependency][platform].get('version_in_cs')

  @classmethod
  def _FormatPath(cls, file_path):
    """Format |file_path| for the current file system.

    We may be downloading files for another platform, so paths must be
    downloadable on the current system.
    """
    if not file_path:
      return file_path
    if os.path.sep != '\\':
      return file_path.replace('\\', os.path.sep)
    elif os.path.sep != '/':
      return file_path.replace('/', os.path.sep)
    return file_path

