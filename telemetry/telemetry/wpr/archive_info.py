# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import re
import shutil
import tempfile

from telemetry import page as page_module
from telemetry.util import cloud_storage


def AssertValidCloudStorageBucket(bucket):
  is_valid = bucket in (None,
                        cloud_storage.PUBLIC_BUCKET,
                        cloud_storage.PARTNER_BUCKET,
                        cloud_storage.INTERNAL_BUCKET)
  if not is_valid:
    raise ValueError("Cloud storage privacy bucket %s is invalid" % bucket)


class ArchiveError(Exception):
  pass


class WprArchiveInfo(object):
  def __init__(self, file_path, data, bucket):
    AssertValidCloudStorageBucket(bucket)
    self._file_path = file_path
    self._base_dir = os.path.dirname(file_path)
    self._data = data
    self._bucket = bucket

    # Ensure directory exists.
    if not os.path.exists(self._base_dir):
      os.makedirs(self._base_dir)

    # Map from the relative path (as it appears in the metadata file) of the
    # .wpr file to a list of user story names it supports.
    self._wpr_file_to_user_story_names = data['archives']

    # Map from the user_story name to a relative path (as it appears
    # in the metadata file) of the .wpr file.
    self._user_story_name_to_wpr_file = dict()
    # Find out the wpr file names for each user_story.
    for wpr_file in data['archives']:
      user_story_names = data['archives'][wpr_file]
      for user_story_name in user_story_names:
        self._user_story_name_to_wpr_file[user_story_name] = wpr_file
    self.temp_target_wpr_file_path = None

  @classmethod
  def FromFile(cls, file_path, bucket):
    if os.path.exists(file_path):
      with open(file_path, 'r') as f:
        data = json.load(f)
        return cls(file_path, data, bucket)
    return cls(file_path, {'archives': {}}, bucket)

  def DownloadArchivesIfNeeded(self):
    """Downloads archives iff the Archive has a bucket parameter and the user
    has permission to access the bucket.

    Raises cloud storage Permissions or Credentials error when there is no
    local copy of the archive and the user doesn't have permission to access
    the archive's bucket.

    Warns when a bucket is not specified or when the user doesn't have
    permission to access the archive's bucket but a local copy of the archive
    exists.
    """
    # Download all .wpr files.
    if not self._bucket:
      logging.warning('User story set in %s has no bucket specified, and '
                      'cannot be downloaded from cloud_storage.', )
      return
    assert 'archives' in self._data, 'Invalid data format in %s. \'archives\'' \
                                     ' field is needed' % self._file_path
    for archive_path in self._data['archives']:
      archive_path = self._WprFileNameToPath(archive_path)
      try:
        cloud_storage.GetIfChanged(archive_path, self._bucket)
      except (cloud_storage.CredentialsError, cloud_storage.PermissionError):
        if os.path.exists(archive_path):
          # If the archive exists, assume the user recorded their own and
          # simply warn.
          logging.warning('Need credentials to update WPR archive: %s',
                          archive_path)
        else:
          logging.error("You either aren't authenticated or don't have "
                        "permission to use the archives for this page set."
                        "\nYou may need to run gsutil config."
                        "\nYou can find instructions for gsutil config at: "
                        "http://www.chromium.org/developers/telemetry/"
                        "upload_to_cloud_storage")
          raise

  def WprFilePathForUserStory(self, story):
    if self.temp_target_wpr_file_path:
      return self.temp_target_wpr_file_path
    wpr_file = self._user_story_name_to_wpr_file.get(story.display_name, None)
    if wpr_file is None and isinstance(story, page_module.Page):
      # Some old pages always use the URL to identify a page rather than the
      # display_name, so try to look for that.
      wpr_file = self._user_story_name_to_wpr_file.get(story.url, None)
    if wpr_file:
      return self._WprFileNameToPath(wpr_file)
    return None

  def AddNewTemporaryRecording(self, temp_wpr_file_path=None):
    if temp_wpr_file_path is None:
      temp_wpr_file_handle, temp_wpr_file_path = tempfile.mkstemp()
      os.close(temp_wpr_file_handle)
    self.temp_target_wpr_file_path = temp_wpr_file_path

  def AddRecordedUserStories(self, user_stories, upload_to_cloud_storage=False):
    if not user_stories:
      os.remove(self.temp_target_wpr_file_path)
      return

    (target_wpr_file, target_wpr_file_path) = self._NextWprFileName()
    for user_story in user_stories:
      self._SetWprFileForUserStory(user_story.display_name, target_wpr_file)
    shutil.move(self.temp_target_wpr_file_path, target_wpr_file_path)

    # Update the hash file.
    with open(target_wpr_file_path + '.sha1', 'wb') as f:
      f.write(cloud_storage.CalculateHash(target_wpr_file_path))
      f.flush()

    self._WriteToFile()
    self._DeleteAbandonedWprFiles()

    # Upload to cloud storage
    if upload_to_cloud_storage:
      if not self._bucket:
        logging.warning('UserStorySet must have bucket specified to upload '
                        'user stories to cloud storage.')
        return
      try:
        cloud_storage.Insert(self._bucket, target_wpr_file,
                             target_wpr_file_path)
      except cloud_storage.CloudStorageError, e:
        logging.warning('Failed to upload wpr file %s to cloud storage. '
                        'Error:%s' % target_wpr_file_path, e)

  def _DeleteAbandonedWprFiles(self):
    # Update the metadata so that the abandoned wpr files don't have
    # empty user story name arrays.
    abandoned_wpr_files = self._AbandonedWprFiles()
    for wpr_file in abandoned_wpr_files:
      del self._wpr_file_to_user_story_names[wpr_file]
      # Don't fail if we're unable to delete some of the files.
      wpr_file_path = self._WprFileNameToPath(wpr_file)
      try:
        os.remove(wpr_file_path)
      except Exception:
        logging.warning('Failed to delete file: %s' % wpr_file_path)

  def _AbandonedWprFiles(self):
    abandoned_wpr_files = []
    for wpr_file, user_story_names in (
        self._wpr_file_to_user_story_names.iteritems()):
      if not user_story_names:
        abandoned_wpr_files.append(wpr_file)
    return abandoned_wpr_files

  def _WriteToFile(self):
    """Writes the metadata into the file passed as constructor parameter."""
    metadata = dict()
    metadata['description'] = (
        'Describes the Web Page Replay archives for a user story set. '
        'Don\'t edit by hand! Use record_wpr for updating.')
    metadata['archives'] = self._wpr_file_to_user_story_names.copy()
    # Don't write data for abandoned archives.
    abandoned_wpr_files = self._AbandonedWprFiles()
    for wpr_file in abandoned_wpr_files:
      del metadata['archives'][wpr_file]

    with open(self._file_path, 'w') as f:
      json.dump(metadata, f, indent=4)
      f.flush()

  def _WprFileNameToPath(self, wpr_file):
    return os.path.abspath(os.path.join(self._base_dir, wpr_file))

  def _NextWprFileName(self):
    """Creates a new file name for a wpr archive file."""
    # The names are of the format "some_thing_number.wpr". Read the numbers.
    highest_number = -1
    base = None
    for wpr_file in self._wpr_file_to_user_story_names:
      match = re.match(r'(?P<BASE>.*)_(?P<NUMBER>[0-9]+)\.wpr', wpr_file)
      if not match:
        raise Exception('Illegal wpr file name ' + wpr_file)
      highest_number = max(int(match.groupdict()['NUMBER']), highest_number)
      if base and match.groupdict()['BASE'] != base:
        raise Exception('Illegal wpr file name ' + wpr_file +
                        ', doesn\'t begin with ' + base)
      base = match.groupdict()['BASE']
    if not base:
      # If we're creating a completely new info file, use the base name of the
      # user story set file.
      base = os.path.splitext(os.path.basename(self._file_path))[0]
    new_filename = '%s_%03d.wpr' % (base, highest_number + 1)
    return new_filename, self._WprFileNameToPath(new_filename)

  def _SetWprFileForUserStory(self, user_story_name, wpr_file):
    """For modifying the metadata when we're going to record a new archive."""
    old_wpr_file = self._user_story_name_to_wpr_file.get(user_story_name, None)
    if old_wpr_file:
      self._wpr_file_to_user_story_names[old_wpr_file].remove(user_story_name)
    self._user_story_name_to_wpr_file[user_story_name] = wpr_file
    if wpr_file not in self._wpr_file_to_user_story_names:
      self._wpr_file_to_user_story_names[wpr_file] = []
    self._wpr_file_to_user_story_names[wpr_file].append(user_story_name)
