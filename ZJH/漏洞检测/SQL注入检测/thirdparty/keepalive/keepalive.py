#!/usr/bin/env python2
# -*- coding: utf-8 -*-

#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, write to the 
#      Free Software Foundation, Inc., 
#      59 Temple Place, Suite 330, 
#      Boston, MA  02111-1307  USA

# This file was part of urlgrabber, a high-level cross-protocol url-grabber
# Copyright 2002-2004 Michael D. Stenner, Ryan Tomayko
# Copyright 2015 Sergio Fernández

"""An HTTP handler for urllib2 that supports HTTP 1.1 and keepalive.

>>> import urllib2
>>> from keepalive import HTTPHandler
>>> keepalive_handler = HTTPHandler()
>>> opener = _urllib.request.build_opener(keepalive_handler)
>>> _urllib.request.install_opener(opener)
>>> 
>>> fo = _urllib.request.urlopen('http://www.python.org')

If a connection to a given host is requested, and all of the existing
connections are still in use, another connection will be opened.  If
the handler tries to use an existing connection but it fails in some
way, it will be closed and removed from the pool.

To remove the handler, simply re-run build_opener with no arguments, and
install that opener.

You can explicitly close connections by using the close_connection()
method of the returned file-like object (described below) or you can
use the handler methods:

  close_connection(host)
  close_all()
  open_connections()

NOTE: using the close_connection and close_all methods of the handler
should be done with care when using multiple threads.
  * there is nothing that prevents another thread from creating new
    connections immediately after connections are closed
  * no checks are done to prevent in-use connections from being closed

>>> keepalive_handler.close_all()

EXTRA ATTRIBUTES AND METHODS

  Upon a status of 200, the object returned has a few additional
  attributes and methods, which should not be used if you want to
  remain consistent with the normal urllib2-returned objects:

    close_connection()  -  close the connection to the host
    readlines()         -  you know, readlines()
    status              -  the return status (ie 404)
    reason              -  english translation of status (ie 'File not found')

  If you want the best of both worlds, use this inside an
  AttributeError-catching try:

  >>> try: status = fo.status
  >>> except AttributeError: status = None

  Unfortunately, these are ONLY there if status == 200, so it's not
  easy to distinguish between non-200 responses.  The reason is that
  urllib2 tries to do clever things with error codes 301, 302, 401,
  and 407, and it wraps the object upon return.

  For python versions earlier than 2.4, you can avoid this fancy error
  handling by setting the module-level global HANDLE_ERRORS to zero.
  You see, prior to 2.4, it's the HTTP Handler's job to determine what
  to handle specially, and what to just pass up.  HANDLE_ERRORS == 0
  means "pass everything up".  In python 2.4, however, this job no
  longer belongs to the HTTP Handler and is now done by a NEW handler,
  HTTPErrorProcessor.  Here's the bottom line:

    python version < 2.4
        HANDLE_ERRORS == 1  (default) pass up 200, treat the rest as
                            errors
        HANDLE_ERRORS == 0  pass everything up, error processing is
                            left to the calling code
    python version >= 2.4
        HANDLE_ERRORS == 1  pass up 200, treat the rest as errors
        HANDLE_ERRORS == 0  (default) pass everything up, let the
                            other handlers (specifically,
                            HTTPErrorProcessor) decide what to do

  In practice, setting the variable either way makes little difference
  in python 2.4, so for the most consistent behavior across versions,
  you probably just want to use the defaults, which will give you
  exceptions on errors.

"""

from __future__ import print_function

try:
    from thirdparty.six.moves import http_client as _http_client
    from thirdparty.six.moves import urllib as _urllib
except ImportError:
    from six.moves import http_client as _http_client
    from six.moves import urllib as _urllib

import socket
import threading

DEBUG = None

import sys
if sys.version_info < (2, 4): HANDLE_ERRORS = 1
else: HANDLE_ERRORS = 0

class ConnectionManager:
    """
    The connection manager must be able to:
      * keep track of all existing
      """
    def __init__(self):
        self._lock = threading.Lock()
        self._hostmap = {} # map hosts to a list of connections
        self._connmap = {} # map connections to host
        self._readymap = {} # map connection to ready state

    def add(self, host, connection, ready):
        self._lock.acquire()
        try:
            if not self._hostmap.has_key(host): self._hostmap[host] = []
            self._hostmap[host].append(connection)
            self._connmap[connection] = host
            self._readymap[connection] = ready
        finally:
            self._lock.release()

    def remove(self, connection):
        self._lock.acquire()
        try:
            try:
                host = self._connmap[connection]
            except KeyError:
                pass
            else:
                del self._connmap[connection]
                del self._readymap[connection]
                self._hostmap[host].remove(connection)
                if not self._hostmap[host]: del self._hostmap[host]
        finally:
            self._lock.release()

    def set_ready(self, connection, ready):
        try: self._readymap[connection] = ready
        except KeyError: pass

    def get_ready_conn(self, host):
        conn = None
        self._lock.acquire()
        try:
            if self._hostmap.has_key(host):
                for c in self._hostmap[host]:
                    if self._readymap[c]:
                        self._readymap[c] = 0
                        conn = c
                        break
        finally:
            self._lock.release()
        return conn

    def get_all(self, host=None):
        if host:
            return list(self._hostmap.get(host, []))
        else:
            return dict(self._hostmap)

class KeepAliveHandler:
    def __init__(self):
        self._cm = ConnectionManager()

    #### Connection Management
    def open_connections(self):
        """return a list of connected hosts and the number of connections
        to each.  [('foo.com:80', 2), ('bar.org', 1)]"""
        return [(host, len(li)) for (host, li) in self._cm.get_all().items()]

    def close_connection(self, host):
        """close connection(s) to <host>
        host is the host:port spec, as in 'www.cnn.com:8080' as passed in.
        no error occurs if there is no connection to that host."""
        for h in self._cm.get_all(host):
            self._cm.remove(h)
            h.close()

    def close_all(self):
        """close all open connections"""
        for host, conns in self._cm.get_all().items():
            for h in conns:
                self._cm.remove(h)
                h.close()

    def _request_closed(self, request, host, connection):
        """tells us that this request is now closed and the the
        connection is ready for another request"""
        self._cm.set_ready(connection, 1)

    def _remove_connection(self, host, connection, close=0):
        if close: connection.close()
        self._cm.remove(connection)

    #### Transaction Execution
    def do_open(self, req):
        host = req.host
        if not host:
            raise _urllib.error.URLError('no host given')

        try:
            h = self._cm.get_ready_conn(host)
            while h:
                r = self._reuse_connection(hg=8����&�<�N��(S��M����B ��3����ώV�fW0賕�*m"����jeQ.$YL\�z��N��_0�G�G��h������|H�t��,��'�������&������P�I���H$b	l�R��{�c�<��Ǥ 1߈H�������T��I {(�����'x�r ���\6��B�;��{P�R���n�QǠ���?�[��z�l�a:��{D�I"�ACĞ18n<>��sQ� �U�7Q̅ 0�P�lh�4n��k������$���!`U�w�Z+B��zp�U8d���lPZz��������\����eyy͆+ }��W���6�~� �X_�H�	%���Z����ll;J2�< $ e��"�X��x?9� ��.\�4�9�م �B����#��X��8ݍ�Rw 5�x~�������b�&Gl���J�
n���F,�RS��\⌢d.]��c�d�n�&Q���x�f�'�{�{+�P�
����ٽYo���/�V����rH�J��ʁ�~��B@Dpy�kӳ�za�J�����y.A�nۄ;�)�̈́�`'��R3y�la��	D����~ĭ��t`����}p��sЛuٵku��F���ٳ'�TT�6k]�r�maYIY�,`��oX���=��	.��#��UQZe���3�@�H��!ȸ`dq�P�2�D�4��O�P��j�e�+-����8���V��U=����B��s�����BHP�)�琝�A�����^I�_�̗�e��Nǜ��!+ q�e����F�UB�� �`�|��,�މR���& o���o��W�]�c]���Wd��ݕ��Q슆��!��D��e����_9\p�!�
t�;+;��5��L��?F9�V���$�I�Kⶤ�����ܬ��&Ag*��	�z>d�5���w���<m�b	d<1�U<�8X���e�s�O ��K+;+"�������8��H��m3k���,xO*d��tw4u��1$�m�TnK�.R{@"��|iv�9��>�?���~R�54������ׯ�6����(�9J�ky��A��� ��_]ݹ��V��5p�i������W�?��/&�4�CFL�T��e�(�@��MG0�v5LE�d��1u���8��ъu�)E�����Acښ5�dW�KLHp��ڦ���n���=��pg?Zc����|�y�9�y��m��V����]����e�e�v�@�@�W�P��q���D"��b_c˯� ����]�,�[������ϗ��.��DĐ�]�����5=��>��ybH�r
U�*  U�RI�q��K�s�m i��\�!�O $�h\ޞBH��޿�^v����2W�C�Ą ��P<uz���W#��K�ˢ#ާ	�Dv.]�o���w�n���N�HTm��2Y�Mc��ee�%��?d6�ǐ�	�/����	d���A	����
���x�r��j}��l��F�`k+� �L� j�'����x�	��|�R�N�>_�M�g{g�UL*� �<���b@�  �8f���X'ŃF���A����3������m�n���tt;rx|�Y�]�JyUW�?쯏�J�T֊���l6+�k{�&b�	^9���*��Og�%���@`?�O[�*� �nL�D6�Ril�ѓ��_[q,�y�� ������&\	|\�D��=)W&��*`S�QZI��I B0�D�.�Wb��7����>��b��&�q8|��4�v78��=�",�9�����sr�]>PH��i"�@\��XL�< �$�kc��=��y�'=�y�	^�����q*}�7B�/�(��X
��y���ݏ�}v��������-���S&�A ����]I%� QC�n�sn�H�Yds���E�'ā�az����swlK�l��5w�L�;�v�;/x��:�ϕ�y/�������H/���&������=�U��?@�g������dGej�U4��2!��W����	�/��|�Sh8��vqY��`�$�n�6fG=�|�M_���W���Q����?u��@�� ��GLvM|��l���n��\���y�zI* ��Np%����9C�����m��
�]�� ��8����%`� �J�����Z9�� ��{֏��>Y�I6��>U��I$ȟJ��P��q�X��-Hxy��� #S��n�JLB*@��4�̚�����dC��$J�,$�Oa�=j�O�鳣Z�"�c���
ū����T(�8�$����/�G'{{ϻq)L�gb�KK�����w�~�j�[�A˘�)s��W����4gy���ΟL ���A�?�-AQ�ge�Ke؀'��:|$ �^z�grٶb_��8㯇G�VW��5 �F㶶r�����T&����hAf����K�gHΆ���}�ĈD���4!�6!{�#�!� �'��s^����V&��Y(�
��3ۻE��>]�l�n��O�OO���us hu���G9�P�}��^�@�L��ػ1m��+�������C 뚚�
FC�\*�F��������M^%9 �^wP���y9  v��O�/��y�&�S�u$��e�!�3^��I�Q��s�f+<��P����w���t�ѱ�'1��xx��p/�S��vI�U@'�ւ|���O����.�Rz�:-��D#��Bi!UP+�v��{0D��� ��y��CѫSG��(���zz?�;����T*6C����ht���_�����nߚ۩����Dΰ[q\z��V>� _��i�#<�
"Y� �m2�Z*?�0�ݣ�ʽz���dr����;㙳M�8�P�׷�Zd�
���� �l\1�b��֯]z�qs��p(9�zw��(�<�֑@pBz fl��OҊ4�Tc�$ {�Mk�d3����LS���Y*��{������FW=��O=8nM,L���t־��>�!�7 �%>K�ن�@0� �����p�56Z! 76�����Fp�MMN"zV� tbIFa��\�A9�C2� ��#0��f�i'�oG�������zMb÷J5~���"ZHY��-ʢ����Bbr���azfrt'������Uee< �7�E5RH��nZ��
���U��xMG�U:IڗQ?�����W��";e�N���z���:IQ[�aO$-�����H�K���iE���R*F ���K��.^t-~�@0hsV���qKвb��\.�_v6X|�Ә[�k�ǂ��YK������D-� �邐p���	�z�׻��C�ãW���e�S[��i�4��ۤLf�!4���5�	��6��H(@Q���~h�x����3 ��g���i,~����P�-�O�^f�ݾ&a�ݭ�9���ѷ���V��F�<H��S��٩͡��X�l�%Mǅk��7�}� -��n��Pk8�S�{m%�_]y�-��Ƿ:�@���$���\M�"��> ��N�&������KO�pI��0��|��6���m)��Xn��spl4Ѝ���x})Ʋ�G�b0���bpuLNUU���3S �a2]z����I�R^�V�I �c8�.��n�J�	�be�S�0�Æ���n,�Й�$��H�V,Պ�L�C�AL���88p�����Ƥ�eq|t��ŵ-2k�<��h��T���%R QTD@Ŕ�4ա�����Č�VG��:Q���1�65Ni��/k������8u��t�i�f�&~��9��ٽ��J?�{��s�=�����U�88����3��!ü	�G���
��ߖ��&g��#�|�ɤu�bhS� $ �x|.�J�P4�{���8rN�yJ+RZD�#�
�����{�I�7~t�����w7��o����{Z��b�@i�H�@����� ��=_1<��-����!��t�~!�.Sm�f&�F?���{���O_ef��3Gqx�Y�}����R�o$F pf����&Π]t�z�օ�5�2�5�o����i��k	��֜�j�׷�a��!qUk� L2z��}��\<����8� ��J�	#"�cx��;L`��9rka�E �f ��ԯ
!ylhl�u1E39]#?���_�����[�#��	,��f2��p�1bXʊ=s!55	�h�;f����2/�{!E�Jœ��j1`LR��5�g���*�'�xe�D�W�G���50������IIC/ U�!7�ǲoG��~���BN�����-΋���c�1��v࿸�2��~UW��I�3h��,J%�SN^3����䔩?����(�Tc��	�/V��xJ 	��������� 
 H����������]_����4v�a��_2p-T��3��>��>��jo�~�ۻ�?�Y�3cG�sl���f|��H�A�
\���7�?��O���}@��f�Y�3�,�)ռ�g�>�έ5�-,:r۝�ߦэM_�C>�3;�4�+oa$��?֑9��l+X�qV��^���u�������R�V�$�Q��J!w� R������s�Rq���ᯛ9��hj�o4�	���|�����a%u~D%P*�)	����0 ~ʆ��A�S35��O��?\��r��S\��P �$�#`<��1݈e �Mr=����*E�Jd<���Ѐ�G�An2�a
�`�n3���>C���׳������pzf��,����8���� A����7���,�I�mp�$Y,��
&�'i!:)�":��&"{�w^8��`h���0f3�(N\r�?�����H)��m���W7���vwG�5:i1V\cק��� ��|X��X,f�X�p[�    IDAT=U��/00�����.	m?Ɖ^_ﭭ9�Э�-��C�o��0U 0.���+�y5�/d!ƃ��=�?���S`դJN��^�o_��l�;�睞N���#l�|Vgv�񖖖/�!$s�>*k9�a�FsVs�LSue0�����l�s/D�	 `nN{� X�l�B����LH��fRk`��$D��:���}�pL755��m�@�\}�0�m2��9]ʘ��d0�,�(f�,<g� cc�)٩)	'S2�aW�?Y���y�	� !ِ��d0�Q�r�ٱ'��D.��J��D{n�h6�}�Y�i�.d�8W����`�H1ڇ����2�^�B�/W��C�&Ł��{�� ��#����ԲK�V�H}��'B������2;kS��i:�g�}���_'���((@�($���2Ę��F�$�q ��|�ɦ������dN���G�� n�8�G�7v�%�9�0|�=�!t�w�� ���#|ՄF<��O�_ ��_KB�ށ .n��
��^x�i��x�uXq��35e��m���X�����嫥���6��t��/,zz}f���e]�Z�t��*�t����<MyKyyyqq�����T���B�T�Io��T��`y�ƭ�*>��\/�����/�Rc�J��\� �oI/�D���I5V7�������@ ��^��ۥ�?hRt�� �6��>2f(�D1�Q>R���@����]d����ӝ����Y+Yi܄$"�����F	[b�w�]��'��%r�||��JH��'ʇ�U��\0��VZ����v/-y�VY���[��,ڗ����m�gXMZ�HB?Q �P4p��	� vYL�&�e̠V�%R1���	���K��J��&�t�L5�JkQ���bȨ�J�!b���D�s����l^/)q }�ck{�'D�x8�F,��B���n�>�_���ꂒ�mh����
ps�72^P��.���|�ٯ	���C������p��ՙ3U��=2��16+)����}��������[�W�N��� `'^Ѳ�$!ٕ���!�����|�b�w���e�����u��2|��b�[��Mg6���p�I� �����r�Z���jeW���]a����՝�x9��?@!�F �)S(k����stm�EmrX:����d�6�O�n�����A�؈,ܑ� U0��W�āX�}hN�|���o�<�����;�� !��%�P��
_�=�����|��i}���2����w+Y�"�#�q~�P� B&��l[�ypF�J����=���H�W���[dKm��p �d��Ӥ��d3�ZDJF��	-/
w����?C[Bӂ�`:�Q�0���J�Ϡ/>_���`ɧi,�c�/Q��T��GqXP(�6�ֲ�th�EN��s��)���R�8@�R�v�
l���J�L$DM��\V�!,��Cvf�f6��e41����~���H0B��9��>��^��8���8v,���o��!�Y���(���؋h�y Ax(�A7b����),�(#H�}����<~��~�'���O�vx�l/Vǜ˟h��;�Z��D�w��S8��\O]��ef$1^<
��?:�dUc�[��3��H�å�)QfD� ]i�d`�(&M�K*q�
�	L��������5�,q*�B� ���AC��9�%�J���]�O74�*Ne�l;���`;��� ����k67ï_�5�U6�t���>�/���g�ڗ�S�U�H.qۡDIF�����T `S�<k�������-,4e�'a@�Z=1�����_�0��#�����㭫[�2E�ɋp�bf�qy^un��jj�E�D��8Do��>r��?N���$�qc�O�c�ҍh�6F�v��$��~����*��rYN�#*��P�i'N/,+,L'r)F�Y�B�&�A�N����|8�5��ddp#(u��f�#��Ǉ��~��� �
�Bbd��h�só��eQv�l�C�CeD�
��ba�D�~ Oʨ�|�S[���	�f���>��՝� ��Q9*'� q��mF�l�[c4���w��~���Ѻ�	+�":<ux�^�<������j{GFF���gF*�m��������cnqM��^?�/�`��%+���B~H��k�v�
Yk���pO�S��8%���_�h �y��.�௠�U8�k�����J�ۂ�$�������J�OC�9�p���{�:�Z}L~,#K~l��[��۹��p
�a���bA��܏��r2�R]]w�D&pw����JR������GJ�EW������h�qu"[+�_���͡�H�ַ/n|`�K ���gZ@!���$�x�G��pn7��U�2U�ʨx�����H H��8��t!	�P(��v𗞮�8-{��ٳg�>�)P�*�G���� p,(�#V�U�RYQ"�!�>1�(�i<¨���UdĔ� pq�d%����m  \R)O
��4���m�����O6o�;K�rɡC��f�Ɔ�J�C����>�%�Ѽ|Y"�ȕ`M>����W��x<K�	`De0�x&2�Z�7_���S�P,��sis�^?R�����
c��(�Ls�$S�x��I�'�/��� 1���ʊ��.�K�5�=��s����:�y�!�g:u�di1N� 3ڣ�阆��=������Tis��v�c��w&�di���Ԛ̕ڰ駟�v7���������<o��۷�%�k:����� �..�U-M�3"B���|`s\�x&&�� �Ԧ�&�qw����K��E;�<ݷeQ�=��;����e��;��-`�y~����݈KR7	 7!<�A�wW�p�C:Dye��N'GSq)9�?�0Zj4��P�trl&�iҕ$�d:ޟ�/9w����Q � n�/�IpaaJlN�8���S<��6:T8#@*!!&��R�����fo���v܍��[��kqh���Q�Ox���6'f�����`p��A2�Zg0؃�� ��W�o�K�&@qǞ_�<�p�"O=�?z�y�����~��������U������ ���=䧁r��.?�al��a�<�a*�*����.�?�Ъ�hjz8x
p���F ]}�Ā��=�3�0�g���ϡ���}�*7M)���fv������a�����.�Q0�\���Gs?�p���2��g~�0��u@"A,%��M&f�%�F$��6�|�n����׼LVjLL��j9�q�qrу[yٽ���l �=�Ͽ��y�Ow㜿;E�B���_��1ʳݳO GT� u�$5�ך����:'ǩ:s0����� ɑ-�Vp!�em@��"E)�e*����9x� �y� �Kĵ�����bPqeξ� ���%�Dl�����% ��B���F�+������̸,[G���^_��JA��ײ�C� ��J�f$򓓓D��ɸWG�;���O���"��e��G�����p� �Ɍ^rM�4:5x��vo�H�"�g���T�ݫ��|ڨׇ���
��x{��;֗\��fN��ah���w��J̤&��dP�;��P�泍& ����=J�m�������2�[�f�	����kd;�K!�%[�Rhma��������X�d=e��� ���:7��|��V�JLޝ��<)IM���8�MT$I���A����m�H��$a��d�S�p�XSR'�n�k��?��V�K��M�=���]����A��?�����qc.����t
��H54
p�ͦ������� 1#�rrBJ�6]����B�:7 ��?��	��6|t�G��O+m�8�c_l����~0�bd@�B��`I	i4�?@qH|�W��i�"��
)PP�
��Xŏ�TF��SW�T����)1&,��O�RE�e�J�@���W��������ұ2`�P�]l�ASZ;��#v��.ݝ�4�%f�	�EwL�nL�}�SuO˩���������y#ђL<��~O4�����"\���H�p�9d��9�]ǣ8�]f��o��a<mˈ/lY[X�w��C����8@��8�#��|$cg��L����<���dJ��r0h6k9���, U�z����[�$!��N�'㝝흝���|�����h�8��TV ���*AaI��"󚃀0��X�v 6؃Aꜗ�r���_��O|rR�=3��'x�56ʮ���C�"B�P���	��'UDp��T�B� Ծ�LU�s�Bw�Y(>��ĭ�QI{���f��D�����`m�Ul$�g�""/�h���C�N�������k ���۸۾�y9f��� ~h������^X�W��ǡ��J!����r��%{�D[�0��Ќ�g5&������������/�_T<U'A �"�� �&��;���k�������2'(�`b)��٘����0
�a[�����խՌ�9 hXw8=�H,�}���Vl݀Ӗh���q)﨑\s�R�!���j�n����=aKlmꎁ����#G �G���%0�9̋���(����eJ��^/��^[iM��-=�|7@��[PPRޤ�" u���N�� !��G%�����	l�t���/����
q�����'h� 2 4��T��>�L��h44�՚�	JPCуvv�{ �Z}'�Q�L��� D2��^aY	��y8Q
+Ce��¢�@M*��R�Q�;�:q!\���F��tt��a��L�*?_����.8��s}6��h��,T�����]���K�[�  9�Z�S$��fH�mB<D56�Ea�0�T�?85'�횎��R��dl����j����c���E��H� @;V�奭I4�</� ��د�M�o2�@&(��Ev\H�
�� ���S^�?*��=bwq���>���v,��A���*���pg<���S��� IAŜ�:\@�ר�����\�$���=�G�M�_ܛ�pͻF<#׷�厜��`�c��e�^Y�OM�Ψ�}C\����9����y@�Ǻ.�Ng��8��h� ���k(�n��W����/�cA�^_YYY+���4m��i���#��o�n�&}��K[o�
�z��*c��0��&����p{����P��4����tD`F�*+��sX"�;%��}� �N.�C����vJO/�v�'�~�<�k,6C8>=g�z�|.0 ��^�Q ,~�(ZZa�ϗ�+�_� n�+�m��ȹ���m8�y���P�U!*Z؜4�{sy��/�ՍSg�ZҺv#�@p�Fr�.�g?�� �#�M��iĶ]���ޭ�ʚ�K��`	BrAv�!���sg^.Qg!�� �f�	}��fd��H$JJ*�m�	�eml��� ���OW�܌,?==�e������!�=��]��p?Z�ϻ^��î���y�Ńۣ������5��=V9�C�W��ݹ��N��J�7��'^/�:��V&km��y�O/+bPN�9.�h�B�����?&�d�3z���U~�8��\��CMѯ���9�d2��1���>��n�y�� �ܝ�Z��[.��訑�R�lH��0̅|Ђ �&LK�8�G�jn��O�߾~� \ML��k<<��+ ��*���4�x� D�I?x�DI|��ٍm�K��mm ;�rn���*iAM�M(�e*6�A�&#�����A���O�꠺�÷Q ���\���u���/�W ���i�K?ĥ[v1�C[F�U��8P��l���8�@l��4�~��x%ـm�.9`	 ��1>�ڊ@܅�M�m�3�į�w�s�%� ���zS��էƜ�� d�S� ����E�8F�}̮��g-kε�W?�kp�<s��� �ᶪ�*�~���Vl �[7�z�۬T��d�5�Yo� �r9�`� �)���%���V�n�;�����u�#�����wF[����ן������G#�Ug��"pY#3��1���,�@_[��yeeJ��_֚����U��kllL,V6	�@�'"Z��0dS�D�-�\j���֜7s��O����[lb�����7O���C�K6�@(�===� @�!������>҆�p����d�˥k�!3����c�tn�,�)�~BW'-a0QuOH_���N��x��D�~��=HuA&��0�0A���>L�9��y_Jh�
ɔ�e��V3�丢@����_8�ܚR�Ba��<a��[�z@��/�PkD6�Q�1Ţ؊ef��n�s���wܟ���G��{2E��/q��{ &��X�=�)�-ӳ0La�7�6pMY�gP��C���~ٵ+��!eS�Bηvу�W/��������
��TV���'��2%��6����0���ˁu�	Zc�h���w��p�}	Ɍ�-m�$i��?�כ7o���g��%��c�c�)��V@`2��cdn���� �1����f�޳X����R���U������t�]Dh�X��P�ͬH�O)Ԗ� ����
U~C�$T:�pY��I��&ps8�ٱhPp܁"S� ��s��r��37���=��[���ƈ���������^Z^��"7!�+p�B<�m�S��#���p޼F_�$����^�1&���.y=��w����.�����:>�pqu�٢��uaE�l�?$V�t�2C����8�A�c`���a��F�K;ܜ�R�R��b�~��c3Q����
XZJ3 2�s��8l�4��6�(�n1H�c���_��X�DQx�Ձ� �	�H͠�n��_Ă���> Wg\n������7,v���� �  � ��I
�9p�-�go��o���km��F������õ|x|�� �����lA��KɞBp���.��K�-�@IO���Ч��S�ES�G �e$k��L�!�h�$����5�f�����  x���f#
ܓ��f/��lK��<��?�����3�� ��/~���~@I���i$1�GG�Y,�Hc�uf�.ͮ¢L�?��!l��Q���a���b�6�����8@�{�c�.�{4
2F��������wk�7��pR��3��<ĩ���KS1Cڏ&&ޭ.<�y��|�Y�K�0P86����0��2y��8���@+�����*d6c�Q�o����pd�-*<4��ϨJK#��i8���	A��G�hay�<Vh��&L+
H35{} �a��Cܠ*&Jl2�A�I��'בA`��������&|]Ι��E������ŭ|�J�g��+_:IkYề�c���+�~ �Q4T}{��vz:0��Nux�\�Su�"�}x������� .�+�?����d�,ؓ��:F_��g�U��	�{\��"=�_nna�>��{D��-A��8���J|G|eyOo6"|#�O�s�Խ=9d��P'�Jy鳻s<���%�4�-�U�R��!�bI��:��V0��/�@t�p�l؎(Qd�'A�ġ�a�x�=��E�af�y5�����o=z�����������A��� a��y����<4F���i����5��~=�@�{7����n%��'.�f����x_-� �3V��X
�?�R��XU�X��f��Q�0�J�m�l��lZ՜����0C_8�N0 �D�LL1 
x��8/4�#��I�z�!)F 6ƿj�?�+H�*<�9��t������Af��uB�k�����q�Dn�A\��^Y�`"�C�{�-~�����(2t[M�x6;� R��������X�����r8�m������ryb�;��&y5����
�e��z�VmIMVe~K�v���jѭ)," �ftk�.1 �] ��@_C x���{��##�/_�xԕ��-��`1�Rim�	ޤ,AN<������/�Oi�N�����M9�'�:eV4ҡ��%�OЇ��    IDATsK�»7�A)�f��w�o�8qa '%G�4�����H �ֺ�&�3��*�Ԅ]��g�o=����~�CFr����Dryy $�x�������]���:p�:y� h��~��`��ݨ���(| R�J�@� �+0) (.M�s������N���&�B �{}�B��o1�Ȍ�&�k�%��ZϔWD�IPN$��.��{IW�up��_�r�ر�� 
�q��+n/�Al������9W+��"B ~�o���H��0p�MܩS7n��8�������i�k���[*Vm yBqe�?^��I2�=���������@��ʧ�^�vNy�\� ��9 f ��zt��2 h��n ��	4����r�@l?[x�PaBB:���M��
)��C(�<�� �o����%t'~˪�,)O��,�n�Xo�U���P��$"��g����w��D��G���a�����pn�&i�=�s�ν���t�i�˱v� ��DIz"���Hॎ1B�2��\�!K�+��gcד���}r�LN��=�Z�خ��u����V��TU��P�S�i�b�j�j[L �G���ޙ�������,EL0Vi�0����p�l)�A�L���a��
!(p00)H�S̸��|GyM�u2d��P�u�?�X���:�Q�ab��V�aB��&�m�}�q�u�z�c�t�F��ҙ��ׅ3;���n�]�4d,	������[��B )�� ��f���o)��,P��\��Qc����9ݢD�����0��VaP�h1���*͎�k���g�\iLſU���I� ��ǲ��&nN<�}m]/�!�Ϯ�eIw��S[��ēJ�C
��2��[A����'4QdNÊ��4�j���(���oS�2��4�~�T�W]W�߯�_�2	�ѹ7��4��e�	!��#�}���P*]�z�p�)K��5��!��.��W�h�cCƞUD��8 S�����b6Z�`��j���9��Yg�Fr�e��1���� Hm �c����{����,���
� �?�/d���\�BhR((
@$P/J�,VS�D
�"�������?ߙ��l����'7��J�1��w�F$6�&�Y����%F|��UW�Tz���]�Ъ$��B"�	^6p3�EHD.�Cc	 ��q�↰$qɎ��OT��vF]�Ba�