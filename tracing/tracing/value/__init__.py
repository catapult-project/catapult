# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Simplified version of telemetry Value system, just enough for us to get
# us up and running.


class Value(object):

  def __init__(self, canonical_url, name, units, description=None,
               important=False, ir_stable_id=None):
    self.canonical_url = canonical_url
    self.name = name
    self.units = units
    self.description = description
    self.important = important
    self.ir_stable_id = ir_stable_id

  def AsDict(self):
    d = {
        'canonical_url': self.canonical_url,
        'name': self.name,
        'important': self.important
    }
    # Only dump values if they're non-None, because Python json-ification turns
    # these to null, instead of leaving them out.
    if self.units is not None:
      d['units'] = self.units

    if self.description is not None:
      d['description'] = self.description

    if self.ir_stable_id is not None:
      d['ir_stable_id'] = self.ir_stable_id

    self._AsDictInto(d)
    assert 'type' in d

    return d

  def _AsDictInto(self, d):
    raise NotImplementedError()

  @classmethod
  def FromDict(cls, d):
    if d['type'] == 'dict':
      return DictValue.FromDict(d)
    elif d['type'] == 'scalar':
      return ScalarValue.FromDict(d)
    elif d['type'] == 'failure':
      return FailureValue.FromDict(d)
    elif d['type'] == 'skip':
      return SkipValue.FromDict(d)
    else:
      raise NotImplementedError()


# TODO(eakuefner): Change to NumericValue after porting Unit
# (https://github.com/catapult-project/catapult/issues/2049)
class ScalarValue(Value):

  def __init__(self, canonical_url, name, value, description=None,
               important=False, ir_stable_id=None):
    assert isinstance(value, dict)
    super(ScalarValue, self).__init__(canonical_url, name, units=None,
                                      description=description,
                                      important=important,
                                      ir_stable_id=ir_stable_id)
    self._value = value

  def __repr__(self):
    return '%s("%s", "%s")' % (self.__class__.__name__,
                               self.name, self.value)

  def _AsDictInto(self, d):
    d['type'] = 'scalar'
    d['value'] = self._value

  @classmethod
  def FromDict(cls, d):
    assert d.get('units', None) == None
    return cls(d['canonical_url'], name=d['name'],
               description=d.get('description', None),
               value=d['value'],
               important=d['important'],
               ir_stable_id=d.get('ir_stable_id', None))

  @property
  def value(self):
    return self._value

  def __getitem__(self, key):
    return self._value[key]


class DictValue(Value):

  def __init__(self, canonical_url, name, value, description=None,
               important=False, ir_stable_id=None):
    assert isinstance(value, dict)
    super(DictValue, self).__init__(canonical_url, name, units=None,
                                    description=description,
                                    important=important,
                                    ir_stable_id=ir_stable_id)
    self._value = value

  def __repr__(self):
    return '%s("%s", "%s")' % (self.__class__.__name__,
                               self.name, self.value)

  def _AsDictInto(self, d):
    d['type'] = 'dict'
    d['value'] = self._value

  @classmethod
  def FromDict(cls, d):
    assert d.get('units', None) == None
    return cls(d['canonical_url'], name=d['name'],
               description=d.get('description', None),
               value=d['value'],
               important=d['important'],
               ir_stable_id=d.get('ir_stable_id', None))

  @property
  def value(self):
    return self._value

  def __getitem__(self, key):
    return self._value[key]

class FailureValue(Value):

  def __init__(self, canonical_url, failure_type_name, description, stack,
               important=False, ir_stable_id=None):
    super(FailureValue, self).__init__(canonical_url,
                                       name=failure_type_name,
                                       units=None,
                                       description=description,
                                       important=important,
                                       ir_stable_id=ir_stable_id)
    assert isinstance(stack, basestring)
    self.stack = stack

  def __repr__(self):
    return '%s("%s", "%s")' % (self.__class__.__name__,
                               self.name, self.description)

  def _AsDictInto(self, d):
    d['type'] = 'failure'
    d['stack_str'] = self.stack

  @classmethod
  def FromDict(cls, d):
    assert d.get('units', None) == None
    return cls(d['canonical_url'],
               failure_type_name=d['name'],
               description=d.get('description', None),
               stack=d['stack_str'],
               important=d.get('important', False),
               ir_stable_id=d.get('ir_stable_id', None))

  def GetGTestPrintString(self):
    return self.stack


class SkipValue(Value):

  def __init__(self, canonical_url, skipped_result_name,
               description=None, important=False, ir_stable_id=None):
    super(SkipValue, self).__init__(canonical_url,
                                    name=skipped_result_name,
                                    units=None,
                                    description=description,
                                    important=important,
                                    ir_stable_id=ir_stable_id)

  def __repr__(self):
    return '%s("%s", "%s")' % (self.__class__.__name__,
                               self.name, self.description)

  def _AsDictInto(self, d):
    d['type'] = 'skip'

  @classmethod
  def FromDict(cls, d):
    assert d.get('units', None) == None
    return cls(d['canonical_url'],
               skipped_result_name=d['name'],
               description=d.get('description', None),
               important=d.get('important', False),
               ir_stable_id=d.get('ir_stable_id', None))
