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
# Copyright 2015 Sergio FernÃ¡ndez

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
                r = self._reuse_connection(hg=8’¹€ã™&Í<‰NÃÑ(S‹ØM ¢‡B áÂ3ÔÂà‹ÏV´fW0è³•Ù*m"±¦¡újeQ.$YL\Œz¶‘Nø±_0÷GËG¾Åh»© ‰™Ë|Hçtı,à³Ä'üôá£Óã¥õ&è÷îùù«PÈIÍÉÜH$b	léRíğ{…c¬<†ĞÇ¤ 1ßˆHŒ§¬æšâTÁŞI {(úøÓ¸‡'xùr ûñ\6ÅÑBú;ê÷{Pò±„R„çÌnÆQÇ ÏÏ?ñ¤­[«î¾z½làa:áÂ{DÕI"ÙACÄ18n<>ğøsQü ¨UÖ7QÌ… 0 P¸lhå4n÷Àkù¿²€é$¤¹¾!`U€wìZ+BµòzpÂU8d·èlPZzø¡à‡–€\¼¼ûeyyÍ†+ }¤ÃÂ‡Wğ…6œ~ó„ƒ âX_ÇH«	%¨à—ZºüƒÆll;J2€< $ e¨Ñ"ùXŒáx?9œ ê«Ø.\Ü4¹9¶Ù… ¾Báó£¡#‰»X 8İîRw 5úx~Ÿı²ÂÚÖb¸&GlúòÎJ½
nÓê›F,çRSû\âŒ¢d.]Œİc˜d¥nğ&Q¨è˜x’f'½{ñ•{+ßP¸
—ÊÑÙ½Yo¼™´/“Vû°ûôrHJ¹ÊÇ~ø’B@Dpy´kÓ³Ìza¶Jí£±»‰y.AñnÛ„;á)çÍ„Ğ`'¶âR3yülaö‘	DÒãÑÙ~Ä­Ÿt`Ïøõ¬}pÿ‚sĞ›uÙµkuÅêF³êúÙ³'ïTTÔ6k]ær“maYIY‰,`oXÿÍ=ÑÖ	.á #ÁúUQZeÀ¥¨3Ë@®Hï¨!È¸`dqˆP¤2™Dò4¹¦O©PÚíjøeµ+-ÿéí­î8­¶V¨ñU=æÀ¤ìBúĞsÓäæ½BHPÒ)ÃçãA¨›ŠÅÂ^IÍ_ŞÌ—åeóùNÇœ‘—!+ qñe–éòçºFUB€Ñ `À|¡, Ş‰î˜–RÖ¨„& oÿ‹úo£å¦W‹]›c]óòíWd£şİ••÷QìŠ†£„!ÄDı©eìÉ‡î_9\p™!å
tè;+;¿·5©ÄLˆ?F9‰Vü¸œ$€I¯Kâ¶¤Ö£’ôÜÜ¬óâ&Ag*¼ÿ	Äz>d¦5ÁçÃwÇäõ<m•b	d<1ˆU<¾8X¶‘‘e¿sÑO ®âK+;+"¢‡éñ€ÇÅô8†ãH®¤m3kğÂ,xO*dÁõî¿¾tw4uãÎ1$°mTnK.R{@"Üÿ|ivÁ9çÍ>Í?­ë~R§54ŞĞü¡¢·×¯ƒ6±æÇ«(ÒÂƒ9Jšky–®AşÍŒ ë”È_]İ¹â“ÅV«Â5piª ¢¸µ­Wş?¦Î/&Í4ãCFL‰T”²e³(Ä@—İMG0¢v5LEëd‚±1u¶‚Œ8ŸÖÑŠuİ)E¥ƒ £­AcÚš5©dW©KLHp“éÚ¦½šŞn¼ÙË=çıpg?Zc°ñÂş|ÎyÎ9ïyÑëm¶ÉV¼ã†îÛ]Åù…»eÏe±vÿ@­@ÄWPº¾q¹ıÊD"îÅb_cË¯ş ‹×Ôğ]è,˜[Š±‡Œêò‰Ï—¶™.“«DÄÚ]îş¸ßÛ5=­Ó>›æ³ybHßî‡ºr
Uİ*  U¨RI…qª«K˜s…m iæÔ\É!„O $•h\ŞBH½¦Ş¿§^v†Ï×½2WìC­Ä„ ™ŞP<uzüŸÔW#¤¸KË¢#Ş§	Dv.]ìo‡ØñwÙn×ëÃN½HTmºõ2YËMc—åeeÌ%…š?d6‰Ç‚	©/­üøä	d€•€A	©õØ
ƒÃôxêr“Ñj}±¼lµFë`k+ü „L‚ jâ'ŸÖ“¾x·	‹Í|õRÔNä>_ãMœg{g¤UL* ¶<ş’áb@Ë  á8f¬‚áX'ÅƒFö·áA¡ö°×3ú”Œ»¡îmõn¶ÿğtt;rx|àYí]JyUWà?ì¯çJêTÖŠ†¿l6+ªk{¬&b¹	^9†……*£ßOg€%å@`?ÄO[Î*‚ ŒnLñD6ŸRilÓÑ“ûº_[q,–yÍß šßô´—£&\	|\ÊD»ß=)W&şü*`SƒQZI»²I B0ÚD÷.îWbòŠ‹á7ÿ¨À¼>˜§bÜØ&çq8|›Ã4„v78…Å=½",Ÿ9áõ†ºòsrğ]>PH¾Œi"‘@\ÌÆXLí< ›$çkc¯†=áy…'=yÅ	^¹ÿËéŞq*}²7Bª/Ñ(‘“X
’øyĞÃİİ¯}v£ãö˜Å–Ûì-²ğŠS&©A õŠìÌ]I%™ QC—nÓsn¹HüYdsŠŠêEú'ÄŒaz¼¾áswlKÚl¶µ5w˜Lı;v»;/x‚¾:¹Ï•áy/àÿø£ƒîÃH/õò&“‹³ÉÄø=ºU‡‡?@Şg²ÒØõÀdGejU4óÏ2!Ÿ˜WşÉ´	…/ŒÌ|«Sh8Üò„vqY­`†$òn¶6fG=½|ÏM_˜»ÕW×ôÌQşå‰ş?u¸«@ßÌ åèGLvM|¨«lÙïënÀ\Ÿ»ÙyızI* ñÁNp%×Ëõğ9CÖ×ÁÙømæğ
á]Ë åĞ8æÚ»%`ƒ ¹JåØ»õZ9ÀØ Úà{Öç>YäˆI6ƒ>UÈáI$ÈŸJŞêP«’qƒX®Ó-HxyÔÀ #Süân‡JLB*@…·4ò…ÌšƒšüdCû$J¥,$ˆOaŞ=jçŸOÒé³£Z³"c¦‹É
Å«×ŞÀğT(¦8Á$ïşÈĞ/§G'{{Ï»q)LÒgbûKK€àÇèÇw—~ëjó[ÜAË˜İ)s®…W‚»Ûâ4gy£§ØÎŸL ÎÍôA?ú-AQgeêKeØ€'©ß:|$ ‚^zÑgrÙ¶b_Áó8ã¯‡G­VW¨›5 â€Fã¶¶r˜–üšãT&ş¢»hAf‡À¯½K‚gHÎ†æöÈ}ÇÄˆD£±ì4!ò¨š6!{¸#ë!Ö ñ'©æs^èø’µV&³©Y(Ü
õÀ3Û»EƒŒ>]lön½…OÀOO‚’«us huŸßè‡G9æ®P˜}¸Ç^î@şLöØ»1mìë+ÇÜõ¾›¿C ëššÂ
FC´\*•F†¾ÿ‘±íêÿM^%9 Ä^wP­¨íy9  v”ÓO»/èîyó&ÌSu$Æeƒ!¸3^”›IÅQûìs¿f+<¼ÇP§ÓÉáwÃñÌtùÑ±”'1µêxx…Çp/SÓñvI‹U@'…Ö‚|àääOÇãÀ«.ÅRzÍ:-…D#µÒBi!UP+¥v†½{0DÙÍó‹ àëyó…CÑ«SGŠ³(®­¹zz?¥;ö¨€ÑT*6C³û±¥htşÇß_¼Ñî÷İnßšÛ©–…ï¬²DÎ°[q\zŒœV>® _¸¹iÁ#<¢
"Y óm2¬Z*?¢0Äİ£ÊÊ½zº÷ıdrÒöü‡;ã™³Më8ûP©×·ÈZdê
¡ÜÏÚ ›l\1œb¹Ö¯]zqsëğp(9Ízw€Á(é”<¡Ö‘@pBz flƒ¤OÒŠ4©Tc›$ {²Mk›d3…“ÿÖLS©ÍY*°½{¸º½ı–¢FW=³«O=8nM,L‹ËÊtÖ¾¹Î>°!Ÿ7 €%>KÙ†Õ@0Ä ¢ÄŸ˜ØpÔ56Z! 76ŞÖÜşâ»FpÁMMN"zV— tbIFaéş\ÊA9íC2© ˜#0µæfËi'àoG¢½§¢¶¶ºzMbÃ·J5~ÇõÊ"ZHYŒÁ-Ê¢¼ÂÃÍBbr‰¬Éazfrt'»¥˜©òØUee< È7àE5RHúnZÓò
ÁÚ€UñÓxMG«U:IÚ—Q?Á €ğ¾WÈî";eãNÅ®Âzı®¶:IQ[aO$-˜‰âúÆH×K¦ÈiEğ€àR*F „ûKóï.^t-~Ë@0hsVÈìöqKĞ²b³Ë\.Í_v6X|Ó˜[ôkşÇ‚Ï‚YK‹¯Òà•ÊD-¤ é‚pé‡ïú	ïz×»¬¯CğÃ£WƒëeôS[¡îiÖ4÷„Û¤Lf¾!4³¡5ä	‘õ6¡©H(@QŞèÙ~hÇx¼¡èÄ3 »‚gèÃéi,~ü÷«ôPÓ- OÈ^f«İ¾&aòİ­ù9†ƒÍÑ·‘ÌúV·ŸF§<H·SŞÙ©Í¡‰±Xòl¹%MÇ…kı7›}¤ -—›nü¤Pk8SŞ{m%À_]yã-ÍÍÇ·:û@£Œò$²ºê\MË"¤€> ³¿NÙ&¹úõ¿èøKOÃpIš¥0÷¼|ùò6˜æm)ş¿Xnÿüspl4ĞñöÎx})Æ²±GÏb0°ÇbpuLNUU™¤¸3S Ğa2]zğ¨ÛáĞIÄR^™V‚I Ÿc8ˆ.ºğ–n‡Jä¡	‘beåS¼0„Ã†ì°Ûñ›n,áĞ™ê$„HV,ÕŠÁL€CÔAL±¿¸88pšÿËÔÙÆ¤™eq|tÅÖÅµ-2k²<úÔh¦¾T’Æñ%R QTD@Å”è4Õ¡˜ ØÁªÄŒŒVGÁ:Q·¾Œ165Ni­­/k´«ÒÓÙ8u÷Ãt²iİfÉ&~Úì9÷¡Ù½¦±J?ğ{şÿsî=çÜé—À¡U¡88ÀŒĞÃ3ìÒ!Ã¼	Gáûğ
éé¬ß–˜&g‹ƒ#¦|‘É¤uğbhSó $ Éx|.ÀJæP4Í{—“ƒ8rN€yJ+RZDø#œ
‹¸Üûù{„Iğ7~tû‡«İİw7Ö×oƒ÷{ZøËbˆ@i™HŠ@‹Á–ñõ äé=_1<ìğ-š‡ı!‡tú~!é.SmÜf&öF?ìïÜ{ùäÉO_efúö3Gqx´Yó}·úûæRÖo$F pf­çÎ÷&Î ]t÷z¬Ö…Ş5³2¹5³oÈê…ªi©«k	¬©Öœ­jÕ×·×aü§!qUk® L2z·œ}šŠ\<‚»ŞŞ8Õ ‚íJ¯	#"¢cxƒ˜;L`í²Ğ9rkaáE éf ¼ËÔ¯
!ylhlÑu1E39]#?üû×_ÿ¡Óëá[¹#µî	,ŠŠf2¿¨p£1bXÊŠ=s!55	Ôh¾;fıœµù2/…{!EáJÅ“¶j1`LRË5ÁgùŒÇ*¸'ØxeDÅWÄGÆÇç¥50£Òá„Œ—IIC/ UÖ!7Ç²oG¯ö~í±×ÎBN¼çùÌı-Î‹¿ÄÜc…1¢Ávà¿¸2¸ÿ~UWÑä¬I3h°ˆ,J%ÅSN^3ñÀ€±ä”©?ÅÆš¢(¬Tc•Ì	û/VûòxJ 	òš—Áè˜óûƒ€ 
 HáøîúİŸŞíŞØ]_ŸŸÀ‰4vÜa˜_2p-T«›3ûÌ>¿”>ßÌjoÚ~æÛ»Ú?ãYÜ3cGËslë›Áşf|ºHÙAÎ
\ıéã›7³?˜îO—îÀ}@Üéf±YÙ3¹,É)Õ¼µgÆ>ïÎ­5û-,:rÛöß¦ÑM_›C>³3;»4è+oa$ğ£ªô?Ö‘9ä¯êl+XóqV»Œ^…¦¼u°½±­¾şºRVé$ÀQÀÎJ!w  Rƒ…ééçÓsËRqº´”á¯›9Š¿hj©o4„	îÒÉ|ûöÀ ×a%u~D%P*ó)	…Şõ0 ~Ê†¬‡AóS35¥šOâã?\¾¹råˆS\©çP ’$æ#`<¥ğ1İˆe ŒMr=÷º¶œ*EäJd<Â×ĞĞ€²GÎAn2a
¹`Án3ÎæØ>CòøÅ×³½Â™áğpzfàù,‚¿™‰8ç¯ Aä’ÿô7ïçØ,¶I‘mpÌ$Y,´–
&š'i!:)­":­ä‰&"{ w^8„Œ`h¥¥È0f3‰(N\rÅ?ŸğûH)ÌÃmÇèîW7ÖÇçvwGÿ5:i1V\c×§ƒ†ß ƒ²|XÀ¹X,fœXìp[Ì    IDAT=Uş¥/00ãëÀã²‹.	m?Æ‰^_ï­­9ñªĞ­­-»C³oæİ0U 0.êÑÏ+‘y5ê/d!Æƒƒï‘=î?°³³S`Õ¤JN^ó¦o_ï‚Ùlµ;ççN‡Ô#lú|VgvÚñ–––/Ê!$s²>*k9şa•FsVs¶LSue0§°¢ì÷lïs/Dï	 `nN{Ñ X§l•BŞáĞÆLH¥ÒfRk`©€$D°²:“¢’}˜pL755Êõm„@ğ\}–0¼m2´€9]Ê˜±Òd0Ø,â(f‡,<gé cc¹)Ù©)	'S2ÁaWî?YŞÙÙyº	¯ !ÙØód0‘Qår±Ù±'ùÜD.ôJœğD{n‚h6ä}ñY‘iÀ.dÉ8WÁ…¢É`¨H1Ú‡––°³2Ä^ò…Bû/W–¦C²&ÅÎ{÷ğ ô«#çÑßÈÔ²K—V™H}úÓ'B¸ßğÁ É2;kSËÀi:Šgº}»€_'ƒÇË((@ô($‡ı2Ä˜£±F$¿q ‹Ú|¥É¦“ØĞ¨ŒdN¥ÑGşñ nÃ8¶G×7vÇ%9ş0|¡=¥!tÄw…† ¨Ÿş#|Õ„F<õÌOö_ ¿Ğ_KBÈŞ .nâı
¸œ^x¹iõÀxÃuXqµş35e°Ùm–í×X„ÜúÌÆå«¥™ÍÚ6‹ït÷‚/,zz}fû¦Ëe]ğZÿt‹Œ*Út÷º­Î<MyKyyyqqİõœ£ÑT–®BÔT—IoäÖT§`yÆ­ç*>ØØ\/—×éôÃ/”Rc‘J¯à¡\ï ¨oI/¬Dşº»I5V7£€Œ—ÊÚÛ@ °±^®¾Û¥«?hRt°º 6ÁÃ>2f(‚D1ŠQ>RÌ¢»@²ıŒñ]däòÎòÓååûY+YiÜ„$"€íÎÌF	[bœw»]’“'‰Â%r¹||ËÈJH‹'Ê‡ÃUãù\0ïÿVZŠ¢Ïîv/-yÌVY­ßŞ[±¯,Ú—ü‡µâmßgXMZáHB?Q æP4pæî	ƒ vYL³&›eÌ V¢%R1ôÄí	Àù‹K¦J´Œ&òt¤L5ÓJkQÙôúbÈ¨€J¦!bÌàĞDısæÑl^/)q }Ÿck{â'Dôx8ŞF,È€Bº‡‚n¼>í_íÀšê‚’Œmh¯À¾÷
psï72^P¹¼.…Âû|€Ù¯	‚ÁşCñ—§ñáÁ…påÜÕ™3U’ê=2õØ16+)¯²¹š}ŒÅ÷šñü÷Î[›W±N’¨ `'^Ñ²È$!Ù•×ö÷!›­¸ÑÜ|ãbÅw¥™Õe¸õ¬©†uµò2|ÚçbÙ[óÆMg6¿¬°p¤Iı ¬“·èõrƒZ¡´‰jeW¤³¸]aª¶×Õ¿x9“É?@!ì®F ±)S(k¬¯—ëstmíEmrX:¼¾ÍdëÂ—6àO¦nÏù‹áñAÛØˆ,Ü‘Ä U0šËWÜÄX}hN|²óæŸoŞ<Åëü¾É;‘” !×É%P¹ğ
_À=¯ÂÃò¹|¾Äi}í”ğÉ2¿¯¯ïw+Y€"ü#Úq~½P‘ B&¸÷l[¬ypFJøó·ÏÌ=½HàW—‚ÿ[dKm•˜p ·d†÷Ó¤“Úd3™ZDJF€–	-/
wš£±í?C[BÓ‚´`:ŒQ®0€èÈJàÏ />_ü…Ü`É§i,Øcı/Q×ÓTš†GqXP(à6™Ö²µthÂENÆí¶sêÖ)§•¥R©8@†RÜví
lÑ‘JèL$DM–ˆ\Vê†!,ÆòCvf²f6ÌÄe41şšìû~…ÙÓH0B‹å9Ïó>ï÷^‚ı8ëİğ8v,µüØo¼ÿ!ûY…„ã(¸ğùØ‹h¡y Ax(à¡A7bëİŞù),Œ(#H€}À€÷ê<~ÿ¼~†'ıÄÊOvxßl/VÇœËŸhÍÍ;ŒZ•D»w“áS8Ê¯\O]ãÎef$1^<
™½?:µdUcí[‡ß3‰ÛHáÃ¥É)QfDô ]iÌd`Ö(&M‚K*q°
î	L”òÔë——ÉÌ5,q*ÂB Â¶°ACéò9%¿J†ùÔ]—O74˜*NeŸl;Š¸Ã`;éâÌ Ññ”Æßk67Ã¯_½5÷U6Útƒ­•>Ö/ĞØægÚ—æSÇUÛH.qÛ¡DIFÖùÕÔÔT `S®<kÿù¿ÿ¯ÿÌ-,4eâ'a@¾Z=1ğø»ïî_ñ0˜ó#©¾ää™ã­«[²2EüÉ‹p¿bf«qy^un±ÍjjÂED‡£8Doİû>rıË?Nï˜$qc³O®c…Òhõ6FàvÒë$ÿŒ~äöíò*·ÎrYN¥#*Œ‚PØi'N/,+,L'r)FÔY„B’&ğAÒNÀŸí|8Õ5Èéddp#(u°Ÿf¶#ëåˆÇ‡ûÁ~ôƒçä¤ 
ÅBbd¤€hÀsÃ³ƒ¡eQvØl½CÑCeDá
¶übaşDË~ OÊ¨÷|ÈS[ßà‰	ÜfŸİû>ÜùÕ« ¨„Q9*'» qôà¯mFßl¼[c4ö¨šw«­~İÓÑÑº¥	+ü":<uxó^Â<à•§Ë×j{GFFªš›gF*æm¥¥­ƒùcnqM°å®^?£/ï`¬Ş%+¿¸ôB~H¡°kÑv™
Yk¸Ğê´pO¥S´ó8%Ùúò_†h îyáñ.à¯ ñU8Ük¯ÂÚù¾JŸÛ‚§$“¹àõËÊÊJ“OCı9íp—€Î{´:·Z}L~,#K~lïê[ÄßÛ¹ˆğp
¬aˆš±bAŒšÜ¤Òr2ÌR]]w÷D&pw•ŸÀ¿JR€ûëçêëGJƒEW¿š¾·¨±h¾qu"[+›_ŞÄ˜Í¡•HúÖ·/n|`áK ›ƒ£gZ@!³³ä$ĞxŒGˆÓpn7§ U²2UæÊ¨xÌÁˆ±ıH HÁ–8ĞÉt!	ÍP(vğ—®ã8-{øÈÙ³g¿>ü)P *ÃGøÆÅá¾ p,(“#VâœU¥RYQ"‰!>1³(Ài<Â¨ã«ÈğUdÄ”ì pqçd%úÙÊâm  \R)O
›4¡¸¹mùİğúò›O6oæ…;KårÉ¡C’¬fûÆ†½J„Cìßãñ>ä%¤Ñ¼|Y"ÉÈ•`M>ø±§WÀ‚x<Kş	`De0Äx&2éZ»7_ÛÛÓSõP,´sis³^?RëĞö‹«
cãã(İLs¹$SÍx»½Iå'ò/·”© 1¶ÆÆÊŠ‚‚.ˆK5°=§s´†¢œ:Êy¦!Ûg:uòdi1Nä 3Ú£é˜†¡=šÌõæ³ÙTis„ív‡c°Òw&ŸdiŠŞèÔšÌ•Ú°é§Ÿív7µƒ¿ø¿áâÂ¹<oõÑÛ·ç%—k:òÕÕÔê â..«U-Mâ3"Bˆ‰‰|`s\èœx&&êÖ ¼Ô¦ı&óqwüµŸæKª´E;ˆ<İ·eQ¬=ø¢;°¸µºe·Û;Úû-`y~œëŒİˆKR7	 7!<ÁAàwW¡p»C:DyeñéN'GSq)9€?0Zj4ÿªP©trl&£iÒ•$Èd:ŞŸ‹/9wîì×ÛQ ê· n°/âIpaaJlNË8™¤€S<ÄÛ6:T8#@*!!&¯…RŒ™•ÂîfoÕ÷â‚vÜ¸¢[‰kqhÍQƒOx—ıü6'fÎä¼Û`p»İA2ØZg0ØƒœäŒ ÄÂWæ™o‹K&@qÇ_ú<˜p"O=½?z„yôóÀ÷†~üÍ±²ĞÃUï³¥ÅåÆ ÎÏÆ=ä§r«ı.?“alëaí<æa*º*ººÀ¼.©?ÑĞªÕhjz8x
pæì“ùF ]}ÛÄ€”Æ=è3ü0ãg®‡ÈÏ¡µÛá¿Âš}Æ*7M)¾ãfvÃşòÕë×a‡ƒŞÁß.åQ0ò\ù±¼Gs?üpş€2šäg~³0——u@"A,%øÛM&f¦%ŠF$‘Ã6ù|Ñnæ×Êø×¼LVjLLêŞj9æ©q¹qrÑƒ[yÙ½µ·îl ¦=ÓÏ¿‰¬yOwãœ¿Í¾E»BéŒ×_¯“1Ê³İ³O GT¾ u¤$5ê×šöãëÑ:'Ç©:s0Îğ¶§ É‘-ŠVp!–em@”œ"E)Ãe*ğ÷ì£ß9xğ ğ°yĞ ‚KÄµô÷õõ•bPqeÎ¾Ø ¿¬ß%‰DlªÅùğ% öÃBŠ²€F´+â¶¶¾—Ì¸,[GÊÀß^_ö’JA‡½×²¿Cş ·çJf$ò“““DÉÉÉ¸WGã;‹Íï½OöğÔ"ÑÈe»G„ó±–¦pò öÉŒ^rM¼4:5xüävoÍHˆ"åg”°¦TŸİ«ÕÖ|Ú¨×‡ÒáÇ
ÆÓx{ö¨;Ö—\®ÌfN©”ah«ğÕw™»JÌ¤&¦¡dPë;‘ïP´æ³&  ¾¼½=J€mğ€¿üåßí2˜[°f“	ü‹Éäkd;ÜK!À%[•Rhma‹¼°Á²Ñéğ™Xƒd=e€‡¢ ”°°:7—š|€¸VÀJLŞ¤¥<)IMêŞÔ8™MT$Iù××A†™Ìèm¾HÄû$aİÏdÊSóp­XSR'æn®k›ª?¨½VıKøë¢M×=¿‰£]º¯£¤Aıù?ÉşÜÑqc.×úìèt
ô‡ïH54
pßÍ¦ß÷¨ğôæÀ 1#¢rrBJˆ6]¾ë…ÊBÑ:7 Å?ÀÒ	ÚÍ6|tğGø»O+mğ8Äc_lËÃş¾~0Ôbd@ñ¾B¢¿`I	i4Æ?@qH|ğ»„W¤Óiğ"À
)PPã‚
³½XÅ¨TFĞüSWÓTš†Ãï)1&,¶ÊOëREÄeJ¥@ƒ¥ôW”öŒí¥´ÅŠÒ±2`¥Pì]lÙASZ;„°#v”Ù.İ±4Ù%f“	îEwLÜnLö}¿SuOË©ÆÌÉÓçıù÷y#Ñ’L<Ãş~O4ŠóÏÎã"\·—’Håpç¤9d¢Š9ò]Ç£8ô]fµ©oÍà°a<mËˆ/lY[X˜w¹úCÜ²¾·8@–„8Â#¿|$cgğLæÍÈï<îàËdJ½¼r0h6k9¹şİ, U÷z¿ÅÁí[š$!¸ãN×'ãíòñ|¸¶»‚ê©hï8§‘TV ğˆ‰*AaI‰Ÿ"óšƒ€0ˆÂXúv 6ØƒAêœ—¾r¾çß_œ¡O|rR«=3¡¡'x¥56Ê®§€C"B¥PèÊØ	´‡'UDpÅTŠB¾ Ô¾é¬LUÈsÍBwÀY(>…œÄ­ÊQI{¯®âf»ÄDŒİ†¥ú`m¯Ul$üg¬""/ühùñÅCŒNÑöÙÇõ™k †§¿Û¸Û¾Šy9f‚„û ~h—µ²ø¼½^XïWıèÇ¡¨òJ!£³•¦rÈÔ%{ÀD[ß0‘âĞŒ‡g5&‰°”Í˜í”æØşßì/Ú_T<U'A æ"¦¦ —&ÙÉ;öíæk¬¾üùİË€2'(ˆ`b)¼“Ù˜ùøÿ0
ÿa[è½ô²Õ­ÕŒ²9 hXw8=¾H,¶}éêÆVlİ€Ó–h®’Îq)ï¨‘\s£Rô†!¦òùjõn¢ø¹×=aKlmê‡ğì‘#G €G¾%0½9Ì‹Ïàï(Ğ»ÄeJıŒ^/¦í^[iM½¿-=½|7@¸„[PPRŞ¤ô" uÀãÖNˆÁ !”İG%º®öŠ‰	lªt­Œ‡/ƒÂ¦Á
q÷ùÚóí'hì½ 2 4ûƒT‡>ÔLõôh44¥Õšé‰	JPCÑƒvvÂ{ „Z}'ê•Q´Lêõ½ D2ÇÙ^aY	ìÃy8Q
+Ce¸şÂ¢Ê@M*ªÿRÜQƒ;Š:q!\«‡“Fô¨tt¯ëaŒÉL¦*?_úÍî§È.8œ„s}6…ºh×ô,TÀ×ÈÈ˜]ıÃÙK€[  9¶ZùS$ï×fHômB<D56»Eaã0â¾T¬?85'½íšàÀRædl©„Íöjâèş¢cÙÙÙEÙÙH @;VÚå¥­I4Í</È ’ìØ¯”M‚o2ƒ@&(ç’ßEv\H
üß ­œ´S^İ?*—ˆ=bwqîÁå>ªèöv,¶µAºë*³É´pg<ıòéSãœàˆ IAÅœÙ:\@ä×¨†™÷…\‹$ø„=‹GîM…_Ü›pÍ»F<#×·ÆåœËş`Ãc«˜eñ¦^YÕOM«Î¨Õ}C\ÕúºÁ9”“ßÔy@ñÇº.NgïÄ8ŒÒh„ üŒk(Šn¯àW¨¯ÜÅ/ücA¾^_YYY+“ÕÒ4mš i¯½³#³Ùo§nĞ&}“ÉK[oƒ
¿zÆ*cáû0áó&Á¨†p{¼°¯P—…4˜¢ótD`F†*+ËàsX"·;%§Ó}† àN.ªCş°ÇvJO/ãv“'ß~»<Øk,6C8>=g¬zÁ|.0 ºì^áˆQ ,~Ó(ZZa¤Ï—Ğ+ş_Ù nİ+mÔ®È¹é«ÍÇm8‚yœı¤PõU!*ZØœ4¬{syÔß/ÖÕSgêµZÒºv#­@p‡Fr±.Æg?¼ Š#«M“iÄ¶]´ªïŞ­†Êš©K–`	BrAv¼!øÃsg^.Qg!çö åfÈ	}ˆfd¨ä¸H$JJ*‰m£	úeml­˜ ÃÑÓOW¿ÜŒ,?==§eÆÜíïÃ!Ğ=ğÀ]‹¾p?ZÁÏ»^»§Ã®‡®y‹ÅƒÛ£§¦‘ÌÎ5™Ì=V9€C®W·îİ¹·ÖNÁ™Jı7­§'^/Ï:ÔÖV&kmşíyâO/+bPNØ9.ŸhğB˜•ÈÕÿ?&—dä3z¬ÏÈU~ˆ8ı¢\òÛCMÑ¯ê‡ûé±9¾d2™ş1·¥¥>ÀØnÈyè €ÜÈZñã[.¦€è¨‘ƒRÏlHäî‡0Ì…|Ğ‚ Ä&LKµ8G´jnùÉO¯ß¾~ \MLÄÀk<<–¡+ Àâ*·ôö4ÇxŠ DïI?xûDI|õìÙmˆK±í³Œmm ;Ğrnÿ·Û*iAMM(¼e*6´Aà&#şØìÆÆAƒ‹ÛOëê ºµÃ·Q Àã²Ü\Ìı¼u¢»©/ûW Øù€iÕK?Ä¥[v1ÿC[FÎUšÊ8P°‚l†‘ü8ˆ@lô 4«~Ÿ‚x%Ù€m©.9`	 øˆ1>ßÚŠ@Ü…¢M…m¡3ÛÄ¯Üwıs£%á† àƒÈzSÓíÕ§Æœ¤” dËS£ Àé‘§ÓE¼8FÂ}Ì®…×g-kÎµşW?üÂkpÙ<s¶ê¼ Àá¶ª¬*µ~°¢¶Vl ê[7çz”Û¬T–Éd–5çYoè €r9Æ`¾ Ø)·¶Ë%ÔííVõnÂ;¼®À«œuÿ#“„÷äıwF[÷ïßö×ŸÿùìÙ÷ßG#«Ugè"pY#3üî1¥¬¬,ï@_[ÙÇyeeJ¥ğ_Öš•‘˜U¬„kllL,V6	æ@Š'"Z˜Ì0dS³D-ã\j•ÊÇÖœ7sŒËOşóöí[lbÿ´Œ‘¸7O§ëãCØK6İ@(½===ù @ë!£ØÄõ—Ó>Ò†pıÑóçd‡Ë¥k¤!3™ÍÄcƒtnÏ,°)ì~BW'-a0QuOH_ü”¹Nºx±î¨DÒ~Â‹…ˆ=HuA&ÓÍ0Ú0AÎËÆ>Lç9¨‚y_Jhù
É”èeÒïV3Âä¸¢@‡¤·_8ÚÜšR¿BaÔÁ<a° [¶z@à/£PkD6£Qğ1Å¢ØŠefºn•s‹şwÜŸ–‰Gİé{2EÜÛ/q•ß{ &¥¢X¬=™)¸-Ó³0LaÆ7¿6pMYægP’„C†›~Ùµ+•Ã!eS½BÎ·vÑƒ´W/ÍÉêÓ×ÊèŠÚ
´šTV¹£¨'¥½2%„Ğ6„à˜›0„å¤áËuö	ZcÕhÔòğwü¼pá«}	ÉŒÀ-m×$iÍÀ?ü×›7oàçîgøÌ%óÅcİcğ)†›V@`2›øcdnÍØÛË ü1—óåúf”Ş³X™¤ñ—ÃRõ¿øUçÓôÆñt¶]DhõXïP´Í¬HÃO)Ô–– ôè–
U~Cµ$T:‹pY¥ØI‹³&ps8‰Ù±hPpÜ"S ìsœrş37ÿñÉ=Ïç[¼»´Æˆ¤â«ïçÇçùñí·^Z^ì‰"7!˜+p­B<ímúSÒø#À×pŞ¼F_ğ£$õ’š’^É1&ıîó.y=‚ w‡±¾—.†¨œè:>ñpqu‰Ù¢ö™uaEÜlİ?$Vèt 2Cµàñ‹„8çAˆc`¨µÚaõÛFøK;Üœ’RªRÑÆbğ~Íæc3Q¾èõƒ
XZJ3 2ıséé8lŒ4”ğ6(Õn1HØc³…ˆ_ˆÀXÊDQx‡Õà ‡	ëHÍ Ìnô_Ä‚§³É> Wg\n‹øƒ˜ƒÃ7,v‘ê³Ïã Ä  Ñ •¢I
“9pÀ-Õgoïåoı˜¬kmÿéF®¾èëèïÃµ|x|ªİ Šö¦óØlAº›KÉBp¡İ¬.‹ŠKõ-¾@IOÏáĞ§âúS¿ES¨G e$kLÄ!‰h«$ ƒõİ5ùfŸ¯¸¸ä  x³±õf#
Ü“û÷f/ÜlKç²Ø<œá?˜ô¶ÖÙ3×îµµı Î€/~»ü°~@I¦•¦i$1¹GGÙY,ÅHc±ufî.Í®Â¢L†?‚à!lùÅQ„À¥aªÿÎbæª6ŠÀö’™8@ƒ{ºcú.©{4
2FøñãÍõõª»wk’7ŸøpRÏÏ3³ı<Ä©ë€à¤KS1CÚ&&Ş­.<œy·¼|œY°KÌ0P86Ÿ“İâ0Øå2yíØ8™¸ @+•òÀş*d6céQäoÛÑ•ÕpdÙ-*<4½ï Ï¨JK#Òşi8Î‹Ù	AğİG€hay»<Vh„Ó&L+
H35{} ¦a„„CÜ *&Jl2‰A˜I§ğ'×‘A`…åæÁÁóÏâ³&|]Î™¦¦E—ßí÷»ÌÅ­|ÿJ×g«‹+_:IkYá»ècÄóï+®~ Q4T}{ßàvz:0àäNux›\ÓSuä"¤}x¸¯Ééò§Ãë§ .ƒ+Î?÷Ëääd°,Ø“•ª:F_‰Ög¶Ušõ	è½{\¢Ä"=È_nna‘>ÃÚ{Dø-A­Ñ8˜ğùJ|G|eyOo6"|#—OÇs¥Ô½=9d†‚P'–Jyé³»s<î™şû¤%™4Š-¡UõR‹á!ÅbI’ñ:­™V0º¡/€@tÜp‡lØ(Qd”'AÀÄ¡‘aØx‰=èîEƒafŞy5éåûµ÷o=zôÌğÜøèøèã’ò†µÁA¼Æï• aˆÛyë©ÉÄ<4FÁ˜i÷¶Ÿ¼5ìõ~=¶@ø{7±´Ôõn%´'.„fÖÎ²³x_-„  3VéìX
î?ÆRµ­XUÊXßæfºØQ©0J©m¾lú‡lZÕœœ–¶ó0C_8ğN0 ÄD´LL1 
x¡µ8/4Ê#ÔØIÆz’!)F 6Æ¿jĞ?“+H*<À9ëtùµùòüšAf®ÂuB kÊé²ìØáŸq‰DnĞA\„é^Y±`"‹C†{-~ø¸·­â(2t[Mşx6;ï R¶ø‰â§ÚëœXÖÕ×Ñ×r8ìmÿê«öº‡¿ryb;Ë²&y5™¥ëó
õeûËz¬VmIMVe~KÆvƒ«®jÑ­)," ‚ftkğ.1 Ø] š@_C xÿö½{³³##—/_¡xÔ•²Ä-­ñ`1¤Rim¾	Ş¤,AN<›àş¨/şOiæ—NºŠÎíªM9ˆ'«:eV4Ò¡¯ğ%’OĞ‡õê    IDATsKÂ»7ƒA)Úf¨ëwğoè8qa '%G©4ûşåûH ×Öº«&ë3‘*éÔ„]©©gòo=ôì±ÇÓ~ÒCFr‰Ê¸Dryy $çx×¸¼êó±ÿ]òÁı:p·:yË hŒÂ~—ó`½İ¨·¯ô(| R¶Jù@º ‡+0) (.MÙsøğ§¡ŸÄãNº»Á&£B ò˜{}˜BÀĞo1ÈŒã&âkŠ%éµZÏ”WDÈIPN$°Ö.³™{IWûupÂá_îrïØ±Çï 
ğq®‚+n/å“Al˜ÙÀá„ñ9W+®Š"B ~Ìo½ıûHÑö0pÉMÜ©S7nàÂ8ç´ÚéÁ›’”iïkïøë[*Vm yBqeÖ?^½²I2ƒ=ú¼²ŒÌı’â@ÍİÊ§æ ^ãvNy§\ß €¹9 f ÖztÑş2 hµÆn Ğ¨	4ÊÚï£å½rº@l?[xèPaBB:‹ÇŠM••
)›…C(â<öî àoÿÛİÇ%t'~Ëªîª,)O±¤,×n©Xo¥UŸôP³Ñ$"œ‹gˆãüw¾ë·D‘ÜGÌçÄa’š¯œ±pnƒ&iğ=ásÎ½œ«’töiÖË±ví ¿DIz"óŞá“Hà¥1Bà2©Ï\Æ!KŒ+àgc×“Âéâ}r“LNÉå=ºZ¹Ø®Ãÿu¡ÔäÈVüğ³TUÕĞPî°SÔiˆbÅj³j[L ²GÄà‹Ş™––’šªŒæ,EL0Viğ0ÔÖÉşp¤l)‰A¸LµaÔ
!(p00)HSÌ¸ö|GyMïu2dõÂ—ÆP°uÏ?÷XÀãí:QÄabÂöVÅaB–™&–mÃ}”q†uÜzà¬càtõF°ÎÒ™ş×…3;‡ûênà]ğ4d,	œ®û©ëí[»ƒB )Ùà ˜™f”õìo)†,Pî\ §Qc™öô×9İ¢D´¿¹¹ú0ÂàVaP‹h1®©Ì*ÍÚk òégÎ\iLÅ¿U”°í½I® ‘´Ç²¸î&nN<}m]/€!–Ï®ûeIwÃäS[±ÉÄ“JåC
©˜2ÉĞ[Aéâ”¢€'4QdNÃŠŒ²4ájêÈÈ(¥’ƒoS¥2‚£4¬~£TúW]WÇß¯­_2	éÑ¹7ãÇ4šÔe©	!¬«#ü}½ÒÿP*]òzúpâ)K´Ğ5±´!ğ»Õ.„ğWÜhŠcCÆUDÿ½8 SÈÔğôÕb6Z§`ŠüjÈƒ9´ñ Yg¢FrâŸe¾æ1èöı HÂm ƒcãœ°«±{‰‹…â,ÒÓÎ
‰ —?€/dƒ¹Ì\¬BhR((
@$P/JÊ,VSğD
ˆ"„µ¶òúŸ?ß™ù€lÀùÛÅ'7ÛÜJÜ1…†w›F$6Ô&õYø‘¶æ%F|ÌùUWÔTz……Á]«Ğª$ÅìB"Á	^6p3EHD.áCc	 ïè²q¨â†°$qÉ‹ÁOT†™vF]¤Ba€