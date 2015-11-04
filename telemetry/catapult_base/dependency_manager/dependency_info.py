# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

class DependencyInfo(object):
  def __init__(self, dependency, platform, config_file, cs_bucket=None,
               cs_hash=None, download_path=None, cs_remote_path=None,
               version_in_cs=None, path_within_archive=None, local_paths=None):
    """ Container for the information needed for each dependency/platform pair
    in the dependency_manager.

    Args:
        Required:
          dependency: Name of the dependency.
          platform: Name of the platform to be run on.
          config_file: Path to the config_file this information came from. Used
                       for error messages to improve debugging.

        Minimum required for downloading from cloud storage:
          cs_bucket: The cloud storage bucket the dependency is located in.
          cs_hash: The hash of the file stored in cloud storage.
          download_path: Where the file should be downloaded to.
          cs_remote_path: Where the file is stored in the cloud storage bucket.

        Optional for downloading from cloud storage:
          version_in_cs: The version of the file stored in cloud storage.
          path_within_archive: Specify if and how to handle zip archives
              downloaded from cloud_storage. Expected values:
                  None: Do not unzip the file downloaded from cloud_storage.
                  '.': Unzip the file downloaded from cloud_storage. The
                      unzipped file/folder is the expected dependency.
                  file_path: Unzip the file downloaded from cloud_storage.
                      |file_path| is the path to the expected dependency,
                      relative to the unzipped archive location.

        Optional:
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
    self._version_in_cs = version_in_cs
    if download_path and path_within_archive:
      self._unzip_location = os.path.abspath(os.path.join(
          os.path.dirname(download_path), '%s_%s' % (dependency, platform)))
      self._path_within_archive = path_within_archive
    else:
      if path_within_archive:
        raise ValueError(
          'Cannot specify archive information without a download path.'
          'path_within_archive: %s, download_path: %s' % (
            path_within_archive, download_path))
      self._unzip_location = None
      self._path_within_archive = None
    self.VerifyCloudStorageInfo()

  def Update(self, new_dep_info):
    """Add the information from |new_dep_info| to this instance.
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
            'Overriding cloud storage data is not allowed when updating a '
            'DependencyInfo. Conflict in dependency %s on platform %s in '
            'config_files: %s.' % (self.dependency, self.platform,
                                  self.config_files))
      else:
        self._download_path = new_dep_info.download_path
        self._cs_remote_path = new_dep_info.cs_remote_path
        self._cs_bucket = new_dep_info.cs_bucket
        self._cs_hash = new_dep_info.cs_hash
        self._version_in_cs = new_dep_info.version_in_cs
        self._path_within_archive = new_dep_info.path_within_archive
        self.VerifyCloudStorageInfo()
    if new_dep_info.local_paths:
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
  def version_in_cs(self):
    return self._version_in_cs

  @property
  def path_within_archive(self):
    return self._path_within_archive

  @property
  def unzip_location(self):
    return self._unzip_location

  @property
  def has_cs_info(self):
    return any([self.cs_bucket, self.cs_remote_path, self.download_path,
                self.cs_hash, self.version_in_cs, self.path_within_archive,
                self.unzip_location])

  @property
  def has_minimum_cs_info(self):
    return all([self.cs_bucket, self.cs_remote_path, self.download_path,
                self.cs_hash])

  def VerifyCloudStorageInfo(self):
    """Ensure either all or none of the needed remote information is specified.
    """
    if self.has_cs_info and not self.has_minimum_cs_info:
      raise ValueError(
            'Attempted to partially initialize cloud storage data for '
            'dependency: %s, platform: %s, download_path: %s, '
            'cs_remote_path: %s, cs_bucket: %s, cs_hash: %s, version_in_cs: %s,'
            ' path_within_archive: %s' % (self.dependency, self.platform,
                self.download_path, self.cs_remote_path, self.cs_bucket,
                self.cs_hash, self._version_in_cs, self._path_within_archive))
    if bool(self.unzip_location) != bool(self.path_within_archive):
      raise ValueError(
          'DependencyInfo must have both or neither unzip_location and '
          'path_within_archive. Found: unzip_location: %s, unzippped_path: %s'
          % (self.unzip_location, self.path_within_archive))

