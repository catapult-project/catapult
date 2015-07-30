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
"""Additional help about Google Cloud Storage projects."""

from __future__ import absolute_import

from gslib.help_provider import HelpProvider

_DETAILED_HELP_TEXT = ("""
<B>OVERVIEW</B>
  This section discusses how to work with projects in Google Cloud Storage.


<B>PROJECT MEMBERS AND PERMISSIONS</B>
  There are three groups of users associated with each project:

  - Project Owners are allowed to list, create, and delete buckets,
    and can also perform administrative tasks like adding and removing team
    members and changing billing. The project owners group is the owner
    of all buckets within a project, regardless of who may be the original
    bucket creator.

  - Project Editors are allowed to list, create, and delete buckets.

  - All Project Team Members are allowed to list buckets within a project.

  These projects make it easy to set up a bucket and start uploading objects
  with access control appropriate for a project at your company, as the three
  group memberships can be configured by your administrative staff. Control
  over projects and their associated memberships is provided by the
  `Google Developers Console <https://cloud.google.com/console#/project>`_.


<B>HOW PROJECT MEMBERSHIP IS REFLECTED IN BUCKET ACLS</B>
  When you create a bucket without specifying an ACL the bucket is given a
  "project-private" ACL, which grants the permissions described in the previous
  section. Here's an example of such an ACL:

    [
      {
        "entity": "group-00b4903a9740e42c29800f53bd5a9a62a2f96eb3f64a4313a115df3f3a776bf7",
        "entityId": "00b4903a9740e42c29800f53bd5a9a62a2f96eb3f64a4313a115df3f3a776bf7",
        "role": "OWNER"
      },
      {
        "entity": "group-00b4903a977fd817e9da167bc81306489181a110456bb635f466d71cf90a0d51",
        "entityId": "00b4903a977fd817e9da167bc81306489181a110456bb635f466d71cf90a0d51",
        "role": "OWNER"
      },
      {
        "entity": "00b4903a974898cc8fc309f2f2835308ba3d3df1b889d3fc7e33e187d52d8e71",
        "entityId": "00b4903a974898cc8fc309f2f2835308ba3d3df1b889d3fc7e33e187d52d8e71",
        "role": "READER"
      }
    ]

  The three "entityId"s are the canonical IDs for the Project Owners,
  Project Editors, and All Project Team Members groups.

  You can edit the bucket ACL if you want to (see "gsutil help acl"),
  but for many cases you'll never need to, and instead can change group
  membership via the
  `Google Developers Console <https://cloud.google.com/console#/project>`_.


<B>IDENTIFYING PROJECTS WHEN CREATING AND LISTING BUCKETS</B>
  When you create a bucket or list your buckets, you need to provide the
  project ID that you want to create or list (using the gsutil mb -p option or
  the gsutil ls -p option, respectively). The project's name shown in the
  Google Developers Console is a user-friendly name that you can choose; this is
  not the project ID required by the gsutil mb and ls commands. To find the
  project ID, go to the Cloud Storage pane in the Google Developers Console.
  The project ID is listed as "Project Number" in the Overview pane of your
  project.
""")


class CommandOptions(HelpProvider):
  """Additional help about Google Cloud Storage projects."""

  # Help specification. See help_provider.py for documentation.
  help_spec = HelpProvider.HelpSpec(
      help_name='projects',
      help_name_aliases=[
          'apis console', 'cloud console', 'console', 'dev console', 'project',
          'proj', 'project-id'],
      help_type='additional_help',
      help_one_line_summary='Working With Projects',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
