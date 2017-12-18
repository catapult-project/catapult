# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

SECRET_KEY = 'this string is not a real django secret key'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join('.', 'db.sqlite3'),
    }
}
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware'
)

ALLOWED_HOSTS = ['testserver']

GOOGLE_OAUTH2_CLIENT_ID = 'client_id2'
GOOGLE_OAUTH2_CLIENT_SECRET = 'hunter2'
GOOGLE_OAUTH2_SCOPES = ('https://www.googleapis.com/auth/cloud-platform',)

ROOT_URLCONF = 'tests.contrib.test_django_util'
