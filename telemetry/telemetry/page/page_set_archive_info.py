# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import os
import re
import shutil
import tempfile

from telemetry.util import cloud_storage


class PageSetArchiveInfo(object):
  def __init__(self, file_path, data, ignore_archive=False):
    self._file_path = file_path
    self._base_dir = os.path.dirname(file_path)

    # Ensure directory exists.
    if not os.path.exists(self._base_dir):
      os.makedirs(self._base_dir)

    # Download all .wpr files.
    if not ignore_archive:
      # TODO(tbarzic): Remove this once http://crbug.com/351143 is diagnosed.
      log_cloud_storage_exception = True
      for archive_path in data['archives']:
        archive_path = self._WprFileNameToPath(archive_path)
        try:
          cloud_storage.GetIfChanged(archive_path)
        except (cloud_storage.CredentialsError,
                cloud_storage.PermissionError) as e:
          if os.path.exists(archive_path):
            # If the archive exists, assume the user recorded their own and
            # simply warn.
            logging.warning('Need credentials to update WPR archive: %s',
                            archive_path)
          elif log_cloud_storage_exception:
            # Log access errors only once, as they should stay the same in other
            # iterations.
            log_cloud_storage_exception = False
            logging.warning('Error getting WPR archive %s: %s ' %
                                (archive_path, str(e)))
            logging.info(
                'HOME: "%s"; USER: "%s"' %
                (os.environ.get('HOME', ''), os.environ.get('USER', '')))

    # Map from the relative path (as it appears in the metadata file) of the
    # .wpr file to a list of page names it supports.
    self._wpr_file_to_page_names = data['archives']

    # Map from the page name to a relative path (as it appears in the metadata
    # file) of the .wpr file.
    self._page_name_to_wpr_file = dict()
    # Find out the wpr file names for each page.
    for wpr_file in data['archives']:
      page_names = data['archives'][wpr_file]
      for page_name in page_names:
        self._page_name_to_wpr_file[page_name] = wpr_file
    self.temp_target_wpr_file_path = None

  @classmethod
  def FromFile(cls, file_path, ignore_archive=False):
    if os.path.exists(file_path):
      with open(file_path, 'r') as f:
        data = json.load(f)
        return cls(file_path, data, ignore_archive=ignore_archive)
    # TODO(tbarzic): Remove this once http://crbug.com/351143 is diagnosed.
    logging.warning('Page set archives not found: %s' % file_path)
    return cls(file_path, {'archives': {}}, ignore_archive=ignore_archive)

  def WprFilePathForPage(self, page):
    if self.temp_target_wpr_file_path:
      return self.temp_target_wpr_file_path
    wpr_file = self._page_name_to_wpr_file.get(page.display_name, None)
    if wpr_file is None:
      # Some old page sets always use the URL to identify a page rather than the
      # display_name, so try to look for that.
      wpr_file = self._page_name_to_wpr_file.get(page.url, None)
    if wpr_file:
      return self._WprFileNameToPath(wpr_file)
    return None

  def AddNewTemporaryRecording(self, temp_wpr_file_path=None):
    if temp_wpr_file_path is None:
      temp_wpr_file_handle, temp_wpr_file_path = tempfile.mkstemp()
      os.close(temp_wpr_file_handle)
    self.temp_target_wpr_file_path = temp_wpr_file_path

  def AddRecordedPages(self, pages):
    if not pages:
      os.remove(self.temp_target_wpr_file_path)
      return

    (target_wpr_file, target_wpr_file_path) = self._NextWprFileName()
    for page in pages:
      self._SetWprFileForPage(page.display_name, target_wpr_file)
    shutil.move(self.temp_target_wpr_file_path, target_wpr_file_path)

    # Update the hash file.
    with open(target_wpr_file_path + '.sha1', 'wb') as f:
      f.write(cloud_storage.CalculateHash(target_wpr_file_path))
      f.flush()

    self._WriteToFile()
    self._DeleteAbandonedWprFiles()

  def _DeleteAbandonedWprFiles(self):
    # Update the metadata so that the abandoned wpr files don't have empty page
    # name arrays.
    abandoned_wpr_files = self._AbandonedWprFiles()
    for wpr_file in abandoned_wpr_files:
      del self._wpr_file_to_page_names[wpr_file]
      # Don't fail if we're unable to delete some of the files.
      wpr_file_path = self._WprFileNameToPath(wpr_file)
      try:
        os.remove(wpr_file_path)
      except Exception:
        logging.warning('Failed to delete file: %s' % wpr_file_path)

  def _AbandonedWprFiles(self):
    abandoned_wpr_files = []
    for wpr_file, page_names in self._wpr_file_to_page_names.iteritems():
      if not page_names:
        abandoned_wpr_files.append(wpr_file)
    return abandoned_wpr_files

  def _WriteToFile(self):
    """Writes the metadata into the file passed as constructor parameter."""
    metadata = dict()
    metadata['description'] = (
        'Describes the Web Page Replay archives for a page set. Don\'t edit by '
        'hand! Use record_wpr for updating.')
    metadata['archives'] = self._wpr_file_to_page_names.copy()
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
    for wpr_file in self._wpr_file_to_page_names:
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
      # page set file.
      base = os.path.splitext(os.path.basename(self._file_path))[0]
    new_filename = '%s_%03d.wpr' % (base, highest_number + 1)
    return new_filename, self._WprFileNameToPath(new_filename)

  def _SetWprFileForPage(self, page_name, wpr_file):
    """For modifying the metadata when we're going to record a new archive."""
    old_wpr_file = self._page_name_to_wpr_file.get(page_name, None)
    if old_wpr_file:
      self._wpr_file_to_page_names[old_wpr_file].remove(page_name)
    self._page_name_to_wpr_file[page_name] = wpr_file
    if wpr_file not in self._wpr_file_to_page_names:
      self._wpr_file_to_page_names[wpr_file] = []
    self._wpr_file_to_page_names[wpr_file].append(page_name)
