# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

class GPUDevice(object):
  """Provides information about an individual GPU device.

     On platforms which support them, the vendor_id and device_id are
     PCI IDs. On other platforms, the vendor_string and device_string
     are platform-dependent strings.
  """

  _VENDOR_ID_MAP = {
      0x1002: 'ATI',
      0x8086: 'Intel',
      0x10de: 'Nvidia',
  }

  def __init__(self, vendor_id, device_id, vendor_string, device_string,
               driver_vendor, driver_version):
    self._vendor_id = vendor_id
    self._device_id = device_id
    self._vendor_string = vendor_string
    self._device_string = device_string
    self._driver_vendor = driver_vendor
    self._driver_version = driver_version

  def __str__(self):
    vendor = 'VENDOR = 0x%x' % self._vendor_id
    vendor_string = self._vendor_string
    if not vendor_string and self._vendor_id in self._VENDOR_ID_MAP:
      vendor_string = self._VENDOR_ID_MAP[self._vendor_id]
    if vendor_string:
      vendor += ' (%s)' % vendor_string
    device = 'DEVICE = 0x%x' % self._device_id
    if self._device_string:
      device += ' (%s)' % self._device_string
    return '%s, %s, DRIVER_VENDOR = %s, DRIVER_VERSION = %s' % (
        vendor, device, self._driver_vendor, self._driver_version)

  @classmethod
  def FromDict(cls, attrs):
    """Constructs a GPUDevice from a dictionary. Requires the
       following attributes to be present in the dictionary:

         vendor_id
         device_id
         vendor_string
         device_string
         driver_vendor
         driver_version

       Raises an exception if any attributes are missing.
    """
    return cls(attrs['vendor_id'], attrs['device_id'],
               attrs['vendor_string'], attrs['device_string'],
               # --browser=reference will use a very old build of Chrome
               # where driver_vendor and driver_version aren't part of
               # the dict.
               attrs.get('driver_vendor', ''),
               attrs.get('driver_version', ''))

  @property
  def vendor_id(self):
    """The GPU vendor's PCI ID as a number, or 0 if not available.

       Most desktop machines supply this information rather than the
       vendor and device strings."""
    return self._vendor_id

  @property
  def device_id(self):
    """The GPU device's PCI ID as a number, or 0 if not available.

       Most desktop machines supply this information rather than the
       vendor and device strings."""
    return self._device_id

  @property
  def vendor_string(self):
    """The GPU vendor's name as a string, or the empty string if not
       available.

       Most mobile devices supply this information rather than the PCI
       IDs."""
    return self._vendor_string

  @property
  def device_string(self):
    """The GPU device's name as a string, or the empty string if not
       available.

       Most mobile devices supply this information rather than the PCI
       IDs."""
    return self._device_string

  @property
  def driver_vendor(self):
    """The GPU driver vendor as a string, or the empty string if not
       available."""
    return self._driver_vendor

  @property
  def driver_version(self):
    """The GPU driver version as a string, or the empty string if not
       available."""
    return self._driver_version
