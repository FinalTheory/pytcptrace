#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Author: 黄龑(huangyan13@baidu.com)
# Created Time: 2016/01/14 14:54
# File Name: http_parser.py
# Description: 
#
# Copyright (c) 2015 Baidu.com, Inc. All Rights Reserved
#

import os
import re
import sys
import unittest
import urlparse
import zlib

from util import (IOrderedDict, unquote, MAXSIZE)

METHOD_RE = re.compile("[A-Z0-9$-_.]{3,20}")
VERSION_RE = re.compile("HTTP/(\d+).(\d+)")
STATUS_RE = re.compile("(\d{3})\s*(\w*)")
HEADER_RE = re.compile("[\x00-\x1F\x7F()<>@,;:\[\]={} \t\\\\\"]")

# errors
BAD_FIRST_LINE = -1
INVALID_HEADER = -2
INVALID_BODY = -3
INVALID_CHUNK = -4
INVALID_TRAILER = -5


class InvalidRequestLine(Exception):
    """ error raised when first line is invalid """


class InvalidHeader(Exception):
    """ error raised on invalid header """


class InvalidChunkSize(Exception):
    """ error raised when we parse an invalid chunk size """


class HttpParser(object):
    def __init__(self, kind=2, decompress=False):
        self.kind = kind
        self.decompress = decompress

        # errors vars
        self.errno = None
        self.errstr = ""

        # protected variables

        # containers
        self._buf = ""
        self._body = ""
        self._environ = dict()
        self._headers = IOrderedDict()

        # variables
        self._version = None
        self._method = None
        self._status_code = None
        self._status = None
        self._reason = None
        self._url = None
        self._path = None
        self._query_string = None
        self._fragment = None

        # flags
        self._chunked = False
        self._have_trailer = False
        self._have_body = False
        self.nb_parsed = 0
        self._clen = 0

        # private events
        self.__on_firstline = False
        self.__on_headers_complete = False
        self.__on_message_begin = False
        self.__on_message_complete = False

        self.__decompress_obj = None
        self.__decompress_first_try = True

    def get_version(self):
        return self._version

    def get_method(self):
        return self._method

    def get_status_code(self):
        return self._status_code

    def get_reason(self):
        return self._reason

    def get_url(self):
        return self._url

    def get_path(self):
        return self._path

    def get_query_string(self):
        return self._query_string

    def get_fragment(self):
        return self._fragment

    def get_headers(self):
        return self._headers

    def get_wsgi_environ(self):
        if not self.__on_headers_complete:
            return None

        environ = self._environ.copy()
        # clean special keys
        for key in ("CONTENT_LENGTH", "CONTENT_TYPE", "SCRIPT_NAME"):
            hkey = "HTTP_%s" % key
            if hkey in environ:
                environ[key] = environ.pop(hkey)

        script_name = environ.get('SCRIPT_NAME',
                                  os.environ.get("SCRIPT_NAME", ""))
        if script_name:
            path_info = self._path.split(script_name, 1)[1]
            environ.update({
                "PATH_INFO": unquote(path_info),
                "SCRIPT_NAME": script_name})
        else:
            environ['SCRIPT_NAME'] = ""

        if environ.get('HTTP_X_FORWARDED_PROTOCOL', '').lower() == "ssl":
            environ['wsgi.url_scheme'] = "https"
        elif environ.get('HTTP_X_FORWARDED_SSL', '').lower() == "on":
            environ['wsgi.url_scheme'] = "https"
        else:
            environ['wsgi.url_scheme'] = "http"

        return environ

    def get_body(self):
        """ return last chunk of the parsed body"""
        return self._body

    def is_upgrade(self):
        """ Do we get upgrade header in the request. Useful for
        websockets """
        return self._headers.get('connection', "").lower() == "upgrade"

    def is_headers_complete(self):
        """ return True if all headers have been parsed. """
        return self.__on_headers_complete

    def is_partial_body(self):
        """ return True if a chunk of body have been parsed """
        return self._have_body

    def is_message_begin(self):
        """ return True if the parsing start """
        return self.__on_message_begin

    def is_message_complete(self):
        """ return True if the parsing is done (we get EOF) """
        return self.__on_message_complete

    def is_chunked(self):
        """ return True if Transfer-Encoding header value is chunked"""
        return self._chunked

    def should_keep_alive(self):
        """ return True if the connection should be kept alive
        """
        hconn = self._headers.get('connection', "").lower()
        if hconn == "close":
            return False
        elif hconn == "keep-alive":
            return True
        return self._version == (1, 1)

    def execute(self, data):
        # end of body can be passed manually by putting a length of 0

        if len(data) == 0:
            self.__on_message_complete = True
            return 0

        # start to parse
        while True:
            if not self.__on_firstline:
                # try to extract first line
                idx = data.find("\r\n")
                if idx < 0:
                    self.errno = BAD_FIRST_LINE
                    self.errstr = "Invalid HTTP request/status line"
                    return BAD_FIRST_LINE
                else:
                    self.__on_firstline = True
                    first_line, self._buf = data[:idx], data[idx + 2:]
                    self.nb_parsed += idx + 2
                    data = ""
                    if not self._parse_firstline(first_line):
                        return BAD_FIRST_LINE
            elif not self.__on_headers_complete:
                try:
                    to_parse = self._buf
                    ret = self._parse_headers(to_parse)
                    self.__on_headers_complete = True
                    self.nb_parsed += len(to_parse) - ret
                except InvalidHeader as e:
                    self.errno = INVALID_HEADER
                    self.errstr = str(e)
                    return INVALID_HEADER
            elif not self.__on_message_complete:
                if not self.__on_message_begin:
                    self.__on_message_begin = True

                to_parse = self._buf
                ret = self._parse_body(to_parse)
                # this is a normal request
                if ret is None:
                    self.__on_message_complete = True
                elif ret == 0:
                    # finished parsing
                    self.__on_message_complete = True
                elif ret < 0:
                    # on error
                    return ret
                elif ret > 0:
                    # parsed a trunk, do nothing
                    pass
            else:
                return self.nb_parsed

    def _parse_firstline(self, line):
        try:
            if self.kind == 2:  # auto detect
                try:
                    self._parse_request_line(line)
                except InvalidRequestLine:
                    self._parse_response_line(line)
            elif self.kind == 1:
                self._parse_response_line(line)
            elif self.kind == 0:
                self._parse_request_line(line)
        except InvalidRequestLine as e:
            self.errno = BAD_FIRST_LINE
            self.errstr = str(e)
            return False
        return True

    def _parse_response_line(self, line):
        bits = line.split(None, 1)
        if len(bits) != 2:
            raise InvalidRequestLine(line)

        # version
        matchv = VERSION_RE.match(bits[0])
        if matchv is None:
            raise InvalidRequestLine("Invalid HTTP version: %s" % bits[0])
        self._version = (int(matchv.group(1)), int(matchv.group(2)))

        # status
        matchs = STATUS_RE.match(bits[1])
        if matchs is None:
            raise InvalidRequestLine("Invalid status %" % bits[1])

        self._status = bits[1]
        self._status_code = int(matchs.group(1))
        self._reason = matchs.group(2)

    def _parse_request_line(self, line):
        bits = line.split(None, 2)
        if len(bits) != 3:
            raise InvalidRequestLine(line)

        # Method
        if not METHOD_RE.match(bits[0]):
            raise InvalidRequestLine("invalid Method: %s" % bits[0])
        self._method = bits[0].upper()

        # URI
        self._url = bits[1]
        parts = urlparse.urlsplit(bits[1])
        self._path = parts.path or ""
        self._query_string = parts.query or ""
        self._fragment = parts.fragment or ""

        # Version
        match = VERSION_RE.match(bits[2])
        if match is None:
            raise InvalidRequestLine("Invalid HTTP version: %s" % bits[2])
        self._version = (int(match.group(1)), int(match.group(2)))

        # update environ
        if hasattr(self, 'environ'):
            self._environ.update({
                "PATH_INFO": self._path,
                "QUERY_STRING": self._query_string,
                "RAW_URI": self._url,
                "REQUEST_METHOD": self._method,
                "SERVER_PROTOCOL": bits[2]})

    def _parse_headers(self, data):
        idx = data.find("\r\n\r\n")
        if idx < 0:  # we don't have all headers
            raise InvalidHeader('Headers not complete')

        # Split lines on \r\n keeping the \r\n on each line
        lines = [line + "\r\n" for line in
                 data[:idx].split("\r\n")]

        # Parse headers into key/value pairs paying attention
        # to continuation lines.
        while len(lines):
            # Parse initial header name : value pair.
            curr = lines.pop(0)
            if curr.find(":") < 0:
                raise InvalidHeader("invalid line %s" % curr.strip())
            name, value = curr.split(":", 1)
            name = name.rstrip(" \t").upper()
            if HEADER_RE.search(name):
                raise InvalidHeader("invalid header name %s" % name)

            if value.endswith("\r\n"):
                value = value[:-2]

            name, value = name.strip(), [value.lstrip()]

            # Consume value continuation lines
            while len(lines) and lines[0].startswith((" ", "\t")):
                curr = lines.pop(0)
                if curr.endswith("\r\n"):
                    curr = curr[:-2]
                value.append(curr)
            value = ''.join(value).rstrip()

            # multiple headers
            if name in self._headers:
                value = "%s, %s" % (self._headers[name], value)

            # store new header value
            self._headers[name] = value

            # update WSGI environ
            key = 'HTTP_%s' % name.upper().replace('-', '_')
            self._environ[key] = value

        # detect now if body is sent by chunks.
        clen = self._headers.get('content-length')
        te = self._headers.get('transfer-encoding', '').lower()
        if self._headers.get('Trailer'):
            self._have_trailer = True

        if clen is not None:
            try:
                self._clen = int(clen)
            except ValueError:
                pass
        else:
            self._chunked = (te == 'chunked')
            if not self._chunked:
                self._clen_rest = MAXSIZE

        # detect encoding and set decompress object
        encoding = self._headers.get('content-encoding')
        if self.decompress:
            if encoding == "gzip":
                self.__decompress_obj = zlib.decompressobj(16 + zlib.MAX_WBITS)
                self.__decompress_first_try = False
            elif encoding == "deflate":
                self.__decompress_obj = zlib.decompressobj()

        rest = data[idx + 4:]
        self._buf = rest
        return len(rest)

    def _parse_body(self, data):
        if not self._chunked:
            complete = True
            self.__on_message_complete = True
            # if we have enough data
            if len(data) < self._clen:
                complete = False
                self._clen = len(data)
                self.errno = INVALID_BODY
                self.errstr = "HTTP body incomplete"

            body_part = data[:self._clen]
            self.nb_parsed += len(body_part)

            # maybe decompress
            if complete and body_part and self.__decompress_obj is not None:
                if not self.__decompress_first_try:
                    body_part = self.__decompress_obj.decompress(body_part)
                else:
                    try:
                        body_part = self.__decompress_obj.decompress(body_part)
                    except zlib.error:
                        self.__decompress_obj.decompressobj = zlib.decompressobj(-zlib.MAX_WBITS)
                        body_part = self.__decompress_obj.decompress(body_part)
                    self.__decompress_first_try = False

            if body_part:
                self._have_body = True
                self._body = body_part

            # we parsed enough content for this response
            # so just ignore the other data
            self._buf = ""

            return
        else:
            try:
                size, rest = self._parse_chunk_size(data)
            except InvalidChunkSize as e:
                self.errno = INVALID_CHUNK
                self.errstr = "invalid chunk size [%s]" % str(e)
                return INVALID_CHUNK

            if size == 0:
                def error_trailer():
                        self.errno = INVALID_TRAILER
                        self.errstr = "Invalid trailer"
                        return INVALID_TRAILER
                # if this response have trailer
                if self._have_trailer and rest[:2] != "\r\n":
                    idx = rest.find("\r\n\r\n")
                    if idx != -1:
                        try:
                            self._parse_headers(rest[:idx + 4])
                            self.nb_parsed += idx + 4
                            return 0
                        except InvalidHeader:
                            return error_trailer()
                    else:
                        return error_trailer()
                if rest[:2] == '\r\n':
                    self.nb_parsed += 2
                    self._buf = ""
                    return 0
                else:
                    return error_trailer()

            if size is None or len(rest) < size:
                self.errno = INVALID_CHUNK
                self.errstr = "Invalid trunk size"
                return INVALID_CHUNK

            body_part, rest = rest[:size], rest[size:]
            if len(rest) < 2:
                self.errno = INVALID_CHUNK
                self.errstr = "chunk missing terminator [%s]" % data
                return INVALID_CHUNK

            self.nb_parsed += len(body_part) + 2

            # maybe decompress
            if self.__decompress_obj is not None:
                body_part = self.__decompress_obj.decompress(body_part)

            self._have_body = True
            self._body += body_part
            self._buf = rest[2:]
            return len(body_part)

    def _parse_chunk_size(self, data):
        idx = data.find("\r\n")
        if idx < 0:
            return None, None
        line, rest_chunk = data[:idx], data[idx + 2:]
        chunk_size = line.split(";", 1)[0].strip()
        try:
            chunk_size = int(chunk_size, 16)
        except ValueError:
            raise InvalidChunkSize(chunk_size)

        self.nb_parsed += idx + 2
        return chunk_size, rest_chunk


class TestHttpParser(unittest.TestCase):
    def test_normal_request(self):
        data = ('GET /anxun/pic/item/0824ab18972bd4073f3636e97c899e510fb30934.jpg HTTP/1.1\r\n'
                'Host: imgsrc.baidu.com\r\n'
                'Connection: Keep-Alive\r\n'
                'User-Agent: android-async-http/1.0\r\n'
                '\r\n')
        r = HttpParser()
        self.assertEqual(r.execute(data), len(data))
        r = HttpParser()
        self.assertEqual(r.execute(data * 2), len(data))

    def test_normal_response(self):
        data = ('HTTP/1.1 200 OK\r\n'
                'Set-Cookie: BAIDUID=0A6D64CF265D82C7BC893B133581312A:FG=1; '
                'max-age=31536000; expires=Wed, 11-Jan-17 07:36:52 GMT; '
                'domain=.baidu.com; path=/; version=1\r\n'
                'P3P: CP=" OTI DSP COR IVA OUR IND COM "\r\n'
                'Content-Type: image/jpeg\r\n'
                'Cache-Control: max-age=31536000\r\n'
                'Error-Message: OK\r\n'
                'ETag: "4936705892209953421"\r\n'
                'Expires: Wed, 11 Jan 2017 07:36:52 GMT\r\n'
                'Last-Modified: Mon, 04 Jan 2016 09:22:55 GMT\r\n'
                'Content-Length: 10\r\n'
                'Connection: close\r\n'
                'Date: Tue, 12 Jan 2016 07:36:52 GMT\r\n'
                'Server: apache\r\n'
                '\r\n'
                '0123456789')
        r = HttpParser()
        self.assertEqual(r.execute(data), len(data))
        r = HttpParser()
        self.assertEqual(r.execute(data * 2), len(data))
        self.assertEqual(r.get_body(), '0123456789')

    def test_empty_response(self):
        data = ('HTTP/1.1 200 OK\r\n'
                'Set-Cookie: BAIDUID=0A6D64CF265D82C7BC893B133581312A:FG=1; '
                'max-age=31536000; expires=Wed, 11-Jan-17 07:36:52 GMT; '
                'domain=.baidu.com; path=/; version=1\r\n'
                'P3P: CP=" OTI DSP COR IVA OUR IND COM "\r\n'
                'Content-Type: image/jpeg\r\n'
                'Cache-Control: max-age=31536000\r\n'
                'Error-Message: OK\r\n'
                'ETag: "4936705892209953421"\r\n'
                'Expires: Wed, 11 Jan 2017 07:36:52 GMT\r\n'
                'Last-Modified: Mon, 04 Jan 2016 09:22:55 GMT\r\n'
                'Connection: close\r\n'
                'Date: Tue, 12 Jan 2016 07:36:52 GMT\r\n'
                'Server: apache\r\n'
                '\r\n'
                '0123456789')
        r = HttpParser()
        self.assertEqual(r.execute(data), len(data) - 10)
        r = HttpParser()
        self.assertEqual(r.execute(data * 2), len(data) - 10)
        self.assertEqual(r.get_body(), '')

    def test_invalid_response(self):
        data = ('HTTP/1.1 200 OK\r\n'
                'Set-Cookie: BAIDUID=0A6D64CF265D82C7BC893B133581312A:FG=1; '
                'max-age=31536000; expires=Wed, 11-Jan-17 07:36:52 GMT; '
                'domain=.baidu.com; path=/; version=1\r\n'
                'P3P: CP=" OTI DSP COR IVA OUR IND COM "\r\n'
                'Content-Type: image/jpeg\r\n'
                'Cache-Control: max-age=31536000\r\n'
                'Error-Message: OK\r\n'
                'ETag: "4936705892209953421"\r\n'
                'Expires: Wed, 11 Jan 2017 07:36:52 GMT\r\n'
                'Last-Modified: Mon, 04 Jan 2016 09:22:55 GMT\r\n'
                'Content-Length: 10\r\n'
                'Connection: close\r\n'
                'Date: Tue, 12 Jan 2016 07:36:52 GMT\r\n'
                'Server: apache\r\n'
                '\r\n'
                '012345678')
        r = HttpParser()
        self.assertEqual(r.execute(data), len(data))
        r = HttpParser()
        self.assertEqual(r.execute(data * 2), len(data) + 1)


    def test_trunk_encoding(self):
        l = 1000
        data = ('HTTP/1.1 200 OK\r\n'
                'Transfer-Encoding: chunked\r\n'
                '\r\n'
                'b\r\n'
                '01234567890\r\n'
                '5\r\n'
                '12345\r\n'
                '0\r\n'
                '\r\n') + 'a' * l
        r = HttpParser()
        self.assertEqual(r.execute(data), len(data) - l)
        self.assertEqual(r.get_body(), '0123456789012345')

    def test_trunk_trailer(self):
        r = HttpParser()
        l = 1000
        data = ('HTTP/1.1 200 OK\r\n'
                'Transfer-Encoding: chunked\r\n'
                'Trailer: Expires\r\n'
                '\r\n'
                'b\r\n'
                '01234567890\r\n'
                '5\r\n'
                '12345\r\n'
                '0\r\n'
                'Expires: fuck\r\n'
                'This: is shit\r\n'
                '\r\n') + 'a' * l
        self.assertEqual(r.execute(data), len(data) - l)
        self.assertEqual(r.get_headers()['Expires'], 'fuck')
        self.assertEqual(r.get_headers()['This'], 'is shit')
        self.assertEqual(r.get_body(), '0123456789012345')


if __name__ == '__main__':
    unittest.main()
