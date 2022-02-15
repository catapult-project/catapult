#!/bin/bash

# This shell script is used for setting up our Kokoro Ubuntu environment
# with necessary dependencies for running integration tests, and then
# running tests when PRs are submitted or code is pushed.
#
# This script is intentionally a bit verbose with what it writes to stdout.
# Since its output is only visible in test run logs, and those logs are only
# likely to be viewed in the event of an error, I decided it would be beneficial
# to leave some settings like `set -x` and `cat`s and `echo`s in. This should
# help future engineers debug what went wrong, and assert info about the test
# environment at the cost of a small preamble in the logs.

# -x : Display commands being run
# -u : Disallow unset variables
# Doc: https://www.gnu.org/software/bash/manual/html_node/The-Set-Builtin.html#The-Set-Builtin
set -xu


# PYMAJOR, PYMINOR, and API environment variables are set per job in:
# go/kokoro-gsutil-configs
PYVERSION="$PYMAJOR.$PYMINOR"

# Processes to use based on default Kokoro specs here:
# go/gcp-ubuntu-vm-configuration-v32i
# go/kokoro-macos-external-configuration
PROCS="8"

GSUTIL_KEY="/tmpfs/src/keystore/74008_gsutil_kokoro_service_key"
GSUTIL_SRC="/tmpfs/src/github/src/gsutil"
GSUTIL_ENTRYPOINT="$GSUTIL_SRC/gsutil.py"
CFG_GENERATOR="$GSUTIL_SRC/test/ci/kokoro/config_generator.sh"
BOTO_CONFIG="/tmpfs/src/.boto_$API"

# gsutil looks for this environment variable to find .boto config
# https://cloud.google.com/storage/docs/boto-gsutil
export BOTO_PATH="$BOTO_CONFIG"

# Set the locale to utf-8 for macos b/154863917
if [[ $KOKORO_JOB_NAME =~ "macos" ]]; then
  export LANG=en_US.UTF-8
fi

function latest_python_release {
  # Return string with latest Python version triplet for a given version tuple.
  # Example: PYVERSION="2.7"; latest_python_release -> "2.7.15"
  pyenv install --list \
    | grep -vE "(^Available versions:|-src|dev|rc|alpha|beta|(a|b)[0-9]+)" \
    | grep -E "^\s*$PYVERSION" \
    | sed -E 's/^[[:space:]]+//' \
    | tail -1
}

function install_pyenv {
  # Install pyenv if missing.
  if ! [ "$(pyenv --version)" ]; then
    # MacOS VM does not have pyenv installed by default.
    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init --path)"
  fi
  pyenv update
  # To address pyenv issue: See b/187701234#comment12.
  cd ~/.pyenv/plugins/python-build/../.. && git pull && \
     git checkout 783870759566a77d09b426e0305bc0993a522765 && cd -
}

function install_python {
  pyenv install -s "$PYVERSIONTRIPLET"
}

function init_configs {
  # Create .boto config for gsutil
  # https://cloud.google.com/storage/docs/gsutil/commands/config
  bash "$CFG_GENERATOR" "$GSUTIL_KEY" "$API" "$BOTO_CONFIG"
  cat "$BOTO_CONFIG"
}

function init_python {
  # Ensure latest release of desired Python version is installed, and that
  # dependencies from pip, e.g. crcmod, are installed.
  install_pyenv
  PYVERSIONTRIPLET=$(latest_python_release)
  install_python
  pyenv global "$PYVERSIONTRIPLET"
  # Check if Python version is same as set by the config
  py_ver=$(python -V 2>&1 | grep -Eo 'Python ([0-9]+)\.[0-9]+')
  if ! [[ $py_ver == "Python $PYVERSION" ]]; then
    echo "Python version $py_ver does not match the required version"
    exit 1
  fi
  python -m pip install -U crcmod
}

function update_submodules {
  # Most dependencies are included in gsutil via submodules. We need to
  # tell git to grab our dependencies' source before we can depend on them.
  cd "$GSUTIL_SRC"
  git submodule update --init --recursive
}


init_configs
init_python
update_submodules

set -e

# Check that we're using the correct config.
python "$GSUTIL_ENTRYPOINT" version -l
# Run integration tests.
python "$GSUTIL_ENTRYPOINT" test -p "$PROCS"
# Run custom endpoint tests.
# We don't generate a .boto for these tests since there are only a few settings.
python "$GSUTIL_ENTRYPOINT" \
  -o "Credentials:gs_host=storage-psc.p.googleapis.com" \
  -o "Credentials:gs_host_header=storage.googleapis.com" \
  -o "Credentials:gs_json_host=storage-psc.p.googleapis.com" \
  -o "Credentials:gs_json_host_header=www.googleapis.com" \
  test gslib.tests.test_psc

# Run mTLS authentication test.
if [[ $API == "json" ]]; then
  MTLS_TEST_ACCOUNT_REFRESH_TOKEN="/tmpfs/src/keystore/74008_mtls_test_account_refresh_token"
  MTLS_TEST_ACCOUNT_CLIENT_ID="/tmpfs/src/keystore/74008_mtls_test_account_client_id"
  MTLS_TEST_ACCOUNT_CLIENT_SECRET="/tmpfs/src/keystore/74008_mtls_test_account_client_secret"
  MTLS_TEST_CERT_PATH="/tmpfs/src/keystore/74008_mtls_test_cert"

  # Generate .boto config specifically for mTLS tests.
  bash "$CFG_GENERATOR" "" "$API" "$BOTO_CONFIG" "$MTLS_TEST_ACCOUNT_REFRESH_TOKEN" "$MTLS_TEST_ACCOUNT_CLIENT_ID" "$MTLS_TEST_ACCOUNT_CLIENT_SECRET" "$MTLS_TEST_CERT_PATH"

  # Run mTLS E2E test.
  python "$GSUTIL_ENTRYPOINT" test gslib.tests.test_mtls.TestMtls
fi
