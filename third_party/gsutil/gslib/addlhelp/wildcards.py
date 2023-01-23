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
"""Additional help about wildcards."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from gslib.help_provider import HelpProvider

_DETAILED_HELP_TEXT = ("""
<B>DESCRIPTION</B>
  gsutil supports URI wildcards for files, buckets, and objects. For
  example, the command:

    gsutil cp gs://bucket/data/abc* .

  copies all objects that start with gs://bucket/data/abc followed by any
  number of characters within that subdirectory.

<B>WILDCARD CHARACTERS</B>
  gsutil uses the following wildcards:

  *
    Match any number of characters within the current directory level. For
    example, ``gs://my-bucket/abc/d*`` matches the object ``abc/def.txt``
    but not the object ``abc/def/g.txt``.

  **
    Match any number of characters across directory boundaries. When used
    as part of a local file path, the ``**`` wildcard should always be
    immediately preceded by a directory delimiter. For example,
    ``my-directory/**.txt`` is valid, but ``my-directory/abc**`` is not.
    
    NOTE: Some command shells expand wildcard matches prior to running the
    gsutil command; however, most shells do not support recursive
    wildcards (``**``). You can skip command shell wildcard expansion and
    instead use gsutil's wildcarding support in such shells by
    single-quoting (on Linux) or double-quoting (on Windows) the argument.
    For example: ``gsutil cp 'data/**' gs://bucket``

  ?
    Match a single character. For example ``gs://bucket/??.txt``
    only matches objects with two characters followed by .txt.

  [chars]
    Match any of the specified characters. For example
    ``gs://bucket/[aeiou].txt`` matches objects that contain a single
    vowel character followed by ``.txt``.

  [char range]
    Match any of the range of characters. For example
    ``gs://bucket/[a-m].txt`` matches objects that contain letters
    a, b, c, ... or m, and end with ``.txt``.

  You can combine wildcards to provide more powerful matches, for example:

    gs://*/[a-m]??.j*g

  Note that unless your command includes a flag to return `noncurrent
  object versions
  <https://cloud.google.com/storage/docs/object-versioning>`_ in the
  results, these wildcards only match live object versions.

  gsutil supports the same wildcards for both object and file names. Thus,
  for example:

    gsutil cp data/abc* gs://bucket
    
  matches all files that start with ``abc`` in the ``data`` directory of
  the local file system.

<B>POTENTIALLY SURPRISING BEHAVIOR WHEN USING WILDCARDS</B>
  There are a couple of ways that using wildcards can result in surprising
  behavior:

  1. When using wildcards in bucket names, matches are limited to buckets in
     the `project <https://cloud.google.com/storage/docs/projects>`_
     specified in the ``-p`` flag. Some commands, such as ``gsutil rm``, do
     not support the ``-p`` flag. If the ``-p`` flag is not or cannot be used
     in a command, matches are limited to buckets in the default project.

  2. Shells (like bash and zsh) can attempt to expand wildcards before passing
     the arguments to gsutil. If the wildcard was supposed to refer to a cloud
     object, this can result in surprising "Not found" errors (e.g., if the
     shell tries to expand the wildcard ``gs://my-bucket/*`` on the local
     machine, matching no local files, and failing the command).

     Note that some shells include additional characters in their wildcard
     character sets. For example, if you use zsh with the extendedglob option
     enabled it treats ``#`` as a special character, which conflicts with
     that character's use in referencing versioned objects (see
     `Restore noncurrent object versions
     <https://cloud.google.com/storage/docs/using-versioned-objects#restore>`_
     for an example).

     To avoid these problems, surround the wildcarded expression with single
     quotes (on Linux) or double quotes (on Windows).

  3. Attempting to specify a filename that contains wildcard characters won't
     work, because gsutil tries to expand the wildcard characters rather
     than using them as literal characters. For example, running the command:

       gsutil cp './file[1]' gs://my-bucket

     causes gsutil to try to match the ``[1]`` part as a wildcard.

     There's an open issue to support a "raw" mode for gsutil to provide a
     way to work with file names that contain wildcard characters, but until /
     unless that support is implemented there's no really good way to use
     gsutil with such file names. You could use a wildcard to name such files,
     for example replacing the above command with:

       gsutil cp './file*1*' gs://my-bucket

     but that approach may be difficult to use in general.


<B>DIFFERENT BEHAVIOR FOR "DOT" FILES IN LOCAL FILE SYSTEM</B>
  Per standard Unix behavior, the wildcard ``*`` only matches files that
  don't start with a ``.`` character (to avoid confusion with the ``.`` and
  ``..`` directories present in all Unix directories). gsutil provides this
  same behavior when using wildcards over a file system URI, but does not
  provide this behavior over cloud URIs. For example, the following command
  copies all objects from gs://bucket1 to gs://bucket2:

    gsutil cp gs://bucket1/* gs://bucket2

  but the following command copies only files that don't start with a ``.``
  from the directory ``dir`` to gs://bucket1:

    gsutil cp dir/* gs://bucket1


<B>EFFICIENCY CONSIDERATION: USING WILDCARDS OVER MANY OBJECTS</B>
  It is more efficient, faster, and less network traffic-intensive
  to use wildcards that have a non-wildcard object-name prefix, like:

    gs://bucket/abc*.txt

  than it is to use wildcards as the first part of the object name, like:

    gs://bucket/*abc.txt

  This is because the request for ``gs://bucket/abc*.txt`` asks the server to
  send back the subset of results whose object name start with ``abc`` at the
  bucket root, and then gsutil filters the result list for objects whose name
  ends with ``.txt``.  In contrast, ``gs://bucket/*abc.txt`` asks the server for
  the complete list of objects in the bucket root, and then filters for those
  objects whose name ends with ``abc.txt``. This efficiency consideration
  becomes increasingly noticeable when you use buckets containing thousands or
  more objects. It is sometimes possible to set up the names of your objects to
  fit with expected wildcard matching patterns, to take advantage of the
  efficiency of doing server-side prefix requests. See, for example
  "gsutil help prod" for a concrete use case example.


<B>EFFICIENCY CONSIDERATION: USING MID-PATH WILDCARDS</B>
  Suppose you have a bucket with these objects:

    gs://bucket/obj1
    gs://bucket/obj2
    gs://bucket/obj3
    gs://bucket/obj4
    gs://bucket/dir1/obj5
    gs://bucket/dir2/obj6

  If you run the command:

    gsutil ls gs://bucket/*/obj5

  gsutil performs a /-delimited top-level bucket listing and then one bucket
  listing for each subdirectory, for a total of 3 bucket listings:

    GET /bucket/?delimiter=/
    GET /bucket/?prefix=dir1/obj5&delimiter=/
    GET /bucket/?prefix=dir2/obj5&delimiter=/

  The more bucket listings your wildcard requires, the slower and more expensive
  it becomes. The number of bucket listings required grows as:

  - the number of wildcard components (e.g., "gs://bucket/a??b/c*/*/d"
    has 3 wildcard components);
  - the number of subdirectories that match each component; and
  - the number of results (pagination is implemented using one GET
    request per 1000 results, specifying markers for each).

  If you want to use a mid-path wildcard, you might try instead using a
  recursive wildcard, for example:

    gsutil ls gs://bucket/**/obj5

  This matches more objects than ``gs://bucket/*/obj5`` (since it spans
  directories), but is implemented using a delimiter-less bucket listing
  request (which means fewer bucket requests, though it lists the entire
  bucket and filters locally, so that could require a non-trivial amount
  of network traffic).
""")


class CommandOptions(HelpProvider):
  """Additional help about wildcards."""

  # Help specification. See help_provider.py for documentation.
  help_spec = HelpProvider.HelpSpec(
      help_name='wildcards',
      help_name_aliases=['wildcard', '*', '**'],
      help_type='additional_help',
      help_one_line_summary='Wildcard Names',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
