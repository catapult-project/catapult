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
 * @fileoverview Classes used to support Message's in ProtoRpc.
 * @author joetyson@gmail.com (Joe Tyson)
 */

goog.provide('ProtoRpc.BooleanField');
goog.provide('ProtoRpc.BytesField');
goog.provide('ProtoRpc.Enum');
goog.provide('ProtoRpc.EnumField');
goog.provide('ProtoRpc.EnumValue');
goog.provide('ProtoRpc.Field');
goog.provide('ProtoRpc.FloatField');
goog.provide('ProtoRpc.IntegerField');
goog.provide('ProtoRpc.Message');
goog.provide('ProtoRpc.MessageField');
goog.provide('ProtoRpc.StringField');
goog.provide('ProtoRpc.Variant');


goog.require('ProtoRpc.Util.Error');



/**
 * Invalid value for message error.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.ValidationError = function(pattern, args) {
  this.name = 'ValidationError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.ValidationError, ProtoRpc.Util.Error);



/**
 * Enumeration definition error.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.EnumDefinitionError = function(pattern, args) {
  this.name = 'EnumDefinitionError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.EnumDefinitionError, ProtoRpc.Util.Error);



/**
 * Field definition error.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.FieldDefinitionError = function(pattern, args) {
  this.name = 'FieldDefinitionError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.FieldDefinitionError, ProtoRpc.Util.Error);



/**
 * Invalid variant provided to field.
 * @constructor
 * @extends {ProtoRpc.FieldDefinitionError}
 */
ProtoRpc.InvalidVariantError = function(pattern, args) {
  this.name = 'InvalidVariantError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.InvalidVariantError, ProtoRpc.FieldDefinitionError);



/**
 * Invalid number provided to field.
 * @constructor
 * @extends {ProtoRpc.FieldDefinitionError}
 */
ProtoRpc.InvalidNumberError = function(pattern, args) {
  this.name = 'InvalidNumberError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.InvalidNumberError, ProtoRpc.FieldDefinitionError);



/**
 * Duplicate number assigned to field.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.DuplicateNumberError = function(pattern, args) {
  this.name = 'DuplicateNumberError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.DuplicateNumberError, ProtoRpc.Util.Error);



/**
 * Raised when definition is not found.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.DefinitionNotFoundError = function(pattern, args) {
  this.name = 'DefinitionNotFoundError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.DefinitionNotFoundError, ProtoRpc.Util.Error);



/**
 * Error found decoding message from encoded form.
 * @constructor
 * @extends {ProtoRpc.Util.Error}
 */
ProtoRpc.DecodeError = function(pattern, args) {
  this.name = 'DecodeError';
  goog.base(this, pattern, args);
};
goog.inherits(ProtoRpc.DecodeError, ProtoRpc.Util.Error);



/**
 * Enumeration which allows inversing of values by name or number.
 *
 * @param {Array.<ProtoRpc.EnumValueDescriptor>} values Enum values.
 * @constructor
 * @export
 */
ProtoRpc.Enum = function(values) {
  for (var number in values) {
    var value = new ProtoRpc.EnumValue(values[number], parseInt(number, 10));
    this[values[number]] = value;
  }
};


/**
 * Lookup value by its number.
 *
 * @param {Number} number
 * @return {ProtoRpc.EnumValue}
 * @export
 */
ProtoRpc.Enum.prototype.getValueFromNumber = function(number) {
  for (var key in this) {
    if (this.hasOwnProperty(key) &&
        this[key].valueOf() == number) {
      return this[key];
    }
  }
  return null;
};



/**
 * Represents a single value in an enumeration.
 *
 * Provides an API for getting both the value as a string as well
 * as the corresponding number:
 *
 *   VALUE = ProtoRpc.EnumValue('VALUE', 1)
 *   Number(VALUE); // returns 2
 *   String(VALUE); // returns 'VALUE'
 *
 * @param {string} name The value's name.
 * @param {Number} number the value's number.
 * @constructor
 */
ProtoRpc.EnumValue = function(name, number) {
  /**
   * @type {string}
   * @private
   */
  this.name_ = name;

  /**
   * @type {Number}
   * @private
   */
  this.number_ = number;
};


/**
 * @inheritDoc
 */
ProtoRpc.EnumValue.prototype.toString = function() {
  return this.name_;
};


/**
 * @return {Number}
 */
ProtoRpc.EnumValue.prototype.valueOf = function() {
  return this.number_;
};


/**
 * Wire Variants.
 * @type {ProtoRpc.Enum}
 */
ProtoRpc.Variant = new ProtoRpc.Enum({
  1: 'DOUBLE',
  2: 'FLOAT',
  3: 'INT64',
  4: 'UINT64',
  5: 'INT32',
  8: 'BOOL',
  9: 'STRING',
  11: 'MESSAGE',
  12: 'BYTES',
  13: 'UINT32',
  14: 'ENUM',
  17: 'SINT32',
  18: 'SINT64'
});



/**
 * @private
 * @constructor
 */
ProtoRpc.Definition_ = function() {

};



/**
 * @private
 * @constructor
 * @extends {ProtoRpc.Definition_}
 */
ProtoRpc.MessageDefinition_ = function(name) {
  goog.base(this);
  
  /**
   * @type {string}
   */
  this.name = null;

  /**
   * @type {Object.<Number, ProtoRpc.Field>}
   */
  this.fieldMap = {};
};
goog.inherits(ProtoRpc.MessageDefinition_, ProtoRpc.Definition_);


/**
 * Create a getter/setter proxy this message definition.
 * @param {ProtoRpc.Message_} instance Message instance.
 */
ProtoRpc.MessageDefinition_.prototype.createProxy = function(instance) {
  /** @constructor */
  var proxy = function() {};
  var proto = proxy.prototype;

  for (var number in this.fieldMap) {
    var field = this.fieldMap[number];
    if (field.isRepeated()) {
      var adder = ProtoRpc.Util.toCamelCase(field.getName(), 'add');
      proto[adder] = goog.bind(instance.addValue, instance, number);
    } else {
      var setter = ProtoRpc.Util.toCamelCase(field.getName(), 'set');
      proto[setter] = goog.bind(instance.setValue, instance, number);
    }
    var getter = ProtoRpc.Util.toCamelCase(field.getName(), 'get');
    proto[getter] = goog.bind(instance.getValue, instance, number);
  }
  return new proxy();
};

ProtoRpc.MessageDefinition_.prototype.getFieldByNumber = function(number) {
  return this.fieldMap[number];
};


/**
 * Message Factory.
 * @param {ProtoRpc.Message.Options} options Message options.
 * @export
 */
ProtoRpc.Message = function(name, options) {
  var def = new ProtoRpc.MessageDefinition_(name);

  for (var fieldName in options.fields || []) {
    var field = options.fields[fieldName];
    field.name_ = fieldName;
    def.fieldMap[field.getNumber()] = field;
  }

  /** @constructor */
  return function(opt_values) {
    var instance = new ProtoRpc.Message_(def);
    return def.createProxy(instance);
  };
};


/**
 * @typedef {{fields: Object.<string, ProtoRpc.Field>,
 *            enums: Object.<string, ProtoRpc.Enum>,
 *            messages: Object.<string, ProtoRpc.Message>}}
 */
ProtoRpc.Message.Options;



/**
 * @private
 * @constructor
 */
ProtoRpc.Message_ = function(definition) {
  /**
   * @type {Object.<Number, *>}
   * @private
   */
  this.values_ = {};

  /**
   * @type {ProtoRpc.MessageDefinition_}
   * @private
   */
  this.definition_ = definition;
};

ProtoRpc.Message_.prototype.getFieldByNumber_ = function(number) {
  return this.definition_.getFieldByNumber(number);
};

ProtoRpc.Message_.prototype.checkInitialized = function() {
  for (var number in this.fields_) {
    var field = this.fields_[number];

    if (field.isRequired()) {
      if (goog.isNull(this.values_[number])) {
        throw new ProtoRpc.ValidationError(
          'Message %s is missing required field %s', [
            this.getName(),
            field.getName()]);
      }
    }

    var value = this.values_[field.getNumber()];
    for (var j = 0; j < value.length; j++) {
      value[j].checkInitialized();
    }

    if (field.getVariant() == ProtoRpc.Variant.MESSAGE) {
      this.getValue(field.getNumber()).checkInitialized();
    }

  }
};


/**
 * @return {string} The name of the Message.
 */
ProtoRpc.Message_.prototype.getName = function() {
  return this.definition_.name;
};


/**
 * Get fields value by field's number.
 *
 * @param {number} number The field's number.
 * @return {*} The value found or undefined if no value.
 */
ProtoRpc.Message_.prototype.getValue = function(number, opt_idx) {
  var value = this.values_[number];
  if (value) {
    return value;
  }
  var field = this.getFieldByNumber_(number);
  return field.getDefaultValue();
};


/**
 * Set the value of a field on the message.
 * @param {Number} number The field's number.
 * @param {*} value The fields value.
 */
ProtoRpc.Message_.prototype.setValue = function(number, value) {
  this.values_[number] = value;
};


/**
 * Append an item to repeated list.
 * @param {number} number Field number.
 * @param {*} value Value to append.
 */
ProtoRpc.Message_.prototype.addValue = function(number, value) {
  throw Error('Not Implemented');
};


/**
 * @typedef {{repeated: (boolean|undefined),
 *            required: (boolean|undefined),
 *            defaultValue: (*|undefined)}}
 */
ProtoRpc.Field.Options;



/**
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options=} options Field options.
 * @constructor
 */
ProtoRpc.Field = function(number, options) {
  options = options || {
    repeated: false,
    required: false
  };


  // TODO: add more validation.

  /**
   * @type {Number}
   * @private
   */
  this.number_ = number;

  if (options.repeated && options.required) {
    // TODO: throw ProtoRpc.FieldDefinitionError(
    throw Error(
        'Cannot set both repeated and required');
  }

  /**
   * @type {boolean}
   * @private
   */
  this.required_ = options.required || false;

  /**
   * @type {boolean}
   * @private
   */
  this.repeated_ = options.repeated || false;

  /**
   * @type {boolean}
   * @private
   */
  this.optional_ = !this.required_;

  /**
   * @type {*}
   * @private
   */
  this.defaultValue_ = options.defaultValue || null;
};


/**
 * @type {string}
 * @private
 */
ProtoRpc.Field.prototype.name_ = null;


/**
 * Possble variants for this field definition.
 * @type {Array.<ProtoRpc.EnumValue>}
 * @private
 */
ProtoRpc.Field.prototype.variants_ = null;


/**
 * Default variant for this field definition.
 * @type {ProtoRpc.EnumValue}
 * @private
 */
ProtoRpc.Field.prototype.defaultVariant_ = null;


/**
 * The native type for this field definition.
 * @type {Object}
 * @private
 */
ProtoRpc.Field.prototype.nativeType_ = null;


/**
 * The Message definition that contains this Field definition.
 * @type {ProtoRpc.MessageDefinition_}
 * @private
 */
ProtoRpc.Field.prototype.messageDefinition_ = null;


/**
 * Get Message definiton that contains this field definition.
 * @return {ProtoRpc.MessageDefinition_} the Containing message definiton 
 *   for field, null if no message defines this field.
 */
ProtoRpc.Field.prototype.getMessageDefinition = function() {
  return this.messageDefiniton_;
};

ProtoRpc.Field.prototype.getNumber = function() {
  return this.number_;
};

ProtoRpc.Field.prototype.getName = function() {
  return this.name_;
};

ProtoRpc.Field.prototype.isRequired = function() {
  return this.required_;
};

ProtoRpc.Field.prototype.isRepeated = function() {
  return this.repeated_;
};

ProtoRpc.Field.prototype.getDefaultValue = function() {
  return this.defaultValue_;
};


/**
 * Validate single element of field.
 * @param {*} value a value to validate.
 */
ProtoRpc.Field.prototype.validateElement = function(value) {
  throw Error('Not implemented');
};



/**
 * Field definition for an Integer.
 *
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.IntegerField = function(number, options) {
  goog.base(this, number, options);
};
goog.inherits(ProtoRpc.IntegerField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.IntegerField.prototype.variants_ = [
  ProtoRpc.Variant.INT32,
  ProtoRpc.Variant.INT64,
  ProtoRpc.Variant.UINT32,
  ProtoRpc.Variant.UINT64,
  ProtoRpc.Variant.SINT32,
  ProtoRpc.Variant.SINT64
];


/** @inheritDoc */
ProtoRpc.IntegerField.prototype.defaultVariant_ = ProtoRpc.Variant.INT64;


/** @inheritDoc */
ProtoRpc.IntegerField.prototype.nativeType_ = Number;



/**
 * Field definition for an Float.
 *
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.FloatField = function(number, options) {
  goog.base(this, number, options);
};
goog.inherits(ProtoRpc.FloatField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.FloatField.prototype.variants_ = [
  ProtoRpc.Variant.FLOAT,
  ProtoRpc.Variant.DOUBLE
];


/** @inheritDoc */
ProtoRpc.FloatField.prototype.defaultVariant_ = ProtoRpc.Variant.DOUBLE;


/** @inheritDoc */
ProtoRpc.FloatField.prototype.nativeType_ = Number;



/**
 * Field definition for an Boolean.
 *
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.BooleanField = function(number, options) {
  goog.base(this, number, options);
};
goog.inherits(ProtoRpc.BooleanField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.BooleanField.prototype.variants_ = [
  ProtoRpc.Variant.BOOL
];


/** @inheritDoc */
ProtoRpc.BooleanField.prototype.defaultVariant_ = ProtoRpc.Variant.BOOL;


/** @inheritDoc */
ProtoRpc.BooleanField.prototype.nativeType_ = Boolean;



/**
 * Field definition for byte string values.
 *
 * Note: Javascript does not have a native bytestring format, so for
 *   now this will do nothing clever.
 *
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.BytesField = function(number, options) {
  goog.base(this, number, options);
};
goog.inherits(ProtoRpc.BytesField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.BytesField.prototype.variants_ = [
  ProtoRpc.Variant.BYTES
];


/** @inheritDoc */
ProtoRpc.BytesField.prototype.defaultVariant_ = ProtoRpc.Variant.BYTES;


/** @inheritDoc */
ProtoRpc.BytesField.prototype.nativeType_ = String;



/**
 * Field definition for string values.
 *
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.StringField = function(number, options) {
  goog.base(this, number, options);
};
goog.inherits(ProtoRpc.StringField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.StringField.prototype.variants_ = [
  ProtoRpc.Variant.STRING
];


/** @inheritDoc */
ProtoRpc.StringField.prototype.defaultVariant_ = ProtoRpc.Variant.STRING;


/** @inheritDoc */
ProtoRpc.StringField.prototype.nativeType_ = String;



/**
 * Field definition for sub-message values.
 *
 * @param {ProtoRpc.Message} message_type Message type for field.
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.MessageField = function(message_type, number, options) {
  goog.base(this, number, options);

  this.nativeType_ = message_type;
};
goog.inherits(ProtoRpc.MessageField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.MessageField.prototype.variants_ = [
  ProtoRpc.Variant.MESSAGE
];


/** @inheritDoc */
ProtoRpc.MessageField.prototype.defaultVariant_ = ProtoRpc.Variant.MESSAGE;



/**
 * Field definition for enum values.
 *
 * @param {ProtoRpc.Enum} enum_type Enumeration type.
 * @param {Number} number Field number.
 * @param {ProtoRpc.Field.Options} options Field's options.
 * @constructor
 * @extends {ProtoRpc.Field}
 * @export
 */
ProtoRpc.EnumField = function(enum_type, number, options) {
  goog.base(this, number, options);

  /** @inheritDoc */
  this.nativeType_ = enum_type;
};
goog.inherits(ProtoRpc.EnumField, ProtoRpc.Field);


/** @inheritDoc */
ProtoRpc.EnumField.prototype.variants_ = [
  ProtoRpc.Variant.ENUM
];


/** @inheritDoc */
ProtoRpc.EnumField.prototype.defaultVariant_ = ProtoRpc.Variant.ENUM;
