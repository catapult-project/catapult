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
lexer grammar protobuf_lexer;

tokens {
    // Imaginary tree nodes.
    ENUMS;
    ENUM_DECL;
    ENUM_DECLS;
    EXTENSION_RANGE;
    FIELD;
    FIELDS;
    FIELD_TYPE;
    GROUP_MESSAGE;
    IMPORTS;
    MESSAGES;
    NAME_ROOT;
    OPTIONS;
    OPTION_ID;
    PROTO_FILE;
    SERVICES;
    USER_OPTION_ID;
}

// Basic keyword tokens.
ENUM : 'enum';
MESSAGE : 'message';
IMPORT : 'import';
OPTION : 'option';
PACKAGE : 'package';
RPC : 'rpc';
SERVICE : 'service';
RETURNS : 'returns';
EXTEND : 'extend';
EXTENSIONS : 'extensions';
TO : 'to';
GROUP : 'group';
MAX : 'max';

COMMENT
    :   '//' ~('\n'|'\r')* '\r'? '\n' {$channel=HIDDEN;}
    |   '/*' ( options {greedy=false;} : . )* '*/' {$channel=HIDDEN;}
    ;

WS 
    :   ( ' '
        | '\t'
        | '\r'
        | '\n'
        ) {$channel=HIDDEN;}
    ;

DATA_TYPE
	:   'double'
	|   'float'
	|   'int32'
	|   'int64'
	|   'uint32'
	|   'uint64'
	|   'sint32'
	|   'sint64'
	|   'fixed32'
	|   'fixed64'
	|   'sfixed32'
	|   'sfixed64'
	|   'bool'
	|   'string'
	|   'bytes'
	;

LABEL
	:   'required'
	|   'optional'
	|   'repeated'
	;
	
BOOL
	:   'true'
	|   'false'
	;

ID
    :   ('a'..'z'|'A'..'Z'|'_') ('a'..'z'|'A'..'Z'|'0'..'9'|'_')*
    ;

INT
	:   '-'? ('0'..'9'+ | '0x' ('a'..'f'|'A'..'F'|'0'..'9')+ | 'inf')
	|   'nan'
	;
	
FLOAT
    :   '-'? ('0'..'9')+ '.' ('0'..'9')* EXPONENT?
    |   '-'? '.' ('0'..'9')+ EXPONENT?
    |   '-'? ('0'..'9')+ EXPONENT
    ;

STRING
    :   '"' ( STRING_INNARDS )* '"';

fragment
STRING_INNARDS
	:   ESC_SEQ
	|   ~('\\'|'"')
	;

fragment
EXPONENT
    :   ('e'|'E') ('+'|'-')? ('0'..'9')+ 
    ;

fragment
HEX_DIGIT
    :   ('0'..'9'|'a'..'f'|'A'..'F')
    ;

fragment
ESC_SEQ 
    :   '\\' ('a'|'b'|'t'|'n'|'f'|'r'|'v'|'\"'|'\''|'\\')
    |   UNICODE_ESC
    |   OCTAL_ESC
    |   HEX_ESC
    ;

fragment
OCTAL_ESC
    :   '\\' ('0'..'3') ('0'..'7') ('0'..'7')
    |   '\\' ('0'..'7') ('0'..'7')
    |   '\\' ('0'..'7')
    ;

fragment
HEX_ESC
	:   '\\x' HEX_DIGIT HEX_DIGIT
	;

fragment
UNICODE_ESC
	:   '\\' 'u' HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT
	;
