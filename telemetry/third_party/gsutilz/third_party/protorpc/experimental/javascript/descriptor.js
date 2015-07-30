// Copyright 2011 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Various descriptor definitions.
 * @author joetyson@gmail.com (Joe Tyson)
 */

goog.provide('ProtoRpc.EnumDescriptor');
goog.provide('ProtoRpc.EnumValueDescriptor');
/*
goog.provide('ProtoRpc.FieldDescriptor');
goog.provide('ProtoRpc.MessageDescriptor');
goog.provide('ProtoRpc.MethodDescriptor');
goog.provide('ProtoRpc.FileDescriptor');
goog.provide('ProtoRpc.FileSet');
goog.provide('ProtoRpc.ServiceDescriptor');*/

goog.require('ProtoRpc.IntegerField');
goog.require('ProtoRpc.Message');
goog.require('ProtoRpc.StringField');


/**
 *
 */
ProtoRpc.EnumValueDescriptor = ProtoRpc.Message('EnumValueDescriptor', {
  fields: {
    'name': new ProtoRpc.StringField(1, {required: true}),
    'number': new ProtoRpc.IntegerField(2, {required: true})
  }
});


/**
 * Enum class descriptor.
 * @export
 */
ProtoRpc.EnumDescriptor = ProtoRpc.Message('EnumDescriptor', {
  fields: {
    'name': new ProtoRpc.StringField(1),
    'values': new ProtoRpc.MessageField(ProtoRpc.EnumValueDescriptor, 2, {
      repeated: true})
  }
});
