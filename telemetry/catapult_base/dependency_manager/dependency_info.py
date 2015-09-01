# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class DependencyInfo(object):
  def __init__(self, dependency, platform, config_file, cs_bucket=None,
               cs_hash=None, download_path=None, cs_remote_path=None,
               local_paths=None):
    """ Container for the information needed for each dependency/platform pair
    in the dependency_manager.

    Information about the file:
      dependency: Name of the dependency.
      platform: Name of the platform to be run on.
      config_file: Path to the config_file this information came from. Used for
                   error messages to improve debugging.

    Information used for downloading from cloud storage:
      cs_bucket: The cloud_storage bucket the dependency is located in.
      cs_hash: The hash of the file stored in cloud_storage.
      download_path: Where the file should be downloaded to.
      cs_remote_path: Where the file is stored in the cloud_storage bucket.

    local_paths: A list of paths to search in order for a local file.
    """
    # TODO(aiolos): update the above doc string for A) the usage of zip files
    # and B) supporting lists of local_paths to be checked for most recently
    # changed files.
    if not dependency or not platform:
      raise ValueError(
          'Must supply both a dependency and platform to DependencyInfo')

    self._dependency = dependency
    self._platform = platform
    self._config_files = [config_file]
    self._local_paths = local_paths or []
    self._download_path = download_path
    self._cs_remote_path = cs_remote_path
    self._cs_bucket = cs_bucket
    self._cs_hash = cs_hash
    self.VerifyCloudStorageInfo()

  def Update(self, new_dep_info, append_to_front):
    """Add the information from |new_dep_info| to this instance.

    append_to_front: Whether new local_paths should be appended to the front of
    the local_paths list, or the end.
    """
    self._config_files.extend(new_dep_info.config_files)
    if (self.dependency != new_dep_info.dependency or
        self.platform != new_dep_info.platform):
      raise ValueError(
          'Cannot update DependencyInfo with different dependency or platform.'
          'Existing dep: %s, existing platform: %s. New dep: %s, new platform:'
          '%s. Config_files conflicting: %s' % (
              self.dependency, self.platform, new_dep_info.dependency,
              new_dep_info.platform, self.config_files))
    if new_dep_info.has_cs_info:
      if self.has_cs_info:
        raise ValueError(
            'Overriding cloud_storage data is not allowed when updating a '
            'DependencyInfo. Conflict in dependency %s on platform %s in '
            'config_files: %s.' % (self.dependency, self.platform,
                                  self.config_files))
      else:
        self._download_path = new_dep_info.download_path
        self._cs_remote_path = new_dep_info.cs_remote_path
        self._cs_bucket = new_dep_info.cs_bucket
        self._cs_hash = new_dep_info.cs_hash
    if new_dep_info.local_paths:
      if append_to_front:
        self._local_paths = [path for path in self._local_paths if
                             path not in new_dep_info.local_paths]
        self._local_paths[0:0] = new_dep_info.local_paths
      else:
        for path in new_dep_info.local_paths:
          if path not in self._local_paths:
            self._local_paths.append(path)

  @property
  def dependency(self):
    return self._dependency

  @property
  def platform(self):
    return self._platform

  @property
  def config_files(self):
    return self._config_files

  @property
  def local_paths(self):
    return self._local_paths

  @property
  def download_path(self):
    return self._download_path

  @property
  def cs_remote_path(self):
    return self._cs_remote_path

  @property
  def cs_bucket(self):
    return self._cs_bucket

  @property
  def cs_hash(self):
    return self._cs_hash

  @property
  def has_cs_info(self):
    self.VerifyCloudStorageInfo()
    return self.cs_hash

  def VerifyCloudStorageInfo(self):
    """Ensure either all or none of the needed remote information is specified.
    """
    if ((self.cs_bucket or self.cs_remote_path or self.download_path or
         self.cs_hash) and not (self.cs_bucket and self.cs_remote_path and
                                self.download_path and self.cs_hash)):
      raise ValueError(
            'Attempted to partially initialize cloud storage data for '
            'dependency: %s, platform: %s, download_path: %s, '
            'cs_remote_path: %s, cs_bucket %s, cs_hash %s' % (
                self.dependency, self.platform, self.download_path,
                self.cs_remote_path, self.cs_bucket, self.cs_hash))

