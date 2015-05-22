#!/bin/bash

# This script prepares the dashboard to be deployed and then
# invokes appcfg.py to upload it. If successful, this uploads
# a new version but doesn't set that version as default.

# USAGE: ./deploy.sh [APP_ID]

# TODO: Finish the deploy script. See: http://crbug.com/488565
#  - Run lint and tests.
#  - Vulcanizing Polymer components.
#  - Versioning of JS and CS.

default_appid=generic.data
appid=${1:-$default_appid}

user=$(git config --get user.email | sed 's/@.*//')
hash=$(git rev-parse --short=10 HEAD)-
version=$hash-$user

dir=$(cd `dirname "$0"` && pwd)

appcfg.py --application="$appid" --version="$version" update "$dir"
