# Copyright 2014 Google Inc. All Rights Reserved.
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

"""Installs certificate on phone with KitKat."""

import argparse
import logging
import os
import subprocess
import sys

KEYCODE_ENTER = '66'
KEYCODE_TAB = '61'

class CertInstallError(Exception):
  pass

class CertRemovalError(Exception):
  pass


class AndroidCertInstaller(object):
  """Certificate installer for phones with KitKat."""

  def __init__(self, device_id, cert_name, cert_path):
    if not os.path.exists(cert_path):
      raise ValueError('Not a valid certificate path')
    self.device_id = device_id
    self.cert_name = cert_name
    self.cert_path = cert_path
    self.file_name = os.path.basename(self.cert_path)
    self.reformatted_cert_fname = None
    self.reformatted_cert_path = None
    self.android_cacerts_path = None

  @staticmethod
  def _run_cmd(cmd, dirname=None):
    return subprocess.check_output(cmd, cwd=dirname)

  def _adb(self, *args):
    """Runs the adb command."""
    cmd = ['adb']
    if self.device_id:
      cmd.extend(['-s', self.device_id])
    cmd.extend(args)
    return self._run_cmd(cmd)

  def _adb_su_shell(self, *args):
    """Runs command as root."""
    cmd = ['shell', 'su', '-c']
    cmd.extend(args)
    return self._adb(*cmd)

  def _get_property(self, prop):
    return self._adb('shell', 'getprop', prop).strip()

  def check_device(self):
    install_warning = False
    if self._get_property('ro.product.device') != 'hammerhead':
      logging.warning('Device is not hammerhead')
      install_warning = True
    if self._get_property('ro.build.version.release') != '4.4.2':
      logging.warning('Version is not 4.4.2')
      install_warning = True
    if install_warning:
      logging.warning('Certificate may not install properly')

  def _input_key(self, key):
    """Inputs a keyevent."""
    self._adb('shell', 'input', 'keyevent', key)

  def _input_text(self, text):
    """Inputs text."""
    self._adb('shell', 'input', 'text', text)

  @staticmethod
  def _remove(file_name):
    """Deletes file."""
    if os.path.exists(file_name):
      os.remove(file_name)

  def _format_hashed_cert(self):
    """Makes a certificate file that follows the format of files in cacerts."""
    self._remove(self.reformatted_cert_path)
    contents = self._run_cmd(['openssl', 'x509', '-inform', 'PEM', '-text',
                              '-in', self.cert_path])
    description, begin_cert, cert_body = contents.rpartition('-----BEGIN '
                                                             'CERTIFICATE')
    contents = ''.join([begin_cert, cert_body, description])
    with open(self.reformatted_cert_path, 'w') as cert_file:
      cert_file.write(contents)

  def _remove_cert_from_cacerts(self):
    self._adb_su_shell('mount', '-o', 'remount,rw', '/system')
    self._adb_su_shell('rm', self.android_cacerts_path)

  def _is_cert_installed(self):
    return (self._adb_su_shell('ls', self.android_cacerts_path).strip() ==
            self.android_cacerts_path)

  def _generate_reformatted_cert_path(self):
    # Determine OpenSSL version, string is of the form
    # 'OpenSSL 0.9.8za 5 Jun 2014' .
    openssl_version = self._run_cmd(['openssl', 'version']).split()

    if len(openssl_version) < 2:
      raise ValueError('Unexpected OpenSSL version string: ', openssl_version)

    # subject_hash flag name changed as of OpenSSL version 1.0.0 .
    is_old_openssl_version = openssl_version[1].startswith('0')
    subject_hash_flag = (
        '-subject_hash' if is_old_openssl_version else '-subject_hash_old')

    output = self._run_cmd(['openssl', 'x509', '-inform', 'PEM',
                            subject_hash_flag, '-in', self.cert_path],
                           os.path.dirname(self.cert_path))
    self.reformatted_cert_fname = output.partition('\n')[0].strip() + '.0'
    self.reformatted_cert_path = os.path.join(os.path.dirname(self.cert_path),
                                              self.reformatted_cert_fname)
    self.android_cacerts_path = ('/system/etc/security/cacerts/%s' %
                                 self.reformatted_cert_fname)

  def remove_cert(self):
    self._generate_reformatted_cert_path()

    if self._is_cert_installed():
      self._remove_cert_from_cacerts()

    if self._is_cert_installed():
      raise CertRemovalError('Cert Removal Failed')

  def install_cert(self, overwrite_cert=False):
    """Installs a certificate putting it in /system/etc/security/cacerts."""
    self._generate_reformatted_cert_path()

    if self._is_cert_installed():
      if overwrite_cert:
        self._remove_cert_from_cacerts()
      else:
        logging.info('cert is already installed')
        return

    self._format_hashed_cert()
    self._adb('push', self.reformatted_cert_path, '/sdcard/')
    self._remove(self.reformatted_cert_path)
    self._adb_su_shell('mount', '-o', 'remount,rw', '/system')
    self._adb_su_shell(
        'cp', '/sdcard/%s' % self.reformatted_cert_fname,
        '/system/etc/security/cacerts/%s' % self.reformatted_cert_fname)
    self._adb_su_shell('chmod', '644', self.android_cacerts_path)
    if not self._is_cert_installed():
      raise CertInstallError('Cert Install Failed')

  def install_cert_using_gui(self):
    """Installs certificate on the device using adb commands."""
    self.check_device()
    # TODO(mruthven): Add a check to see if the certificate is already installed
    # Install the certificate.
    logging.info('Installing %s on %s', self.cert_path, self.device_id)
    self._adb('push', self.cert_path, '/sdcard/')

    # Start credential install intent.
    self._adb('shell', 'am', 'start', '-W', '-a', 'android.credentials.INSTALL')

    # Move to and click search button.
    self._input_key(KEYCODE_TAB)
    self._input_key(KEYCODE_TAB)
    self._input_key(KEYCODE_ENTER)

    # Search for certificate and click it.
    # Search only works with lower case letters
    self._input_text(self.file_name.lower())
    self._input_key(KEYCODE_ENTER)

    # These coordinates work for hammerhead devices.
    self._adb('shell', 'input', 'tap', '300', '300')

    # Name the certificate and click enter.
    self._input_text(self.cert_name)
    self._input_key(KEYCODE_TAB)
    self._input_key(KEYCODE_TAB)
    self._input_key(KEYCODE_TAB)
    self._input_key(KEYCODE_ENTER)

    # Remove the file.
    self._adb('shell', 'rm', '/sdcard/' + self.file_name)


def parse_args():
  """Parses command line arguments."""
  parser = argparse.ArgumentParser(description='Install cert on device.')
  parser.add_argument(
      '-n', '--cert-name', default='dummycert', help='certificate name')
  parser.add_argument(
      '--overwrite', default=False, action='store_true',
      help='Overwrite certificate file if it is already installed')
  parser.add_argument(
      '--remove', default=False, action='store_true',
      help='Remove certificate file if it is installed')
  parser.add_argument(
      '--device-id', help='device serial number')
  parser.add_argument(
      'cert_path', help='Certificate file path')
  return parser.parse_args()


def main():
  args = parse_args()
  cert_installer = AndroidCertInstaller(args.device_id, args.cert_name,
                                        args.cert_path)
  if args.remove:
    cert_installer.remove_cert()
  else:
    cert_installer.install_cert(args.overwrite)


if __name__ == '__main__':
  sys.exit(main())
