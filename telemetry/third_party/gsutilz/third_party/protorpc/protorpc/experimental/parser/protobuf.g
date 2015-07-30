/* !/usr/bin/env python
 *
 * Copyright 2011 Google Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

parser grammar protobuf;

scalar_value
    :   STRING
    |   FLOAT
    |   INT
    |   BOOL
    ;

id
    :   ID
    |   PACKAGE
    |   SERVICE
    |   MESSAGE
    |   ENUM
    |   DATA_TYPE
    |   EXTENSIONS
	;

user_option_id
    :   '(' name_root='.'? qualified_name ')'
          -> ^(USER_OPTION_ID $name_root? qualified_name)
    ;

option_id
	:   (id | user_option_id) ('.'! (id | user_option_id))*
	;

option
	:   option_id '=' (scalar_value | id)
          -> ^(OPTION ^(OPTION_ID option_id) scalar_value? id?)
	;

decl_options
    :   '[' option (',' option)* ']'
          -> ^(OPTIONS option*)
    ;

qualified_name
	:   id ('.'! id)*
	;

field_decl
	:   qualified_name id '=' INT decl_options? ';'
          -> ^(FIELD_TYPE qualified_name) id INT decl_options?
	|   GROUP id '=' INT '{' message_def '}'
          -> ^(FIELD_TYPE GROUP) id INT ^(GROUP_MESSAGE message_def)
	;

field
	:   LABEL field_decl
          -> ^(FIELD LABEL field_decl)
	;

enum_decl
	:   id '=' INT decl_options? ';'
          -> ^(ENUM_DECL id INT decl_options?)
	;

enum_def
	:   ENUM id '{' (def_option | enum_decl | ';')* '}'
          -> ^(ENUM id
              ^(OPTIONS def_option*)
              ^(ENUM_DECLS enum_decl*))
	;

extensions
	:	EXTENSIONS start=INT (TO (end=INT | end=MAX))? ';' -> ^(EXTENSION_RANGE $start $end)
	;

message_def
    :   ( field
        | enum_def
        | message
        | extension
        | extensions
        | def_option
        | ';'
        )* ->
        ^(FIELDS field*)
        ^(MESSAGES message*)
        ^(ENUMS enum_def*)
        ^(EXTENSIONS extensions*)
        ^(OPTIONS def_option*)
    ;

message
	:   MESSAGE^ id '{'! message_def '}'!
	;

method_options
	:   '{'! (def_option | ';'!)+ '}'!
	;

method_def
	:   RPC id '(' qualified_name ')'
        RETURNS '(' qualified_name ')' (method_options | ';')
	;

service_defs
	:   (def_option	 | method_def  | ';')+
	;

service
	:   SERVICE id '{' service_defs? '}'
	;

extension
	:   EXTEND qualified_name '{' message_def '}'
	;

import_line
	:   IMPORT! STRING ';'!
	;

package_decl
	:   PACKAGE^ qualified_name ';'!
	;

def_option
	:   OPTION option ';' -> option
	;

proto_file
	:   ( package_decl
        | import_line
        | message
        | enum_def
        | service
        | extension
        | def_option
        | ';'
        )*
        -> ^(PROTO_FILE package_decl*
            ^(IMPORTS import_line*)
            ^(MESSAGES message*)
            ^(ENUMS enum_def*)
            ^(SERVICES service*)
            ^(EXTENSIONS extension*)
            ^(OPTIONS def_option*)
        )
	;
