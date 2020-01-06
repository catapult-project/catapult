#!/bin/bash

# Copyright 2019 Google LLC
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

# Create a .boto config file for gsutil to use in Kokoro tests.
# https://cloud.google.com/storage/docs/gsutil/commands/config

GSUTIL_KEY=$1
API=$2
OUTPUT_FILE=$3

cat > $3 << EOM
[Credentials]
gs_service_key_file = $GSUTIL_KEY

[GSUtil]
default_project_id = bigstore-gsutil-testing
prefer_api = $API
test_hmac_service_account = sa-hmac@bigstore-gsutil-testing.iam.gserviceaccount.com
test_hmac_list_service_account = sa-hmac-list@bigstore-gsutil-testing.iam.gserviceaccount.com
test_hmac_alt_service_account = sa-hmac2@bigstore-gsutil-testing.iam.gserviceaccount.com
test_impersonate_service_account = bigstore-gsutil-impersonation@bigstore-gsutil-testing.iam.gserviceaccount.com
test_impersonate_failure_account = no-impersonation@bigstore-gsutil-testing.iam.gserviceaccount.com

[OAuth2]
client_id = 909320924072.apps.googleusercontent.com
client_secret = p3RlpR10xMFh9ZXBS/ZNLYUu
EOM
