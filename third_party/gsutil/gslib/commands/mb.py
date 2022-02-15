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
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import re
import textwrap

from gslib.cloud_api import BadRequestException
from gslib.command import Command
from gslib.command_argument import CommandArgument
from gslib.cs_api_map import ApiSelector
from gslib.exception import CommandException
from gslib.exception import InvalidUrlError
from gslib.storage_url import StorageUrlFromString
from gslib.third_party.storage_apitools import storage_v1_messages as apitools_messages
from gslib.utils.constants import NO_MAX
from gslib.utils.retention_util import RetentionInSeconds
from gslib.utils.text_util import InsistAscii
from gslib.utils.text_util import InsistOnOrOff
from gslib.utils.text_util import NormalizeStorageClass

_SYNOPSIS = """
  gsutil mb [-b (on|off)] [-c <class>] [-l <location>] [-p <proj_id>]
            [--retention <time>] [--pap <setting>] gs://<bucket_name>...
"""

_DETAILED_HELP_TEXT = ("""
<B>SYNOPSIS</B>
""" + _SYNOPSIS + """


<B>DESCRIPTION</B>
  The mb command creates a new bucket. Google Cloud Storage has a single
  namespace, so you are not allowed to create a bucket with a name already
  in use by another user. You can, however, carve out parts of the bucket name
  space corresponding to your company's domain name (see "gsutil help naming").

  If you don't specify a project ID using the -p option, the bucket is created
  using the default project ID specified in your `gsutil configuration file
  <https://cloud.google.com/storage/docs/boto-gsutil>`_.

  The -c and -l options specify the storage class and location, respectively,
  for the bucket. Once a bucket is created in a given location and with a
  given storage class, it cannot be moved to a different location, and the
  storage class cannot be changed. Instead, you would need to create a new
  bucket and move the data over and then delete the original bucket.

  The --retention option specifies the retention period for the bucket. For more
  details about retention policy see "gsutil help retention".

  The -b option specifies the uniform bucket-level access setting of the bucket.
  ACLs assigned to objects are not evaluated in buckets with uniform bucket-
  level access enabled. Consequently, only IAM policies grant access to objects
  in these buckets.

  The --pap option specifies the public access prevention setting of the bucket.
  When enforced, objects in this bucket cannot be made publicly accessible.

<B>BUCKET STORAGE CLASSES</B>
  You can specify one of the `storage classes
  <https://cloud.google.com/storage/docs/storage-classes>`_ for a bucket
  with the -c option.

  Example:

    gsutil mb -c nearline gs://some-bucket

  See online documentation for
  `pricing <https://cloud.google.com/storage/pricing>`_ and
  `SLA <https://cloud.google.com/storage/sla>`_ details.

  If you don't specify a -c option, the bucket is created with the
  default storage class Standard Storage.

<B>BUCKET LOCATIONS</B>
  You can specify one of the `available locations
  <https://cloud.google.com/storage/docs/locations>`_ for a bucket
  with the -l option.

  Examples:

    gsutil mb -l asia gs://some-bucket

    gsutil mb -c standard -l us-east1 gs://some-bucket

  If you don't specify a -l option, the bucket is created in the default
  location (US).

<B>Retention Policy</B>
  You can specify retention period in one of the following formats:

  --retention <number>s
      Specifies retention period of <number> seconds for objects in this bucket.

  --retention <number>d
      Specifies retention period of <number> days for objects in this bucket.

  --retention <number>m
      Specifies retention period of <number> months for objects in this bucket.

  --retention <number>y
      Specifies retention period of <number> years for objects in this bucket.

  Examples:

    gsutil mb --retention 1y gs://some-bucket

    gsutil mb --retention 36m gs://some-bucket

  If you don't specify a --retention option, the bucket is created with no
  retention policy.

<B>UNIFORM BUCKET-LEVEL ACCESS</B>
  You can enable or disable uniform bucket-level access for a bucket
  with the -b option.

  Examples:

    gsutil mb -b off gs://bucket-with-acls

    gsutil mb -b on gs://bucket-with-no-acls

<B>OPTIONS</B>
  -b <on|off>            Specifies the uniform bucket-level access setting.
                         Default is "off"

  -c class               Specifies the default storage class.
                         Default is "Standard".

  -l location            Can be any supported location. See
                         https://cloud.google.com/storage/docs/locations
                         for a discussion of this distinction. Default is US.
                         Locations are case insensitive.

  -p proj_id             Specifies the project ID or project number to create
                         the bucket under.

  -s class               Same as -c.

  --retention time       Specifies the retention policy. Default is no retention
                         policy. This can only be set on gs:// buckets and
                         requires using the JSON API.

  --pap setting          Specifies the public access prevention setting.
                         Valid values are "enforced" or "unspecified".
                         Default is "unspecified".

""")

# Regex to disallow buckets violating charset or not [3..255] chars total.
BUCKET_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\._-]{1,253}[a-zA-Z0-9]$')
# Regex to disallow buckets with individual DNS labels longer than 63.
TOO_LONG_DNS_NAME_COMP = re.compile(r'[-_a-z0-9]{64}')

IamConfigurationValue = apitools_messages.Bucket.IamConfigurationValue
BucketPolicyOnlyValue = IamConfigurationValue.BucketPolicyOnlyValue


class MbCommand(Command):
  """Implementation of gsutil mb command."""

  # Command specification. See base class for documentation.
  command_spec = Command.CreateCommandSpec(
      'mb',
      command_name_aliases=['makebucket', 'createbucket', 'md', 'mkdir'],
      usage_synopsis=_SYNOPSIS,
      min_args=1,
      max_args=NO_MAX,
      supported_sub_args='b:c:l:p:s:',
      supported_private_args=['retention=', 'pap='],
      file_url_ok=False,
      provider_url_ok=False,
      urls_start_arg=0,
      gs_api_support=[ApiSelector.XML, ApiSelector.JSON],
      gs_default_api=ApiSelector.JSON,
      argparse_arguments=[
          CommandArgument.MakeZeroOrMoreCloudBucketURLsArgument()
      ],
  )
  # Help specification. See help_provider.py for documentation.
  help_spec = Command.HelpSpec(
      help_name='mb',
      help_name_aliases=[
          'createbucket',
          'makebucket',
          'md',
          'mkdir',
          'location',
          'dra',
          'dras',
          'reduced_availability',
          'durable_reduced_availability',
          'rr',
          'reduced_redundancy',
          'standard',
          'storage class',
          'nearline',
          'nl',
      ],
      help_type='command_help',
      help_one_line_summary='Make buckets',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )

  def RunCommand(self):
    """Command entry point for the mb command."""
    bucket_policy_only = None
    location = None
    storage_class = None
    seconds = None
    public_access_prevention = None
    if self.sub_opts:
      for o, a in self.sub_opts:
        if o == '-l':
          location = a
        elif o == '-p':
          # Project IDs are sent as header values when using gs and s3 XML APIs.
          InsistAscii(a, 'Invalid non-ASCII character found in project ID')
          self.project_id = a
        elif o == '-c' or o == '-s':
          storage_class = NormalizeStorageClass(a)
        elif o == '--retention':
          seconds = RetentionInSeconds(a)
        elif o == '-b':
          if self.gsutil_api.GetApiSelector('gs') != ApiSelector.JSON:
            raise CommandException('The -b <on|off> option '
                                   'can only be used with the JSON API')
          InsistOnOrOff(a, 'Only on and off values allowed for -b option')
          bucket_policy_only = (a == 'on')
        elif o == '--pap':
          public_access_prevention = a

    bucket_metadata = apitools_messages.Bucket(location=location,
                                               storageClass=storage_class)
    if bucket_policy_only or public_access_prevention:
      bucket_metadata.iamConfiguration = IamConfigurationValue()
      iam_config = bucket_metadata.iamConfiguration
      if bucket_policy_only:
        iam_config.bucketPolicyOnly = BucketPolicyOnlyValue()
        iam_config.bucketPolicyOnly.enabled = bucket_policy_only
      if public_access_prevention:
        iam_config.publicAccessPrevention = public_access_prevention

    for bucket_url_str in self.args:
      bucket_url = StorageUrlFromString(bucket_url_str)
      if seconds is not None:
        if bucket_url.scheme != 'gs':
          raise CommandException('Retention policy can only be specified for '
                                 'GCS buckets.')
        retention_policy = (apitools_messages.Bucket.RetentionPolicyValue(
            retentionPeriod=seconds))
        bucket_metadata.retentionPolicy = retention_policy

      if public_access_prevention and self.gsutil_api.GetApiSelector(
          bucket_url.scheme) != ApiSelector.JSON:
        raise CommandException(
            'The --pap option can only be used for GCS Buckets with the JSON API'
        )
      if not bucket_url.IsBucket():
        raise CommandException('The mb command requires a URL that specifies a '
                               'bucket.\n"%s" is not valid.' % bucket_url)
      if (not BUCKET_NAME_RE.match(bucket_url.bucket_name) or
          TOO_LONG_DNS_NAME_COMP.search(bucket_url.bucket_name)):
        raise InvalidUrlError('Invalid bucket name in URL "%s"' %
                              bucket_url.bucket_name)

      self.logger.info('Creating %s...', bucket_url)
      # Pass storage_class param only if this is a GCS bucket. (In S3 the
      # storage class is specified on the key object.)
      try:
        self.gsutil_api.CreateBucket(bucket_url.bucket_name,
                                     project_id=self.project_id,
                                     metadata=bucket_metadata,
                                     provider=bucket_url.scheme)
      except BadRequestException as e:
        if (e.status == 400 and e.reason == 'DotfulBucketNameNotUnderTld' and
            bucket_url.scheme == 'gs'):
          bucket_name = bucket_url.bucket_name
          final_comp = bucket_name[bucket_name.rfind('.') + 1:]
          raise CommandException('\n'.join(
              textwrap.wrap(
                  'Buckets with "." in the name must be valid DNS names. The bucket'
                  ' you are attempting to create (%s) is not a valid DNS name,'
                  ' because the final component (%s) is not currently a valid part'
                  ' of the top-level DNS tree.' % (bucket_name, final_comp))))
        else:
          raise

    return 0
