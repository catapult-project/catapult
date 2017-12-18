# Copyright 2014 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Setup script for oauth2client.

Also installs included versions of third party libraries, if those libraries
are not already installed.
"""
from __future__ import print_function

import sys

if sys.version_info < (2, 6):
    print('oauth2client requires python2 version >= 2.6.', file=sys.stderr)
    sys.exit(1)
if (3, 1) <= sys.version_info < (3, 3):
    print('oauth2client requires python3 version >= 3.3.', file=sys.stderr)
    sys.exit(1)

from setuptools import find_packages
from setuptools import setup

install_requires = [
    'httplib2>=0.9.1',
    'pyasn1>=0.1.7',
    'pyasn1-modules>=0.0.5',
    'rsa>=3.1.4',
    'six>=1.6.1',
]

long_desc = """The oauth2client is a client library for OAuth 2.0."""

import oauth2client
version = oauth2client.__version__

setup(
    name="oauth2client",
    version=version,
    description="OAuth 2.0 client library",
    long_description=long_desc,
    author="Google Inc.",
    url="http://github.com/google/oauth2client/",
    install_requires=install_requires,
    packages=find_packages(),
    license="Apache 2.0",
    keywords="google oauth 2.0 http client",
    classifiers=[
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
