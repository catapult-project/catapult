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
 * @fileoverview Javascript client implementation for ProtoRpc services.
 * @author joetyson@gmail.com (Joe Tyson)
 */

goog.provide('ProtoRpc.RPC');
goog.provide('ProtoRpc.RPC.State');
goog.provide('ProtoRpc.ServiceStub');

goog.require('ProtoRpc.EnumDescriptor');
goog.require('ProtoRpc.Message');

goog.require('goog.json');
goog.require('goog.net.XmlHttp');


/**
 * Represents a client side RPC.
 *
 * @export
 * @param {string} service_path Relative URI where service lives.
 * @param {string} method_name Name of method being invoked.
 * @param {Object} request The request.
 * @param {Function} success Function to call when RPC completes.
 * @param {Function=} error Function to call when RPC has an error.
 * @constructor
 */
ProtoRpc.RPC = function(service_path, method_name, request, success, error) {
  this.successCallback_ = success;
  this.errorCallback_ = error || null;

  this.request_ = request;

  var xhr = new goog.net.XmlHttp();

  /**
   * Try to open an XMLHttpRequest. If an error occurs, it's generally
   *  due to a permission issue.
   * @preserveTry
   */
  try {
    xhr.open('POST', service_path + '.' + method_name, true);
  } catch (err) {
    this.setState_(ProtoRpc.RPC.State.REQUEST_ERROR);
  }

  xhr.setRequestHeader('Content-Type', ProtoRpc.RPC.CONTENT_TYPE);

  /**
   * Send request or catch error.
   * @preserveTry
   */
  try {
    xhr.onreadystatechange = goog.bind(this.onReadyStateChange_, this);
    // TODO: What if serialization fails?
    xhr.send(goog.json.serialize(request));
  } catch (err) {
    this.setState_(ProtoRpc.RPC.State.REQUEST_ERROR);
  }

  this.xhr_ = xhr;
};


/**
 * Rpc States.
 * @enum {string}
 */
ProtoRpc.RPC.State = {
  OK: 'OK',
  RUNNING: 'RUNNING',
  REQUEST_ERROR: 'REQUEST_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
  APPLICATION_ERROR: 'APPLICATION_ERROR'
};


/**
 * Content-Type to use when making remote calls.
 * @const
 */
ProtoRpc.RPC.CONTENT_TYPE = 'application/json;charset=utf-8';


/**
 * Reference to an XMLHttpRequest object being used for RPC.
 * @type {XMLHttpRequest}
 * @private
 */
ProtoRpc.RPC.prototype.xhr_ = null;


/**
 * Functon to call when RPC completes successfully.
 * @type {Function}
 * @private
 */
ProtoRpc.RPC.prototype.successCallback_ = null;


/**
 * Function to call when an error happens.
 * @type {Function}
 * @private
 */
ProtoRpc.RPC.prototype.errorCallback_ = null;


/**
 * The Rpc's request message.
 * @type {Object}
 * @private
 */
ProtoRpc.RPC.prototype.request_ = null;


/**
 * The Rpc's response from the server.
 * @type {Object}
 * @private
 */
ProtoRpc.RPC.prototype.response_ = null;


/**
 * The current state of the Rpc.
 * @type {ProtoRpc.RPC.State}
 * @private
 */
ProtoRpc.RPC.prototype.state_ = ProtoRpc.RPC.State.RUNNING;


/**
 * The Rpc's Error Message, if error.
 * @type {string}
 * @private
 */
ProtoRpc.RPC.prototype.errorMessage_ = '';


/**
 * The Rpc's Error Name, if error.
 * @type {string}
 * @private
 */
ProtoRpc.RPC.prototype.errorName_ = '';


/**
 * Method invoked when RPC's xhr readyState is changed.
 * @private
 */
ProtoRpc.RPC.prototype.onReadyStateChange_ = function() {
  if (this.state_ != ProtoRpc.RPC.State.RUNNING) {
    return;
  }

  if (this.xhr_.readyState != goog.net.XmlHttp.ReadyState.COMPLETE) {
    return;
  }

  var status = this.xhr_.status;
  var statusText = this.xhr_.statusText;
  var content = this.xhr_.responseText;

  if (status >= 400) {
    /**
     * Try to parse RpcStatus from message.
     * @preserveTry
     */
    try {
      var rpcStatus = goog.json.parse(content);
      this.errorName_ = rpcStatus['error_name'] || null;
      this.errorMessage_ = rpcStatus['error_message'] || null;
      // TODO(joe): More robust RpcStatus handling...
      this.setState_(rpcStatus['state']);
    } catch (err) {
      this.errorName_ = 'Unknown Error.';
      this.setState_(ProtoRpc.RPC.State.REQUEST_ERROR);
    }
    return;
  }

  // TODO: validation
  // TODO: What if parsing fails?
  this.response_ = goog.json.parse(content);
  this.setState_(ProtoRpc.RPC.State.OK);
};


/**
 * Set the Rpc's state.
 * @param {ProtoRpc.RPC.State} state The Rpc State to set.
 * @private
 */
ProtoRpc.RPC.prototype.setState_ = function(state) {
  // TODO: Bitmask "allowed" transitions?
  this.state_ = state;
  if (state != ProtoRpc.RPC.State.OK) {
    this.callErrorHandler_();
    return;
  }
  this.callSuccessHandler_();
};


/** @private */
ProtoRpc.RPC.prototype.callErrorHandler_ = function() {
  // TODO: optional context/this?
  this.errorCallback_(this);
};


/** @private */
ProtoRpc.RPC.prototype.callSuccessHandler_ = function() {
  // TODO: optional context/this?
  this.successCallback_(this);
};


/**
 * Get the response from a completed RPC.
 * Throws {@code ProtoRpc.RpcError} if an error occured while
 *  running the RPC.
 * @return {Object} The response message from RPC.
 * @export
 */
ProtoRpc.RPC.prototype.getResponse = function() {
  if (this.state_ != ProtoRpc.RPC.State.OK) {
    throw this.getError();
  }
  return this.response_;
};


/**
 * Get the error from a failed RPC. This may be any of the appropriate
 * error types which can be associated with an RPC.
 * @export
 * @return {Error} The Error associated with RPC.
 */
ProtoRpc.RPC.prototype.getError = function() {
  // TODO: if not in error, do something.
  var error = new Error(this.errorName_);
  error.message = this.errorMessage_;
  error.type = this.state_;
  return error;
};


/**
 * Represents a Service Stub for a given service name, path, and set
 * of methods.
 * @param {string} path The path where the service accepts method calls.
 * @param {Array.<ProtoRpc.MethodDescriptor>} methods An array of method
 *     descriptors.
 * @constructor
 */
ProtoRpc.ServiceStub = function(path, methods) {
  this.path_ = path;
  var l = methods.length;
  for (var i = 0; i < l; i++) {
    this.addMethod_(methods[i]);
  }
};


/**
 * Add a method to the service.
 * @param {ProtoRpc.MethodDescriptor} method_descriptor The method descriptor.
 * @private
 */
ProtoRpc.ServiceStub.prototype.addMethod_ = function(method_descriptor) {
  var method_name = method_descriptor.name;
  this[method_name] = this.makeMethod_(method_name, this.path_);
};

/**
 * Helper to make methods.
 * @param {string} name Method name.
 * @param {string} path Service path.
 * @return {function({request: Object,
 *                    success: function(ProtoRpc.RPC),
 *                    error: function(ProtoRpc.RPC)})}
 * @private
 */
ProtoRpc.ServiceStub.prototype.makeMethod_ = function(name, path) {
  return function(kwargs) {
    var request = kwargs['request'] || {};
    var success = kwargs['success'];
    var error = kwargs['error'] || null;

    if (!goog.isFunction(success)) {
      throw Error('Success callback needs to be a function!');
    }

    if (error && !goog.isFunction(error)) {
      throw Error('Error callback needs to be a function!');
    }

    return new ProtoRpc.RPC(path, name, request, success, error);
  };
};

/**
 * Protojson Specific Serializer.
 * @constructor
 */
ProtoRpc.Serializer = function() {
  // TODO: Have option for using key's as field number vs. field name.
};

ProtoRpc.Serializer.prototype.serialize = function(message) {
  var descriptor = message.getDescriptor();
  var fields = descriptor['fields'];

  var obj = {};

  for (var i = 0; i < fields.length; i++) {
    var field = fields[i];

    if (message.has(field)) {
      if (field['label'] == 'REPEATED') {
        var arr = [];
        obj[field.toString()] = arr;

        var repeatedValues = message.get(field);
        for (var j = 0; j < repeatedValues.length; j++) {
          arr.push(this.serialize_(field, repeatedValues[j]));
        }
      } else {
        obj[field.toString()] = message.get(field);
      }
    } else {
      // Default values
    }
  }
};


/**
 * @param {ProtoRpc.FieldDescriptor} field Field Descriptor of value.
 * @param {*} value Field's unserialized value.
 */
ProtoRpc.Serializer.prototype.serialize_ = function(field, value) {
  switch (field['variant']) {
    case ProtoRpc.Variant.MESSAGE:
      return this.serializeMessage_(value);
      break;
    case ProtoRpc.Variant.ENUM:
      return this.serializeEnum_(value);
      break;
    default:
      return value;
  }
};