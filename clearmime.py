#!/usr/bin/python

# Copyright 2008 Lenny Domnitser <http://domnit.org/>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

__all__ = 'clarify',
__author__ = 'Lenny Domnitser'
__version__ = '0.1'

import email
import re

TEMPLATE = '''-----BEGIN PGP SIGNED MESSAGE-----
Hash: %(hashname)s
NotDashEscaped: You need GnuPG to verify this message

%(text)s%(sig)s'''


def _clarify(message, messagetext):
    if message.get_content_type() == 'multipart/signed':
        if message.get_param('protocol') == 'application/pgp-signature':
            hashname = message.get_param('micalg').upper()
            assert hashname.startswith('PGP-')
            hashname = hashname.replace('PGP-', '', 1)
            textmess, sigmess = message.get_payload()
            assert sigmess.get_content_type() == 'application/pgp-signature'
            #text = textmess.as_string() - not byte-for-byte accurate
            text = messagetext.split('\n--%s\n' % message.get_boundary(), 2)[1]
            sig = sigmess.get_payload()
            assert isinstance(sig, str)
            # Setting content-type to application/octet instead of text/plain
            # to maintain CRLF endings. Using replace_header instead of
            # set_type because replace_header clears parameters.
            message.replace_header('Content-Type', 'application/octet')
            clearsign = TEMPLATE % locals()
            clearsign = clearsign.replace(
                '\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
            message.set_payload(clearsign)
    elif message.is_multipart():
        for message in message.get_payload():
            _clarify(message, messagetext)


def clarify(messagetext):
    '''given a string containing a MIME message, returns a string
    where PGP/MIME messages are replaced with clearsigned messages.'''

    message = email.message_from_string(messagetext)
    _clarify(message, messagetext)
    return message.as_string()


if __name__ == '__main__':
    import sys
    sys.stdout.write(clarify(sys.stdin.read()))
