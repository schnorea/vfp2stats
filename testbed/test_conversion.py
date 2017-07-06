from __future__ import print_function

import difflib

import vfp2py


def Test0():
    input_str = '''
LOCAL STRING_VAL, FLOAT_VAL, INT_VAL, BOOL_VAL, NULL_VAL, NULLDATE_VAL, DATE_VAL, DATETIME_VAL, OBJ_VAL
STRING_VAL = \'str\'
float_val = 3.0
int_val = 3
BOOL_VAL = .F.
NULL_VAL = NULL
NULLDATE_VAL = { / / }
DATE_VAL = {^2017-5-6}
DATETIME_VAL = {^2017-5-6 5P}
?(float_val + INT_VAL + INT_VAL + - - FLOAT_VAL + int_VAL - FLOAT_val) / ++3 / --4 * -5 - INT_VAL * 3
?CHR(3)
?CHR(INT_VAL)
?SPACE(3)
?SPACE(INT_VAL)
?DAY(DATE_VAL)
?DOW(DATE_VAL)
?\'chr(65)\' + space(1) + chr(61) + \' \' + chr(65) + \', just letting you know.\' + chr(13) + chr(10)
?2 ** 3 ** 4
?2 ** (3 ** 4)
?(((2)))
OBJ_VAL = CREATEOBJECT(\'TEST\')
OBJ_VAL = CREATEOBJECT(\'FORM\')
RELEASE STRING_VAL, INT_VAL, BOOL_VAL, NULL_VAL
'''.strip()
    output_str = '''
string_val = float_val = int_val = bool_val = null_val = nulldate_val = date_val = datetime_val = obj_val = False  # LOCAL Declaration
string_val = \'str\'
float_val = 3.0
int_val = 3
bool_val = False
null_val = None
nulldate_val = None
date_val = dt.date(2017, 5, 6)
datetime_val = dt.datetime(2017, 5, 6, 17)
print((float_val + int_val + int_val + float_val + int_val - float_val) / 3 / 4 * -5 - int_val * 3)
print(\'\\x03\')
print(chr(int(int_val)))
print(\'   \')
print(int(int_val) * \' \')
print(date_val.day)
print(vfpfunc.dow_fix(date_val.weekday()))
print(\'chr(65) = A, just letting you know.\\r\\n\')
print((2 ** 3) ** 4)
print(2 ** 3 ** 4)
print(2)
obj_val = vfpfunc.create_object(\'Test\')
obj_val = vfpfunc.Form()
del string_val, int_val, bool_val, null_val
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test1():
    input_str = '''
   *comment with spaces
#DEFINE cantbewrong
#DEFINE SPACE CHR
#IFDEF cantbewrong
#IF FILE ( \'test.h\' )
   ***comment***
   # include  test.h
   # include  \'test.h\'
   # include  \'test\' + \'.h\'
   STORE 5 to  x && set x to 5
#ELSE
#ENDIF
   x = \'test\' + CHR(13) + CHR(10)
   x = space(5)
   x = \'\' + CHR(13) + CHR(10)
#ELSE
_SCREEN.LOGO.TOP = (_SCREEN.HEIGHT-_SCREEN.LOGO.HEIGHT)/2-3

WAIT WINDOW space(3) + \'please wait\' + CHR(32) NOWAIT TIMEOUT 1.3
#ENDIF
'''.strip()
    output_str = '''
from __future__ import division, print_function

from vfp2py import vfpfunc


def _program_main():
    vfpfunc.variable.pushscope()
    # comment with spaces
    ###comment###
    vfpfunc.variable[\'x\'] = \'\\n\'
    vfpfunc.variable[\'x\'] = \'\\n\'
    vfpfunc.variable[\'x\'] = \'\\n\'
    # set x to 5
    vfpfunc.variable[\'x\'] = 5
    vfpfunc.variable[\'x\'] = \'test\\r\\n\'
    vfpfunc.variable[\'x\'] = \'\\x05\'
    vfpfunc.variable[\'x\'] = \'\\r\\n\'
    vfpfunc.variable.popscope()
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str).strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test2():
    input_str = '''
DEFINE CLASS SUBOBJ AS CUSTOM
   X = 3
   FUNCTION INIT(X)
      THIS.X = X
   ENDFUNC
ENDDEFINE

DEFINE CLASS TESTCLASS AS COMMANDBUTTON
   ADD OBJECT TEST1 as custom
   ADD OBJECT TEST2 as subobj WITH X = 4
   ADD OBJECT TEST3 as unknownobj WITH X = \'4\'
   FUNCTION INIT(X)
   ENDFUNC
ENDDEFINE
'''.strip()
    output_str = '''
from __future__ import division, print_function

from vfp2py import vfpfunc


def _program_main():
    pass


class Subobj(vfpfunc.Custom):

    def init(self, x=False):
        self.x = x
        self.x = 3


class Testclass(vfpfunc.Commandbutton):

    def init(self, x=False):
        pass
        self.test1 = vfpfunc.Custom()
        self.test2 = Subobj(x=4)
        self.test3 = vfpfunc.create_object(\'Unknownobj\', x=\'4\')
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str).strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test3():
    input_str = '''
DO A
DO A+B
DO A + B
DO ALLTRIM(A)
CD ..
'''.strip()
    output_str = '''
a._program_main()
__import__(\'a+b\')._program_main()  # NOTE: function call here may not work
__import__(a + b)._program_main()  # NOTE: function call here may not work
__import__(a.strip())._program_main()  # NOTE: function call here may not work
os.chdir(\'..\')
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test4():
    input_str = '''
LOCAL test
copy file (test) to tset
rename (test) to tset
mkdir test - test
MD test+test
rmdir (test+test)
rd alltrim(test)
'''.strip()
    output_str = '''
test = False  # LOCAL Declaration
shutil.copyfile(test, \'tset\')
shutil.move(test, \'tset\')
os.mkdir(test - test)
os.mkdir(\'test+test\')
os.rmdir(test + test)
os.rmdir(test.strip())
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test5():
    input_str = '''
continue
LOCAL SEARCH_FOR
SEARCH_FOR = \'PAUL\'
SEEK ALLTRIM(SEARCH_FOR)
RELEASE SEARCH_FOR
'''.strip()
    output_str = '''
vfpfunc.db.continue_locate()
search_for = False  # LOCAL Declaration
search_for = \'PAUL\'
vfpfunc.db.seek(None, search_for.strip())
del search_for
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test6():
    input_str = '''
MKDIR TEST
?DATE()
?PI()
'''.strip()
    output_str = '''
from __future__ import division, print_function

import datetime as dt
import math
import os


def _program_main():
    os.mkdir(\'test\')
    print(dt.datetime.now().date())
    print(math.pi)
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str).strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test7():
    input_str = '''
PUSH KEY CLEAR
PUSH KEY
POP KEY ALL
POP KEY
'''.strip()
    output_str = '''
 # FIX ME: PUSH KEY CLEAR
# FIX ME: PUSH KEY
# FIX ME: POP KEY ALL
# FIX ME: POP KEY
pass
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test8():
    input_str = '''
LOCAL X, Y
X = .F.
Y = \'failed\'
ASSERT NOT X
ASSERT X = .T. MESSAGE Y + \' ASSERT\'
'''.strip()
    output_str = '''
x = y = False  # LOCAL Declaration
x = False
y = \'failed\'
assert not x
assert x == True, y + \' ASSERT\'
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test9():
    input_str = '''
SET COMPATIBLE OFF
SET COMPATIBLE DB4
SET COMPATIBLE FOXPLUS
SET COMPATIBLE ON
SET COMPATIBLE FOXPLUS PROMPT
SET COMPATIBLE DB4 NOPROMPT
'''.strip()
    output_str = '''
vfpfunc.set(u\'compatible\', \'OFF\', set_value=True)
vfpfunc.set(u\'compatible\', \'ON\', set_value=True)
vfpfunc.set(u\'compatible\', \'OFF\', set_value=True)
vfpfunc.set(u\'compatible\', \'ON\', set_value=True)
vfpfunc.set(u\'compatible\', \'OFF\', \'PROMPT\', set_value=True)
vfpfunc.set(u\'compatible\', \'ON\', \'NOPROMPT\', set_value=True)
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test10():
    input_str = '''
APPEND FROM TABLE_NAME
APPEND FROM TABLE_NAME TYPE DELIMITED
APPEND FROM \'table\' + \'_\' + \'name\' TYPE \'Delimited\'
'''.strip()
    output_str = '''
vfpfunc.db.append_from(None, \'table_name\')
vfpfunc.db.append_from(None, \'table_name\', filetype=\'delimited\')
vfpfunc.db.append_from(None, \'table_name\', filetype=\'delimited\')
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise


def Test11():
    input_str = '''
LOCAL MYFILE, mydir
MYFILE = \'c:\\test\\test.prg\'
MYDIR = \'c:\\test\\test\\dir\'
?file(myfile)
?justdrive(MYFILE)
?justpath(MYFILE)
?justfname(MYFILE)
?juststem(myfile)
?JUSTEXT(myfile)
?FORCEEXT(myfile, \'py\')
?directory(mydir)
?justdrive(MYDIR)
?justpath(MYDIR)
?justfname(MYDIR)
?juststem(mydir)
?JUSTEXT(mydir)
?FORCEEXT(mydir, \'py\')
?ADDBS(MYDIR) + \'dir1\'
?ADDBS(ADDBS(MYDIR) + \'dir1\') + \'dir2\'
?ADDBS(ADDBS(ADDBS(MYDIR) + \'dir1\') + \'dir2\') + \'dir3\'
RELEASE MYFILE, MYDIR
'''.strip()
    output_str = '''
myfile = mydir = False  # LOCAL Declaration
myfile = \'c:\\\\test\\\\test.prg\'
mydir = \'c:\\\\test\\\\test\\\\dir\'
print(os.path.isfile(myfile))
print(os.path.splitdrive(myfile)[0])
print(os.path.dirname(myfile))
print(os.path.basename(myfile))
print(os.path.splitext(os.path.basename(myfile))[0])
print(os.path.splitext(myfile)[1][1:])
print(os.path.splitext(myfile)[0] + \'.\' + \'py\')
print(os.path.isdir(mydir))
print(os.path.splitdrive(mydir)[0])
print(os.path.dirname(mydir))
print(os.path.basename(mydir))
print(os.path.splitext(os.path.basename(mydir))[0])
print(os.path.splitext(mydir)[1][1:])
print(os.path.splitext(mydir)[0] + \'.\' + \'py\')
print(os.path.join(mydir, \'dir1\'))
print(os.path.join(mydir, \'dir1\', \'dir2\'))
print(os.path.join(mydir, \'dir1\', \'dir2\', \'dir3\'))
del myfile, mydir
'''.strip()
    test_output_str = vfp2py.vfp2py.prg2py(input_str, parser_start='lines', prepend_data='').strip()
    try:
        assert test_output_str == output_str
    except AssertionError:
        diff = difflib.unified_diff((test_output_str + '\n').splitlines(1), (output_str + '\n').splitlines(1))
        print(''.join(diff))
        raise

