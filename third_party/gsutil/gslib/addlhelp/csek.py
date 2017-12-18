# -*- coding: utf-8 -*-
# Copyright 2015 Google Inc. All Rights Reserved.
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
"""Additional help text for encryption and customer-supplied encryption keys."""

from __future__ import absolute_import

from gslib.help_provider import HelpProvider

_DETAILED_HELP_TEXT = ("""
<B>OVERVIEW</B>
  By default, Google Cloud Storage encrypts all object data using
  Google-managed encryption keys and the AES256 encryption algorithm. However,
  you can also supply your own encryption keys, also known as customer-supplied
  encryption keys. Google Cloud Storage will not permanently store these keys
  on Google's servers or otherwise manage them.

  gsutil accepts customer-supplied encryption and decryption keys for
  interacting with Google Cloud Storage objects using the JSON API. The keys
  are provided via the .boto configuration file like so:

    [GSUtil]
    encryption_key = ...
    decryption_key1 = ...
    decryption_key2 = ...

  Each key is a RFC 4648 Base64-encoded string of 256 bits of data for use
  with the AES256 encryption algorithm.


<B>ENCRYPTION BEHAVIOR</B>
  A single encryption_key may be specified in the .boto configuration file,
  and multiple decryption_keys may be specified.

  If encryption_key exists in the .boto configuration file, gsutil ensures that
  data it writes or copies in Google Cloud Storage is encrypted with that
  key. If encryption_key is not supplied, gsutil ensures that all data it
  writes or copies instead uses Google-managed keys.
  WARNING: This means gsutil will replace customer-supplied encryption with
  Google-managed encryption if encryption_key is not specified but a
  matching decryption_key is specified.

  Objects encrypted with customer-supplied encryption keys require the matching
  decryption key any time they are downloaded or copied (via the gsutil cat,
  cp, mv, or rsync commands). Viewing the CRC32C or MD5 hashes of such objects
  (via the ls -L or stat commands) also requires the matching decryption key.

  If a matching key exists in the .boto configuration, gsutil provides it
  as needed in requests to Google Cloud Storage and operates on the
  decrypted results. gsutil never stores encrypted data on your local disk.

  gsutil automatically detects the correct customer-supplied encryption key to
  use for a cloud object by comparing the key's SHA256 hash against the hash of
  the customer-supplied encryption key. gsutil considers the configured
  encryption key and up to 100 decryption keys when searching for a match.
  Decryption keys must be listed in the boto configuration file in ascending
  numerical order starting with 1. For example, in the following configuration:

    decryption_key1 = ...
    decryption_key9 = ...
    decryption_key10 = ...
    decryption_key11 = ...

  decryption_keys 9, 10, and 11 will be ignored because no values for
  decryption_keys 2 through 8 are provided.


<B>RESUMABLE OPERATIONS AND ENCRYPTION KEYS</B>
  If the encryption_key in your boto configuration file changes during a
  partially-completed write or copy operation (for example, if you re-run
  a `gsutil cp` object upload after hitting ^C or encountering a network
  timeout), gsutil will restart the partially-completed operation to ensure
  that the destination object is written with the new key.


<B>GENERATING ENCRYPTION KEYS</B>
  Generating a 256-bit RFC 4648 Base64-encoded string for use as an encryption
  key can be easily done with Python:

    python -c 'import base64; import os;\\
               print(base64.encodestring(os.urandom(32)))'


<B>MANAGING ENCRYPTION KEYS</B>
  Because Google does not store customer-supplied encryption keys, if you lose
  your customer-supplied encryption key, you will permanently lose access to all
  of your data encrypted with that key. Therefore, it is recommended that you
  back up each encryption key to a secure location. The .boto configuration
  file should never be the only place where your key is stored.

  Also, when you create a customer-supplied encryption key, anyone who has the
  key and access to your objects can read those objects' data. Take precautions
  to ensure that your encryption keys are not shared with untrusted parties.


<B>ROTATING KEYS</B>
  To rotate keys, you can change your encryption_key configuration value to a
  decryption_key configuration value and then use a new value for the
  encryption_key. Then you can use the rewrite command to rotate keys in the
  cloud without downloading and re-uploading the data. For example, if your
  initial configuration is:

    # Old encryption key
    encryption_key = keyA...

  You can change it the configuration to:

    # New encryption key
    encryption_key = keyB...
    # Encryption key prior to rotation
    decryption_key1 = keyA...

  and rotate the encryption key on an object by running:

    gsutil rewrite gs://bucket/object temp-file


<B>PERFORMANCE IMPLICATIONS FOR CUSTOMER-SUPPLIED ENCRYPTION KEYS</B>
  Because gsutil must retrieve the SHA256 hash of an encryption key for
  comparison with decryption keys in the .boto configuration file, gsutil
  performs an additional metadata GET request for each object encrypted with a
  customer-supplied encryption key. In particular, performing a long listing via
  `gsutil ls -L` requires a GET request for each object that is
  encrypted with a customer-supplied encryption key. Therefore, listing such
  objects with the -L flag will require one operation per object, which will be
  substantially slower than listing objects encrypted with Google-owned keys.


<B>SECURITY IMPLICATIONS FOR CUSTOMER-SUPPLIED ENCRYPTION KEYS</B>
  gsutil always sends encryption keys over HTTPS, so your keys will never be
  visible on the network. However, the keys are present in your .boto
  configuration file as well as in the memory of the machine executing gsutil.
  Therefore, if this file or the machine are compromised, your encryption keys
  should also be considered compromised, and you should immediately perform
  key rotation for all objects encrypted with the compromised keys.


<B>XML API UNSUPPORTED</B>
  gsutil does not support using the XML API to interact with encrypted objects,
  and will use the JSON API if any encryption_key or decryption_keys are
  specified in configuration.
""")


class CommandOptions(HelpProvider):
  """Additional help text for customer-supplied encryption keys."""

  # Help specification. See help_provider.py for documentation.
  help_spec = HelpProvider.HelpSpec(
      help_name='csek',
      help_name_aliases=['decrypt', 'decryption', 'encrypt', 'encryption',
                         'csk'],
      help_type='additional_help',
      help_one_line_summary='Supplying Your Own Encryption Keys',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )
