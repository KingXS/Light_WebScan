#!/usr/bin/env python2

"""
Copyright (c) 2006-2019 sqlmap developers (http://sqlmap.org/)
See the file 'LICENSE' for copying permission
"""

import os

from lib.core.agent import agent
from lib.core.common import checkFile
from lib.core.common import dataToStdout
from lib.core.common import Backend
from lib.core.common import isStackingAvailable
from lib.core.common import readInput
from lib.core.common import unArrayizeValue
from lib.core.compat import xrange
from lib.core.data import conf
from lib.core.data import logger
from lib.core.data import queries
from lib.core.enums import DBMS
from lib.core.enums import CHARSET_TYPE
from lib.core.enums import EXPECTED
from lib.core.enums import OS
from lib.core.exception import SqlmapFilePathException
from lib.core.exception import SqlmapMissingMandatoryOptionException
from lib.core.exception import SqlmapUnsupportedFeatureException
from lib.core.exception import SqlmapUserQuitException
from lib.core.unescaper import unescaper
from lib.request import inject

class UDF:
    """
    This class defines methods to deal with User-Defined Functions for
    plugins.
    """

    def __init__(self):
        self.createdUdf = set()
        self.udfs = {}
        self.udfToCreate = set()

    def _askOverwriteUdf(self, udf):
        message = "UDF '%s' already exists, do you " % udf
        message += "want to overwrite it? [y/N] "

        return readInput(message, default='N', boolean=True)

    def _checkExistUdf(self, udf):
        logger.info("checking if UDF '%s' already exist" % udf)

        query = agent.forgeCaseStatement(queries[Backend.getIdentifiedDbms()].check_udf.query % (udf, udf))
        return inject.getValue(query, resumeValue=False, expected=EXPECTED.BOOL, charsetType=CHARSET_TYPE.BINARY)

    def udfCheckAndOverwrite(self, udf):
        exists = self._checkExistUdf(udf)
        overwrite = True

        if exists:
            overwrite = self._askOverwriteUdf(udf)

        if overwrite:
            self.udfToCreate.add(udf)

    def udfCreateSupportTbl(self, dataType):
        debugMsg = "creating a support table for user-defined functions"
        logger.debug(debugMsg)

        self.createSupportTbl(self.cmdTblName, self.tblField, dataType)

    def udfForgeCmd(self, cmd):
        if not cmd.startswith("'"):
            cmd = "'%s" % cmd

        if not cmd.endswith("'"):
            cmd = "%s'" % cmd

        return cmd

    def udfExecCmd(self, cmd, silent=False, udfName=None):
        if udfName is None:
            udfName = "sys_exec"

        cmd = unescaper.escape(self.udfForgeCmd(cmd))

        return inject.goStacked("SELECT %s(%s)" % (udfName, cmd), silent)

    def udfEvalCmd(self, cmd, first=None, last=None, udfName=None):
        if udfName is None:
            udfName = "sys_eval"

        if conf.direct:
            output = self.udfExecCmd(cmd, udfName=udfName)

            if output and isinstance(output, (list, tuple)):
                new_output = ""

                for line in output:
                    new_output += line.replace("\r", "\n")

                output = new_output
        else:
            cmd = unescaper.escape(self.udfForgeCmd(cmd))

            inject.goStacked("INSERT INTO %s(%s) VALUES (%s(%s))" % (self.cmdTblName, self.tblField, udfName, cmd))
            output = unArrayizeValue(inject.getValue("SELECT %s FROM %s" % (self.tblField, self.cmdTblName), resumeValue=False, firstChar=first, lastChar=last, safeCharEncode=False))
            inject.goStacked("DELETE FROM %s" % self.cmdTblName)

        return output

    def udfCheckNeeded(self):
        if (not conf.fileRead or (conf.fileRead and not Backend.isDbms(DBMS.PGSQL))) and "sys_fileread" in self.sysUdfs:
            self.sysUdfs.pop("sys_fileread")

        if not conf.osPwn:
            self.sysUdfs.pop("sys_bineval")

        if not conf.osCmd and not conf.osShell and not conf.regRead:
            self.sysUdfs.pop("sys_eval")

            if not conf.osPwn and not conf.regAdd and not conf.regDel:
                self.sysUdfs.pop("sys_exec")

    def udfSetRemotePath(self):
        errMsg = "udfSetRemotePath() method must be defined within the plugin"
        raise SqlmapUnsupportedFeatureException(errMsg)

    def udfSetLocalPaths(self):
        errMsg = "udfSetLocalPaths() method must be defined within the plugin"
        raise SqlmapUnsupportedFeatureException(errMsg)

    def udfCreateFromSharedLib(self, udf=None, inpRet=None):
        errMsg = "udfCreateFromSharedLib() method must be defined within the plugin"
        raise SqlmapUnsupportedFeatureException(errMsg)

    def udfInjectCore(self, udfDict):
        written = False

        for udf in udfDict.keys():
            if udf in self.createdUdf:
                continue

            self.udfCheckAndOverwrite(udf)

        if len(self.udfToCreate) > 0:
            self.udfSetRemotePath()
            checkFile(self.udfLocalFile)
            written = self.writeFile(self.udfLocalFile, self.udfRemoteFile, "binary", forceCheck=True)

            if written is not True:
                errMsg = "there has been a problem uploading the shared library, "
                errMsg += "it looks like the binary file has not been written "
                errMsg += "on the database underlying file system"
                logger.error(errMsg)

                message = "do you want to proceed anyway? Beware that the "
                message += "operating system takeover will fail [y/N] "

                if readInput(message, default='N', boolean=True):
                    written = True
                else:
                    return False
        else:
            return True

        for udf, inpRet in udfDict.items():
            if udf in self.udfToCreate and udf not in self.createdUdf:
                self.udfCreateFromSharedLib(udf, inpRet)

        if Backend.isDbms(DBMS.MYSQL):
            supportTblType = "longtext"
        elif Backend.isDbms(DBMS.PGSQL):
            supportTblType = "text"

        self.udfCreateSupportTbl(supportTblType)

        return written

    def udfInjectSys(self):
        self.udfSetLocalPaths()
        self.udfCheckNeeded()
        return self.udfInjectCore(self.sysUdfs)

    def udfInjectCustom(self):
        if Backend.getIdentifiedDbms() not in (DBMS.MYSQL, DBMS.PGSQL):
            errMsg = "UDF injection feature only works on MySQL and PostgreSQL"
            logger.error(errMsg)
            return

        if not isStackingAvailable() and not conf.direct:
            errMsg = "UDF injection feature requires stacked queries SQL injection"
            logger.error(errMsg)
            return

        self.checkDbmsOs()

        if not self.isDba():
            warnMsg = "functionality requested probably does not work because "
            warnMsg += "the current session user is not a database administrator"
            logger.warn(warnMsg)

        if not conf.shLib:
            msg = "what is the local path of the shared library? "

            while True:
                self.udfLocalFile = readInput(msg)

                if self.udfLocalFile:
                    break
                else:
                    logger.warn("you need to specify the local path of the shared library")
        else:
            self.udfLocalFile = conf.shLib

        if not os.path.exists(self.udfLocalFile):
            errMsg = "the specified shared library file does not exist"
            raise SqlmapFilePathException(errMsg)

        if not self.udfLocalFile.endswith(".dll") and not self.udfLocalFile.endswith(".so"):
            errMsg = "shared library file must end with '.dll' or '.so'"
            raise SqlmapMissingMandatoryOptionException(errMsg)

        elif self.udfLocalFile.endswith(".so") and Backend.isOs(OS.WINDOWS):
            errMsg = "you provided a shared object as shared library, but "
            errMsg += "the database underlying operating system is Windows"
            raise SqlmapMissingMandatoryOptionException(errMsg)

        elif self.udfLocalFile.endswith(".dll") and Backend.isOs(OS.LINUX):
            errMsg = "you provided a dynamic-link library as shared library, "
            errMsg Çÿ'Ñ.ÿ€¼²[ ö—ş•|
Úı Ğí"¾[  øÿimåäÿ Ğ-«Ê[  øÿ¨¡K€ÿ ĞNıÖ[  øÿñØû Ğ;â[  øÿõs<ş Ğ
(ì[  øÿd¼¬ÿ ĞÎ,÷[  X ÚÉú Ğrp@  øÿzg.Æÿ ĞÚ¡\  øÿ¹GÇƒÿ Ğ
u\  øÿ|<1¬ÿ ĞÅ|\  øÿ;”nà PY'\  øÿÈ=å/û ĞÈÑ'\  øÿ)g³» Ğqı¿> ä³5É(<Hş Ğ_ş3\  øÿcGFbÿ Ğ£P?\  øÿ]é9ü ĞÌI\  øÿL^ş Ğ9Q\  øÿ\Cšÿ Ğ¹]\  ò1ùÿ Pş ĞÕ«i\ øóÿSOèµ Ğí,¿>  X ‚ˆ Éú ĞÃ«@  X 0nÉú Ğ·@  øÿô>†wÿ Ğu/u\  øÿ|kÎÿ ĞÂm\  øÿ Am”ÿ Ğ¾è\  øÿØ~}+ÿ ĞM7™\  øÿ =<Ùÿ ĞÀµ¥\  øÿ3ÈÓ‰ÿ Ğ6Œ±\  øÿ‚«« ÿ Ğ½\  øÿ—ÿ ĞqÉ\  øÿRËÎÿ ĞÕ\ êR3øAV0 ĞÉ²õE êS5Ñ–Äÿ€·
Vá\ Å£7ğ!û›ÿ Ğ¸í\  øÿÙNY¥ÿ Ğ®gù\  øÿ¾¦ïÿ Ğ3]  øÿC{Ôÿ Ğw]  øÿòÈ-”ÿ Ğ}«]  øÿ“
Öı Ğ,É(]  øÿvú« ÿ Ğ^ 4]  øÿm‹ì Ğ¡¿> Øt6µÁhÇÿÀ³J@] ±ôÿ¼€Ã ĞØÚõE öÿB9 Ğ éõE ¡õÿ©Ó¬ ĞĞõE Áõÿ›J¯ Ğ˜&õE ºôÿ¹º Ğ	õE Bõÿø·‹ Ğ„{õE Bõÿ¹ÂH Ğ*yõE RõÿÍDÈO ĞÀkõE rõÿ‹ßÙ Ğ—RõE £ôÿòÄÄ9 Ğ»åõE ¯ôÿIéHr ĞXöõE bõÿÔšëà Ğ 8õE ¼ôÿØ£Vn ĞM„õE ­ôÿĞ›By ĞæVõE ¡õÿàÄF% ĞõE bõÿe$|ö ĞûŒõE öÿxµˆ Ğâ_õE ¡õÿLERİ ĞìsõE RõÿÛÔã ĞI¶õE óõÿj¾p ĞüõE £ôÿ¦vÒÒ ĞŒ•õE Åôÿ¯G+ë Ğ¡ÁõE bõÿÆóı ĞĞ
õE bõÿĞÌÄ{ ĞÚõE ±õÿ"@ss ĞtœõE ¸ôÿ)‚Æš Ğ‰õE öÿŸkº‹ ĞõE #öÿÜïCr ĞhÎõE °ôÿ7Œ’ ĞâõE ¿ôÿo;M Ğ1˜õE ÁõÿùW€¬ ĞNòõE öÿ ik¾ ĞëVõE RõÿÛr·¸ ĞºRõE Rõÿ‡¨ ĞÇ©õE RõÿI-ì Ğ±õE Rõÿà¹Ø Ğ¹™õE ‘õÿáú{ Ğ‹SõE Rõÿºœ	 Ğ¯˜õE ±õÿÂË±e Ğk8õE ‘õÿ…’ Ğ=õE Rõÿl˜ Ğ|ZõE ©ôÿ¿ Ğs~õE Bõÿ#ú®æ Ğ†õE bõÿYÅC Ğ¹ÕõE öÿ×¶…( ĞƒõE ­ôÿ™4P Ğİ0õE Bõÿnò¼$ ĞN(õE RõÿO9Ÿ9 ĞeõE öÿã-/ ĞØoõE Rõÿda—¢ ĞËYõE ¯ôÿ	<Ÿü ĞcäõE xs0ÃCÈÏÿÀ«sÃL]  øÿu€UÔÿ ĞL€X]  øÿ¸Å¹‡ÿ Ğíd] ç‡õËìYzñ Ğ9To  øÿÄ,Q›ÿ Ğ3¿o] D³5ŞÌ|Æÿ@¶CÁw] *S3ídVé ĞŒÍƒ] "Ô5YFÿ Ğä ]  øÿ$Ê×Óÿ Ğ¯Ú›]  øÿÃ¹„Eú Ğ¸©§]  øÿ§Uùİÿ Ğœ{³]  øÿÅvÑØÿ ĞÜ´¿]  øÿ6şêÿ ĞşË] ‚Ó5¹Œ>Åÿ@·=à×]  øÿãZHXÿ Ğ„
ã]  øÿ3ËÉÿ ĞDï]  øÿÂë—Äÿ ĞD û]  øÿt²§“ÿ Ğ˜ø^  øÿCÂÇı Ğ`‚^  øÿH›§ù Ğ€^ 3mr²ØÿÀ£È+^  øÿ½hì’ÿ Ğbˆ7^  øÿ3<Wÿ ĞiİC^  øÿ-¬ ‚ş ĞP:O^  øÿ^jáÿ Ğ*[^  øÿlƒíÿ Ğ5Æg^  ğÿK[y Ğ,©õE  øÿDĞt PÈœs^ ”ôÿf#ÅF ĞÂ¿>  X >üÉú ĞœÚ@  ğÿZ1¤H Ğµ™¿>  H >Éú ĞiÕ@ ÿ2•a¿û Ğ6k^ Xs4°f¨šÿ Ğ¢‡‹^ ¼28ÖÄ¼ÿ ½ë…‹^ ºS6~&†’ÿ Ğ§š—^ Ùb2Â§Äÿ@®	ì£^ 9# ²Øÿ` Ş¯^  X ¦-o.ú ĞãÕö<  X T«Lú Ğ,Uö< ÚR4ßÑFö Ğ”Â»^ éc5œ×Äÿ€µ‡Ç^ æ—ÿ~zI Ğ
\¿> Ó1zÒ¾nş ĞpÓ^  X ï_.ú Ğqö< õÿQw Ğ"õE ş§üãØ-å Ğ¦ü¿>  øÿ|èÅÿ Ğyaß^  øÿ¨^øı Ğ·å¿>  øÿ­]=¤ÿ ĞÕ‘ë^  øÿ¼bˆ·ÿ Ğ%,÷^  øÿ¶·^±ş ĞÅÌ÷^ f“5ëuZÄÿ`¸–¿_ Œ45ÿ¾”-  ĞĞŠ_ Aã)ô{ß~ÿ Ğås_  øÿ¥ÿ ĞW'_  øÿ<y¤ÿ ĞÓ‚3_  øÿCéVÿ Ğì±?_ Hu5n¾Ø˜ ĞòWK_  øÿÈ‹§°ÿ Ğ·^W_  øÿç[ Ê Ğ2Ço  øÿÑ_ ĞV‰¿>  øÿùZ^±ş ĞFqc_  øÿş¸Ìÿ ĞWeo_  X Ç™ÿ ĞH­z_  X :cÉú Ğ¥@  X ê½[.ú ĞWö<  X Ésïí Ğ»‡<>  X 0ûÈú Ğq@@  øÿìFóÓÿ ĞR„_  øÿj¯ı Ğóh_  øÿÄ`+îş Ğ¹…œ_  øÿƒ=‚ƒÿ Ğ‹¢¦_  øÿÎ„†ÿ ĞìQ²_  øÿ@5ÿ Ğy‘¾_  øÿ¢¬€ÿ ĞD¾Ê_  øÿºÚÃÿ Ğ §Ö_  øÿ–&–ş Ğà=â_  øÿì<Ecş Ğ7xî_  øÿ_+½ÿ Ğ`áú_  øÿ)¯¨šÿ Ğ¢‡‹^  X ©…©Lú ĞQhö<  ğÿØp²Åí Ğš¿>  øÿ¶Åÿ Ğì'`  øÿ
œ Éÿ ĞRu`  øÿ±û²Øÿ Ğâ-`  øÿåÖp] Ğî¿>  X ºYâô ĞÜxö<  øÿ«gW§ÿ ĞÓc*`  X Šà$Éú ĞœÍ@  X w‚Éú ĞŠ@  X .Pº÷ Ğ¡Ãö<  X ûHú ĞmNö<  X Òº÷ ĞÀö<  ğÿ‚BÇ ĞBÁ¿>  ğÿ¢˜  ĞÎ®¿>  øÿà	¬ P´v4`  øÿP¨b–ş ĞÊ´@` ZS4ŠÒ& Ğ«õE  øÿBÈöş ĞrïL`  ğÿ™)Á- Ğë»õE  øÿ01[Äÿ ĞJÉX`  øÿËÂÿÀÇ[d` /3 FÑ±ı Ğjp` b÷ÿCxL Ğ‰¬õE R÷ÿİ.IZ ĞG¦õE  øÿ68&û ĞÕ	o  øÿdëÁÿ Ğ':|`  øÿ5cÑ¤ÿ Ğaˆ` ±ä6Ï Ğfş”`  øÿÍA Ğ65¿> õÿ„ , Ğ;éõE ¥£7µfß Ğ0h ` :S.ëvÅÿ ² `  øÿm‰raş ĞrI«`  øÿıe›ÿ Ğ<ç¶` †”9²úÙÿ€L™Â` ,37”’ÿ ĞÏİÂ` BÔ5eÇ>dÿ Ğm£Í` êS9{‹]ÿ Ğ@iÙ`  X -DQ.ú Ğ÷ö<  øÿ²Ñ“£ Pãå`  øÿğ9´ Ğuñ`  øÿÃ§I" ĞÖuY  øÿiÊı Ğ©±ñ`  X ÙZ-Èì ĞZû<>  øÿ=Xxaş Ğµ}ı`  øÿ3„Ñdş ĞÎZo  øÿÅü@ş Ğ«a  øÿû%'Gÿ ĞiÙa  øÿÓY+Sÿ ĞÌ†a  øÿ³ÒÆÿ ĞÙ`'a  øÿ .ÿ Ğ~2a  øÿFÈÑ Ğ*3¿>  øÿ¶âÏØÿ Ğwì>a  øÿÀÀ5ş ĞˆÎIa  øÿÖÖ =ÿ Ğ•Ua  Iñ/âj Ğ[×_a JS5(5Vºÿ`¾æwka  øÿ=hzş Ğñwa  øÿixÆkş Ğ³ƒa  øÿ¬•Šÿ Ğ—Şa 7…4MÔiO Ğ…”ša ‰f9Ww©ÿ Ğóša 5£6xƒ+Ïÿ ­j©¥a 2Õ6h®ÿ Ğ*G¥a =#8„3Ãÿ Ğï°a 9d0¼NGBş Ğ¼’»a N3U“r«ş ĞM$Æa  øÿÊÃ(©ÿ Ğ‘PÒa Ä2ÉMMWÿ Ğ}İa  øÿú*Øÿ Ğã8éa  øÿŒà;Äş ĞÛMôa ô6¹p„ÿ Ğƒeÿa êR7åV¶ÿÀÆ4K
b égÿï8w  ĞÚwo  €e¯ Ğÿs…7ôb xÀ‹;ˆ¯ÿù„Ä4"b  ğÿ¹iÙ ĞŠÙ¿> jS5‘üöÿ Ğ‘,b Õ6aön5ÿ ĞrN7b qã4Aö/€ÿ ĞzœCb KC-É¯ÕÀÿà»åŒ7b ÂÓ5}>‡ÿ Ğ÷şOb #2Êøã{ÿ Ğ Ob %£3£–[aş Ğ#Zb n9±ò^ş ĞWBZb  ğÿµ ĞßŸ¿>  øÿÚÕ”·ÿ Ğ›šôa  øÿmıØÿ Ğ*«eb  øÿõÒò¤ş Ğgâpb  øÿ©qP  Ğ®o €ó5eÌàÿ Ğ"|b  øÿ#& x P¤Î‡b …ôÿLW)_ Ğ%¿>  øÿ6Üş2ÿ ĞS“b  øÿâÏîKÿ Ğx$Ÿb  øÿÏ†æ±ÿ ĞÇç«b  øÿ>jÀÿ Ğ”~·b  øÿ^á.oÿ ĞÛ?Ãb  øÿYK· Ğê¿> ùgşŠş'ı ĞYY¿> /9š`1Õÿ §~/Ïb 1ã4€ïzÿ Ğx_Úb ü4:)„Ãÿ€·Ö‘æb ‚Ò3Ù-ş2ÿ Ğ9ïòb  øÿU€İšı Ğ­şb ƒÂ5ZÇ=ãş Ğwc
c  øÿB& Pœ•c  øÿm	¿ù Ğ~Zc õ§şwÃ‹" P‚š!c ×—ş+ú4¤ Ğ¿>  øÿËI\bş Ğ¿7-c ¿6Á]ş Ğèà8c  øÿ²’ÿ ĞkrCc  øÿãíçş ĞÒóOc  øÿå¯ó¹ÿ ĞÄ$[c  øÿÁZzÿ Ğÿ§fc  øÿ ¼ò†ÿ Ğr7rc  øÿ×Áâ©ÿ Ğõ~c  øÿ›ÉŸ«÷ Ğ'Šc  øÿ >+¬ı Ğe –c KD|’5Æÿ€µÔD¢c ­#3H Ó×ÿ€¤-†®c ºR0rƒ¦ìÿ ¦œ¹c ès3ªxÿ Ğ ¹c  øÿGŸuÿ ĞoóÄc  øÿcâ©ÿ ĞnöĞc 7ƒ8xöI|ÿ Ğé0Üc ô²4æì^ş Ğ
çc ;C2÷Š¥tÿ Ğ)Úòc  øÿó{ Íı ĞëÓıc  øÿ¡÷ÛÏÿ Ğ_ã	d  øÿF›)ü ĞğQd  øÿò@‚¤ş Ğ‘c d ËB5àµ±ÿ€Ë¬§,d RÕ8y*®tÿ Ğ|õ8d aä5yÊ_ª÷ Ğ¨Dd ƒşf$©— Ğs+¿>  øÿK H§ÿ ĞÕ'Pd  øÿ[ÓHĞÿ Ğ%ÿ[d  øÿ]nŒVü Ğ@§gd $7u=Ó×ÿ ¤20rd (t9Í#Ø«ÿ Ğ”ˆ}d  øÿ®øÌø Ğ ö¿>  øÿ€J´[ÿ ĞMÚˆd  øÿc¤8Õş Ğær”d å7áp_¨÷ Ğ_ÌŸd áâ3fc¿uÿ ĞÕ¸«d \36ã„˜ş ĞÀ¹·d  øÿMÿ Ğp¢Ãd  øÿ•q'©ÿ Ğ00Ïd  øÿXî[ÿ Ğ÷ÄÚd  øÿNx*iş ĞÈGåd  øÿÊ€ªü ĞÀñd  øÿxù¦{ÿ Ğğ<ıd üòÿÓİ6# Ğ*æ¿> ºR8ä5æ]ÿ Ğ\Èe ’Õ: ¼.ÿ Ğv)e ¡â/øßuÿ Ğ“R e  øÿv¼­?ÿ Ğâ(,e  øÿMf¹ P”7e ‡„1t5Ùøş Ğ*·Ce  øÿëµpş ĞAßNe è÷ÿÅc  Ğ}	Ne  øÿ­Ñ-« Ğç¿>  ğÿ*ÉNa Ğ8¿> ëGÿ?‚U< Ğö Ye "ãü¨‡ Ğù¿>  øÿÖÈIÿ Ğüúbe 9d4*M§¶ÿ ÅŞme ƒ5ó¹ÿ ĞÀxe :óÿ{Gğ ĞeD¿> úT4_“fòş ĞÎ†ƒe  øÿ «
 PßÃe  øÿ/Í’ş Ğ¼"o  øÿ@·uÿ ĞµZše  øÿb?¦÷ Ğø%¦e  øÿšòÛZÿ Ğ
 ²e  øÿ‰ô‰ğş ĞO½e ¾6›şb¯ÿàÌ%ÇÈe Qã8ŠWOuÿ Ğs:Ôe  øÿjĞ ‹ÿ Ğ0Úàe  øÿ¢vZÿ Ğy ëe  øÿŸ®²¡ş Ğ‚Áöe  øÿ&kú”ş Ğ/bf  øÿ¬ªMlû ĞÎÛf  øÿ‚°ü Ğ2Áf  øÿ÷d‡ÿ ĞŞ&f  øÿÃö­ÿ Ğ1f qã2‡Ù/tÿ Ğş\<f ;C6ü}E×ÿ€¥şHf  øÿÓjµ{	 Ğ}A¿>  øÿh%Hş Ğ½#Sf  øÿ`à$Ğÿ ĞkÈ^f  øÿz_sÿ ĞZif  øÿÜ‚%Âÿ ĞuÇuf  øÿÔo‡ÿ ĞÊïf  øÿáJ¦6 Ğƒšf  øÿ’¾UÒÿ Ğå„f  øÿèm™fÿ Ğååf  øÿˆÕ0Òş Ğ‹Hf  øÿŞ€&½ÿ Ğ"1f ºS4ùª4ÿ Ğ×·™f  øÿHZ»Şÿ Ğ£j¤f ó2I”pƒÿ Ğ'¡¯f  ó7}½@Èÿ ´j¶¯f o7ÓDñÃÿ ¸–ºf ˜s4Ğ†H“ P³uÅf  ø