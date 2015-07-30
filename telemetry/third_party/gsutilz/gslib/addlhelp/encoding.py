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
"""Additional help about CRC32C and installing crcmod."""

from __future__ import absolute_import

from gslib.help_provider import HelpProvider

_DETAILED_HELP_TEXT = ("""
<B>OVERVIEW</B>
  To minimize the chance for `filename encoding interoperability problems
  <https://en.wikipedia.org/wiki/Filename#Encoding_indication_interoperability>`_ 
  gsutil requires use of the `UTF-8 <https://en.wikipedia.org/wiki/UTF-8>`_
  character encoding when uploading and downloading files. Because UTF-8 is in
  widespread (and growing) use, for most users nothing needs to be done to use
  UTF-8. Users with files stored in other encodings (such as
  `Latin 1 <https://en.wikipedia.org/wiki/ISO/IEC_8859-1>`_) must convert those
  filenames to UTF-8 before attempting to upload the files. 

  The most common place where users who have filenames that use some other
  encoding encounter a gsutil error is while uploading files using the recursive
  (-R) option on the gsutil cp , mv, or rsync commands. When this happens you'll
  get an error like this:

      CommandException: Invalid Unicode path encountered
      ('dir1/dir2/file_name_with_\\xf6n_bad_chars').
      gsutil cannot proceed with such files present.
      Please remove or rename this file and try again.

  Note that the invalid Unicode characters have been hex-encoded in this error
  message because otherwise trying to print them would result in another
  error.

  If you encounter such an error you can either remove the problematic file(s)
  or try to rename them and re-run the command. If you have a modest number of
  such files the simplest thing to do is to think of a different name for the
  file and manually rename the file (using local filesystem tools). If you have
  too many files for that to be practical you can use a tool to convert the old
  character encoding to UTF-8. One such tool is `native2ascii
  <http://docs.oracle.com/javase/7/docs/technotes/tools/solaris/native2ascii.html>`_.

  Note also that there's no restriction on the character encoding used in file
  content - it can be UTF-8, a different encoding, or non-character
  data (like audio or video content). The gsutil UTF-8 character encoding
  requirement applies only to filenames.


<B>CROSS-PLATFORM ENCODING PROBLEMS OF WHICH TO BE AWARE</B>
  Using UTF-8 for all object names and filenames will ensure that gsutil doesn't
  encounter character encoding errors while operating on the files.
  Unfortunately, it's still possible that files uploaded / downloaded this way
  can have interoperability problems, for a number of reasons unrelated to
  gsutil. For example:

    - Windows filenames are case-insensitive, while GCS, Linux and MacOS are
      not. Thus, for example, if you have two filenames on Linux differing only
      in case and upload both to GCS and then subsequently download them to
      Windows, you will end up with just one file whose contents came from the
      last of these files to be written to the filesystem. Moreover, case
      translation is handled by tables that change across OS versions.
    - Mac OS performs character encoding decomposition based on tables stored in
      the OS, and the tables change between Unicode versions. Thus the encoding
      used by an external library may not match that performed by the the OS.
    - Windows console support for Unicode is difficult to use correctly.

  For a more thorough list of such issues see `this presentation
  <http://www.i18nguy.com/unicode/filename-issues-iuc33.pdf>`_

  These problems mostly arise when sharing data across platforms (e.g.,
  uploading data from a Windows machine to GCS, and then downloading from GCS
  to a machine running MacOS). Unfortunately these problems are a consequence
  of the lack of a filename encoding standard, and users need to be aware of the
  kinds of problems that can arise when copying filenames across platforms.

  There is one precaution users can exercise to prevent some of these problems:
  When using the Windows console specify wildcards or folders (using the -R
  option) rather than explicitly named individual files.
""")


class CommandOptions(HelpProvider):
  """Additional help about filename encoding and interoperability problems."""

  # Help specification. See help_provider.py for documentation.
  help_spec = HelpProvider.HelpSpec(
      help_name='encoding',
      help_name_aliases=['encodings', 'utf8', 'utf-8', 'latin1', 'unicode',
                         'interoperability'],
      help_type='additional_help',
      help_one_line_summary='Filename encoding and interoperability problems',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
