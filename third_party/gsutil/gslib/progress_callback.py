# -*- coding: utf-8 -*-
# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Helper functions for progress callbacks."""

import logging
import sys

from gslib.util import MakeHumanReadable
from gslib.util import UTF8

# Default upper and lower bounds for progress callback frequency.
_START_BYTES_PER_CALLBACK = 1024*64
_MAX_BYTES_PER_CALLBACK = 1024*1024*100

# Max width of URL to display in progress indicator. Wide enough to allow
# 15 chars for x/y display on an 80 char wide terminal.
MAX_PROGRESS_INDICATOR_COLUMNS = 65


class ProgressCallbackWithBackoff(object):
  """Makes progress callbacks with exponential backoff to a maximum value.

  This prevents excessive log message output.
  """

  def __init__(self, total_size, callback_func,
               start_bytes_per_callback=_START_BYTES_PER_CALLBACK,
               max_bytes_per_callback=_MAX_BYTES_PER_CALLBACK,
               calls_per_exponent=10):
    """Initializes the callback with backoff.

    Args:
      total_size: Total bytes to process. If this is None, size is not known
          at the outset.
      callback_func: Func of (int: processed_so_far, int: total_bytes)
          used to make callbacks.
      start_bytes_per_callback: Lower bound of bytes per callback.
      max_bytes_per_callback: Upper bound of bytes per callback.
      calls_per_exponent: Number of calls to make before reducing rate.
    """
    self._bytes_per_callback = start_bytes_per_callback
    self._callback_func = callback_func
    self._calls_per_exponent = calls_per_exponent
    self._max_bytes_per_callback = max_bytes_per_callback
    self._total_size = total_size

    self._bytes_processed_since_callback = 0
    self._callbacks_made = 0
    self._total_bytes_processed = 0

  def Progress(self, bytes_processed):
    """Tracks byte processing progress, making a callback if necessary."""
    self._bytes_processed_since_callback += bytes_processed
    if (self._bytes_processed_since_callback > self._bytes_per_callback or
        (self._total_bytes_processed + self._bytes_processed_since_callback >=
         self._total_size and self._total_size is not None)):
      self._total_bytes_processed += self._bytes_processed_since_callback
      # TODO: We check if >= total_size and truncate because JSON uploads count
      # headers+metadata during their send progress. If the size is unknown,
      # we can't do this and the progress message will make it appear that we
      # send more than the original stream.
      if self._total_size is not None:
        bytes_sent = min(self._total_bytes_processed, self._total_size)
      else:
        bytes_sent = self._total_bytes_processed
      self._callback_func(bytes_sent, self._total_size)
      self._bytes_processed_since_callback = 0
      self._callbacks_made += 1

      if self._callbacks_made > self._calls_per_exponent:
        self._bytes_per_callback = min(self._bytes_per_callback * 2,
                                       self._max_bytes_per_callback)
        self._callbacks_made = 0


def ConstructAnnounceText(operation_name, url_string):
  """Constructs announce text for ongoing operations on url_to_display.

  This truncates the text to a maximum of MAX_PROGRESS_INDICATOR_COLUMNS.
  Thus, concurrent output (gsutil -m) leaves progress counters in a readable
  (fixed) position.

  Args:
    operation_name: String describing the operation, i.e.
        'Uploading' or 'Hashing'.
    url_string: String describing the file/object being processed.

  Returns:
    Formatted announce text for outputting operation progress.
  """
  # Operation name occupies 11 characters (enough for 'Downloading'), plus a
  # space. The rest is used for url_to_display. If a longer operation name is
  # used, it will be truncated. We can revisit this size if we need to support
  # a longer operation, but want to make sure the terminal output is meaningful.
  justified_op_string = operation_name[:11].ljust(12)
  start_len = len(justified_op_string)
  end_len = len(': ')
  if (start_len + len(url_string) + end_len >
      MAX_PROGRESS_INDICATOR_COLUMNS):
    ellipsis_len = len('...')
    url_string = '...%s' % url_string[
        -(MAX_PROGRESS_INDICATOR_COLUMNS - start_len - end_len - ellipsis_len):]
  base_announce_text = '%s%s:' % (justified_op_string, url_string)
  format_str = '{0:%ds}' % MAX_PROGRESS_INDICATOR_COLUMNS
  return format_str.format(base_announce_text.encode(UTF8))


class FileProgressCallbackHandler(object):
  """Outputs progress info for large operations like file copy or hash."""

  def __init__(self, announce_text, logger, start_byte=0,
               override_total_size=None):
    """Initializes the callback handler.

    Args:
      announce_text: String describing the operation.
      logger: For outputting log messages.
      start_byte: The beginning of the file component, if one is being used.
      override_total_size: The size of the file component, if one is being used.
    """
    self._announce_text = announce_text
    self._logger = logger
    self._start_byte = start_byte
    self._override_total_size = override_total_size
    # Ensures final newline is written once even if we get multiple callbacks.
    self._last_byte_written = False

  # Function signature is in boto callback format, which cannot be changed.
  def call(self,  # pylint: disable=invalid-name
           last_byte_processed,
           total_size):
    """Prints an overwriting line to stderr describing the operation progress.

    Args:
      last_byte_processed: The last byte processed in the file. For file
                           components, this number should be in the range
                           [start_byte:start_byte + override_total_size].
      total_size: Total size of the ongoing operation.
    """
    if not self._logger.isEnabledFor(logging.INFO) or self._last_byte_written:
      return

    if self._override_total_size:
      total_size = self._override_total_size

    if total_size:
      total_size_string = '/%s' % MakeHumanReadable(total_size)
    else:
      total_size_string = ''
    # Use sys.stderr.write instead of self.logger.info so progress messages
    # output on a single continuously overwriting line.
    # TODO: Make this work with logging.Logger.
    sys.stderr.write('%s%s%s    \r' % (
        self._announce_text,
        MakeHumanReadable(last_byte_processed - self._start_byte),
        total_size_string))
    if total_size and last_byte_processed - self._start_byte == total_size:
      self._last_byte_written = True
      sys.stderr.write('\n')
