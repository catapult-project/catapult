# -*- coding: utf-8 -*-
# Copyright 2012 Google Inc. All Rights Reserved.
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
"""Additional help about subdirectory handling in gsutil."""

from __future__ import absolute_import

from gslib.help_provider import HelpProvider

_DETAILED_HELP_TEXT = ("""
<B>OVERVIEW</B>
  This section provides details about how subdirectories work in gsutil.
  Most users probably don't need to know these details, and can simply use
  the commands (like cp -r) that work with subdirectories. We provide this
  additional documentation to help users understand how gsutil handles
  subdirectories differently than most GUI / web-based tools (e.g., why
  those other tools create "dir_$folder$" objects), and also to explain cost and
  performance implications of the gsutil approach, for those interested in such
  details.

  gsutil provides the illusion of a hierarchical file tree atop the "flat"
  name space supported by the Google Cloud Storage service. To the service,
  the object gs://your-bucket/abc/def/ghi.txt is just an object that happens to
  have "/" characters in its name. There are no "abc" or "abc/def" directories;
  just a single object with the given name. This diagram:
  https://cloud.google.com/storage/images/gsutil-subdirectories-thumb.png
  illustrates how gsutil provides a hierarchical view of objects in a bucket.

  gsutil achieves the hierarchical file tree illusion by applying a variety of
  rules, to try to make naming work the way users would expect. For example, in
  order to determine whether to treat a destination URL as an object name or the
  root of a directory under which objects should be copied gsutil uses these
  rules:

  1. If the destination object ends with a "/" gsutil treats it as a directory.
     For example, if you run the command:

       gsutil cp your-file gs://your-bucket/abc/

     gsutil will create the object gs://your-bucket/abc/your-file.

  2. If the destination object is XYZ and an object exists called XYZ_$folder$
     gsutil treats XYZ as a directory. For example, if you run the command:

       gsutil cp your-file gs://your-bucket/abc

     and there exists an object called abc_$folder$, gsutil will create the
     object gs://your-bucket/abc/your-file.

  3. If you attempt to copy multiple source files to a destination URL, gsutil
     treats the destination URL as a directory. For example, if you run
     the command:

       gsutil cp -r your-dir gs://your-bucket/abc

     gsutil will create objects like gs://your-bucket/abc/your-dir/file1, etc.
     (assuming file1 is a file under the source directory your-dir).

  4. If none of the above rules applies, gsutil performs a bucket listing to
     determine if the target of the operation is a prefix match to the
     specified string. For example, if you run the command:

       gsutil cp your-file gs://your-bucket/abc

     gsutil will make a bucket listing request for the named bucket, using
     delimiter="/" and prefix="abc". It will then examine the bucket listing
     results and determine whether there are objects in the bucket whose path
     starts with gs://your-bucket/abc/, to determine whether to treat the target
     as an object name or a directory name. In turn this impacts the name of the
     object you create: If the above check indicates there is an "abc" directory
     you will end up with the object gs://your-bucket/abc/your-file; otherwise
     you will end up with the object gs://your-bucket/abc. (See
     "HOW NAMES ARE CONSTRUCTED" under "gsutil help cp" for more details.)

  This rule-based approach stands in contrast to the way many tools work, which
  create objects to mark the existence of folders (such as "dir_$folder$").
  gsutil understands several conventions used by such tools but does not
  require such marker objects to implement naming behavior consistent with
  UNIX commands.

  A downside of the gsutil approach is it requires an extra bucket listing
  before performing the needed cp or mv command. However those listings are
  relatively inexpensive, because they use delimiter and prefix parameters to
  limit result data. Moreover, gsutil makes only one bucket listing request
  per cp/mv command, and thus amortizes the bucket listing cost across all
  transferred objects (e.g., when performing a recursive copy of a directory
  to the cloud).
""")


class CommandOptions(HelpProvider):
  """Additional help about subdirectory handling in gsutil."""

  # Help specification. See help_provider.py for documentation.
  help_spec = HelpProvider.HelpSpec(
      help_name='subdirs',
      help_name_aliases=[
          'dirs', 'directory', 'directories', 'folder', 'folders', 'hierarchy',
          'subdir', 'subdirectory', 'subdirectories'],
      help_type='additional_help',
      help_one_line_summary='How Subdirectories Work',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
