# -*- coding: utf-8 -*-
# Copyright 2011 Google Inc. All Rights Reserved.
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
"""Implementation of mb command for creating cloud storage buckets."""

from __future__ import absolute_import

import textwrap

from gslib.cloud_api import BadRequestException
from gslib.command import Command
from gslib.command_argument import CommandArgument
from gslib.cs_api_map import ApiSelector
from gslib.exception import CommandException
from gslib.storage_url import StorageUrlFromString
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.util import NO_MAX


_SYNOPSIS = """
  gsutil mb [-c class] [-l location] [-p proj_id] uri...
"""

_DETAILED_HELP_TEXT = ("""
<B>SYNOPSIS</B>
""" + _SYNOPSIS + """


<B>DESCRIPTION</B>
  The mb command creates a new bucket. Google Cloud Storage has a single
  namespace, so you will not be allowed to create a bucket with a name already
  in use by another user. You can, however, carve out parts of the bucket name
  space corresponding to your company's domain name (see "gsutil help naming").

  If you don't specify a project ID using the -p option, the bucket
  will be created using the default project ID specified in your gsutil
  configuration file (see "gsutil help config"). For more details about
  projects see "gsutil help projects".

  The -c and -l options specify the storage class and location, respectively,
  for the bucket. Once a bucket is created in a given location and with a
  given storage class, it cannot be moved to a different location, and the
  storage class cannot be changed. Instead, you would need to create a new
  bucket and move the data over and then delete the original bucket.


<B>BUCKET STORAGE CLASSES</B>
  If you don't specify a -c option, the bucket will be created with the default
  (Standard) storage class.

  If you specify -c DURABLE_REDUCED_AVAILABILITY (or -c DRA), it causes the data
  stored in the bucket to use Durable Reduced Availability storage. Buckets
  created with this storage class have lower availability than Standard storage
  class buckets, but durability equal to that of buckets created with Standard
  storage class. This option allows users to reduce costs for data for which
  lower availability is acceptable. Durable Reduced Availability storage would
  not be appropriate for "hot" objects (i.e., objects being accessed frequently)
  or for interactive workloads; however, it might be appropriate for other types
  of applications. See the online documentation for
  `pricing <https://cloud.google.com/storage/pricing>`_
  and `SLA <https://cloud.google.com/storage/sla>`_
  details.


  If you specify -c NEARLINE (or -c NL), it causes the data
  stored in the bucket to use Nearline storage. Buckets created with this
  storage class have higher latency and lower throughput than Standard storage
  class buckets. The availability and durability remains equal to that of
  buckets created with the Standard storage class. This option is best for
  objects which are accessed rarely and for which slower performance is
  acceptable. See the online documentation for
  `pricing <https://cloud.google.com/storage/pricing>`_ and
  `SLA <https://cloud.google.com/storage/sla>`_ details.


<B>BUCKET LOCATIONS</B>
  If you don't specify a -l option, the bucket will be created in the default
  location (US). Otherwise, you can specify one of the available continental
  locations:

  - ASIA (Asia)
  - EU (European Union)
  - US (United States)

  Example:
    gsutil mb -l ASIA gs://some-bucket

  If you specify the Durable Reduced Availability storage class (-c DRA), you
  can specify one of the continental locations above or one of the regional
  locations below: [1]_

  - ASIA-EAST1 (Eastern Asia-Pacific)
  - US-EAST1 (Eastern United States)
  - US-EAST2 (Eastern United States)
  - US-EAST3 (Eastern United States)
  - US-CENTRAL1 (Central United States)
  - US-CENTRAL2 (Central United States)
  - US-WEST1 (Western United States)

  Example:
    gsutil mb -c DRA -l US-CENTRAL1 gs://some-bucket

  .. [1] These locations are for `Regional Buckets <https://developers.google.com/storage/docs/regional-buckets>`_.
     Regional Buckets is an experimental feature and data stored in these
     locations is not subject to the usual SLA. See the documentation for
     additional information.


<B>OPTIONS</B>
  -c class          Can be DRA (or DURABLE_REDUCED_AVAILABILITY), NL (or
                    NEARLINE), or S (or STANDARD). Default is STANDARD.

  -l location       Can be any continental location as described above, or
                    for DRA storage class, any regional or continental
                    location. Default is US. Locations are case insensitive.

  -p proj_id        Specifies the project ID under which to create the bucket.
""")


class MbCommand(Command):
  """Implementation of gsutil mb command."""

  # Command specification. See base class for documentation.
  command_spec = Command.CreateCommandSpec(
      'mb',
      command_name_aliases=['makebucket', 'createbucket', 'md', 'mkdir'],
      usage_synopsis=_SYNOPSIS,
      min_args=1,
      max_args=NO_MAX,
      supported_sub_args='c:l:p:',
      file_url_ok=False,
      provider_url_ok=False,
      urls_start_arg=0,
      gs_api_support=[ApiSelector.XML, ApiSelector.JSON],
      gs_default_api=ApiSelector.JSON,
      argparse_arguments=[
          CommandArgument.MakeZeroOrMoreCloudBucketURLsArgument()
      ]
  )
  # Help specification. See help_provider.py for documentation.
  help_spec = Command.HelpSpec(
      help_name='mb',
      help_name_aliases=[
          'createbucket', 'makebucket', 'md', 'mkdir', 'location', 'dra',
          'dras', 'reduced_availability', 'durable_reduced_availability', 'rr',
          'reduced_redundancy', 'standard', 'storage class', 'nearline', 'nl'],
      help_type='command_help',
      help_one_line_summary='Make buckets',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )

  def RunCommand(self):
    """Command entry point for the mb command."""
    location = None
    storage_class = None
    if self.sub_opts:
      for o, a in self.sub_opts:
        if o == '-l':
          location = a
        elif o == '-p':
          self.project_id = a
        elif o == '-c':
          storage_class = self._Normalize_Storage_Class(a)

    bucket_metadata = apitools_messages.Bucket(location=location,
                                               storageClass=storage_class)

    for bucket_uri_str in self.args:
      bucket_uri = StorageUrlFromString(bucket_uri_str)
      if not bucket_uri.IsBucket():
        raise CommandException('The mb command requires a URI that specifies a '
                               'bucket.\n"%s" is not valid.' % bucket_uri)

      self.logger.info('Creating %s...', bucket_uri)
      # Pass storage_class param only if this is a GCS bucket. (In S3 the
      # storage class is specified on the key object.)
      try:
        self.gsutil_api.CreateBucket(
            bucket_uri.bucket_name, project_id=self.project_id,
            metadata=bucket_metadata, provider=bucket_uri.scheme)
      except BadRequestException as e:
        if (e.status == 400 and e.reason == 'DotfulBucketNameNotUnderTld' and
            bucket_uri.scheme == 'gs'):
          bucket_name = bucket_uri.bucket_name
          final_comp = bucket_name[bucket_name.rfind('.')+1:]
          raise CommandException('\n'.join(textwrap.wrap(
              'Buckets with "." in the name must be valid DNS names. The bucket'
              ' you are attempting to create (%s) is not a valid DNS name,'
              ' because the final component (%s) is not currently a valid part'
              ' of the top-level DNS tree.' % (bucket_name, final_comp))))
        else:
          raise

    return 0

  def _Normalize_Storage_Class(self, sc):
    sc = sc.upper()
    if sc in ('DRA', 'DURABLE_REDUCED_AVAILABILITY'):
      return 'DURABLE_REDUCED_AVAILABILITY'
    if sc in ('S', 'STD', 'STANDARD'):
      return 'STANDARD'
    if sc in ('NL', 'NEARLINE'):
      return 'NEARLINE'
    return sc
