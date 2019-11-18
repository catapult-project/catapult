# Protocol Buffers - Google's data interchange format
# Copyright 2008 Google Inc.  All rights reserved.
# https://developers.google.com/protocol-buffers/
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import six
import struct

import wire_format


def _VarintSize(value):
  """Compute the size of a varint value."""
  if value <= 0x7f: return 1
  if value <= 0x3fff: return 2
  if value <= 0x1fffff: return 3
  if value <= 0xfffffff: return 4
  if value <= 0x7ffffffff: return 5
  if value <= 0x3ffffffffff: return 6
  if value <= 0x1ffffffffffff: return 7
  if value <= 0xffffffffffffff: return 8
  if value <= 0x7fffffffffffffff: return 9
  return 10


def _SignedVarintSize(value):
  """Compute the size of a signed varint value."""
  if value < 0: return 10
  if value <= 0x7f: return 1
  if value <= 0x3fff: return 2
  if value <= 0x1fffff: return 3
  if value <= 0xfffffff: return 4
  if value <= 0x7ffffffff: return 5
  if value <= 0x3ffffffffff: return 6
  if value <= 0x1ffffffffffff: return 7
  if value <= 0xffffffffffffff: return 8
  if value <= 0x7fffffffffffffff: return 9
  return 10


def _VarintEncoder():
  """Return an encoder for a basic varint value (does not include tag)."""

  def EncodeVarint(write, value):
    bits = value & 0x7f
    value >>= 7
    while value:
      write(six.int2byte(0x80|bits))
      bits = value & 0x7f
      value >>= 7
    return write(six.int2byte(bits))

  return EncodeVarint


def _SignedVarintEncoder():
  """Return an encoder for a basic signed varint value (does not include
  tag)."""

  def EncodeSignedVarint(write, value):
    if value < 0:
      value += (1 << 64)
    bits = value & 0x7f
    value >>= 7
    while value:
      write(six.int2byte(0x80|bits))
      bits = value & 0x7f
      value >>= 7
    return write(six.int2byte(bits))

  return EncodeSignedVarint


_EncodeVarint = _VarintEncoder()
_EncodeSignedVarint = _SignedVarintEncoder()


def _VarintBytes(value):
  """Encode the given integer as a varint and return the bytes.  This is only
  called at startup time so it doesn't need to be fast."""

  pieces = []
  _EncodeVarint(pieces.append, value)
  return b"".join(pieces)


def TagBytes(field_number, wire_type):
  """Encode the given tag and return the bytes.  Only called at startup."""

  return _VarintBytes(wire_format.PackTag(field_number, wire_type))


def _SimpleEncoder(wire_type, encode_value, compute_value_size):
  """Return a constructor for an encoder for fields of a particular type.

  Args:
      wire_type:  The field's wire type, for encoding tags.
      encode_value:  A function which encodes an individual value, e.g.
        _EncodeVarint().
      compute_value_size:  A function which computes the size of an individual
        value, e.g. _VarintSize().
  """

  def SpecificEncoder(field_number, is_repeated, is_packed):
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        size = 0
        for element in value:
          size += compute_value_size(element)
        local_EncodeVarint(write, size)
        for element in value:
          encode_value(write, element)
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          encode_value(write, element)
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        return encode_value(write, value)
      return EncodeField

  return SpecificEncoder


def _FloatingPointEncoder(wire_type, format):
  """Return a constructor for an encoder for float fields.

  This is like StructPackEncoder, but catches errors that may be due to
  passing non-finite floating-point values to struct.pack, and makes a
  second attempt to encode those values.

  Args:
      wire_type:  The field's wire type, for encoding tags.
      format:  The format string to pass to struct.pack().
  """

  value_size = struct.calcsize(format)
  if value_size == 4:
    def EncodeNonFiniteOrRaise(write, value):
      # Remember that the serialized form uses little-endian byte order.
      if value == _POS_INF:
        write(b'\x00\x00\x80\x7F')
      elif value == _NEG_INF:
        write(b'\x00\x00\x80\xFF')
      elif value != value:           # NaN
        write(b'\x00\x00\xC0\x7F')
      else:
        raise
  elif value_size == 8:
    def EncodeNonFiniteOrRaise(write, value):
      if value == _POS_INF:
        write(b'\x00\x00\x00\x00\x00\x00\xF0\x7F')
      elif value == _NEG_INF:
        write(b'\x00\x00\x00\x00\x00\x00\xF0\xFF')
      elif value != value:                         # NaN
        write(b'\x00\x00\x00\x00\x00\x00\xF8\x7F')
      else:
        raise
  else:
    raise ValueError('Can\'t encode floating-point values that are '
                     '%d bytes long (only 4 or 8)' % value_size)

  def SpecificEncoder(field_number, is_repeated, is_packed):
    local_struct_pack = struct.pack
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        local_EncodeVarint(write, len(value) * value_size)
        for element in value:
          # This try/except block is going to be faster than any code that
          # we could write to check whether element is finite.
          try:
            write(local_struct_pack(format, element))
          except SystemError:
            EncodeNonFiniteOrRaise(write, element)
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          try:
            write(local_struct_pack(format, element))
          except SystemError:
            EncodeNonFiniteOrRaise(write, element)
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        try:
          write(local_struct_pack(format, value))
        except SystemError:
          EncodeNonFiniteOrRaise(write, value)
      return EncodeField

  return SpecificEncoder


Int32Encoder = Int64Encoder = EnumEncoder = _SimpleEncoder(
    wire_format.WIRETYPE_VARINT, _EncodeSignedVarint, _SignedVarintSize)

UInt32Encoder = UInt64Encoder = _SimpleEncoder(
    wire_format.WIRETYPE_VARINT, _EncodeVarint, _VarintSize)

FloatEncoder    = _FloatingPointEncoder(wire_format.WIRETYPE_FIXED32, '<f')

DoubleEncoder   = _FloatingPointEncoder(wire_format.WIRETYPE_FIXED64, '<d')


def BoolEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a boolean field."""

  false_byte = b'\x00'
  true_byte = b'\x01'
  if is_packed:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
    local_EncodeVarint = _EncodeVarint
    def EncodePackedField(write, value):
      write(tag_bytes)
      local_EncodeVarint(write, len(value))
      for element in value:
        if element:
          write(true_byte)
        else:
          write(false_byte)
    return EncodePackedField
  elif is_repeated:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_VARINT)
    def EncodeRepeatedField(write, value):
      for element in value:
        write(tag_bytes)
        if element:
          write(true_byte)
        else:
          write(false_byte)
    return EncodeRepeatedField
  else:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_VARINT)
    def EncodeField(write, value):
      write(tag_bytes)
      if value:
        return write(true_byte)
      return write(false_byte)
    return EncodeField


def StringEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a string field."""

  tag = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
  local_EncodeVarint = _EncodeVarint
  local_len = len
  assert not is_packed
  if is_repeated:
    def EncodeRepeatedField(write, value):
      for element in value:
        encoded = element.encode('utf-8')
        write(tag)
        local_EncodeVarint(write, local_len(encoded))
        write(encoded)
    return EncodeRepeatedField
  else:
    def EncodeField(write, value):
      encoded = value.encode('utf-8')
      write(tag)
      local_EncodeVarint(write, local_len(encoded))
      return write(encoded)
    return EncodeField

