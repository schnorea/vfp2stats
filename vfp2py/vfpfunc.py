from __future__ import division

import builtins
import datetime as dt
import os
import sys
import types
import ctypes
import ctypes.util
import traceback
import re

import dbf

SET_PROPS = {
    'bell': ['ON', ''],
    'cursor': ['ON'],
    'deleted': ['OFF'],
    'exact': ['OFF'],
    'near': ['OFF'],
    'refresh': [0, 5],
    'status': ['OFF'],
    'status bar': ['ON'],
    'unique': ['OFF'],
}

class MainWindow(object):
    pass

class Custom(object):
    def __init__(self, **kwargs):
        self.init()

    def init(self):
        pass

    def add_object(self, obj):
        pass

class Form(Custom):
    pass

class CommandButton(Custom):
    pass

class Label(Custom):
    pass

class Array(object):
    def __init__(self, dim1, dim2=0, offset=0):
        self.columns = bool(dim2)
        self.offset = offset
        if not dim2:
            dim2 = 1
        self.dim1 = int(dim1)
        self.data = [False]*self.dim1*int(dim2)


    def _subarray(self, inds):
        def modify_slice(ind):
            def modify_slice_ind(slice_ind):
                return slice_ind - 1 if slice_ind is not None else None
            return slice(modify_slice_ind(ind.start), modify_slice_ind(ind.stop), ind.step)

        ind = modify_slice(inds)
        data = self.data[ind]
        new_array = Array(len(data), 1, ind.start)
        new_array.data = data
        return new_array

    def _get_index(self, inds):
        if not isinstance(inds, tuple):
            inds = (inds, 1)
        if len(inds) < 2:
            inds = (inds[0], 1)
        ind1, ind2 = [int(ind) - 1 for ind in inds]
        ind = (len(self) // self.dim1)*ind1 + ind2 - self.offset
        if ind < 0:
            raise IndexError('invalid indices')
        return ind

    def __getitem__(self, inds):
        if isinstance(inds, slice):
            return self._subarray(inds)
        return self.data[self._get_index(inds)]

    def __setitem__(self, inds, val):
        self.data[self._get_index(inds)] = val

    def __call__(self, *args):
        return self[args]

    def __len__(self):
        return len(self.data)

    def alen(self, arr_attr=0):
        if arr_attr == 2 and not self.columns:
            return 0
        return {
            0: len(self),
            1: self.dim1,
            2: len(self) // self.dim1,
        }[arr_attr]

    def index(self, val):
        try:
            return self.data.index(val) + 1 + self.offset
        except ValueError:
            return 0

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        dims = (self.dim1,) if self.dim1 == len(self) else (self.dim1, len(self) // self.dim1)
        return '{}({})'.format(type(self).__name__, ', '.join(str(dim) for dim in dims))


class _Database_Context(object):
    def __init__(self):
        self.current_table = -1
        self.open_tables = [{'name': None}]*10

    def _table_index(self, tablename=None):
        if not tablename:
            ind = self.current_table
        elif isinstance(tablename, (int, float)):
            ind = tablename
        else:
            tablenames = [t['name'] for t in self.open_tables]
            if tablename in tablenames:
                ind = tablenames.index(tablename)
            else:
                raise Exception('Table is not currently open')
        return ind

    def _get_table_info(self, tablename=None):
        return self.open_tables[self._table_index(tablename)]

    def _get_table(self, tablename=None):
        return self._get_table_info(tablename)['table']

    def create_table(self, tablename, setup_string, free):
        if free == 'free':
            dbf.Table(tablename, setup_string)

    def select(self, tablename):
        self.current_table = self._table_index(tablename)
        table_data = self.open_tables[self.current_table]
        if table_data['recno'] == 0:
            table_data['recno'] = min(len(table_data['table']), 1)

    def use(self, tablename, workarea, opentype):
        if tablename is None:
            if workarea is 0:
                return
            table = self.open_tables[self._table_index(workarea)]['table']
            table.close()
            self.open_tables[self.current_table] = {'name': None}
            self.current_table = -1
            return
        table = dbf.Table(tablename)
        table.open()
        if workarea == 0:
            tablenames = [t['name'] for t in self.open_tables]
            workarea = tablenames.index(None)
        self.open_tables[workarea] = {'name': tablename, 'table': table, 'recno': 0}
        self.current_table = workarea

    def append(self, tablename, editwindow):
        table_info = self._get_table_info(tablename)
        table = table_info['table']
        table.append()
        table_info['recno'] = len(table)

    def replace(self, field, value, scope):
        field = field.lower().split('.')
        if len(field) > 1:
            if len(field) == 2:
                table = str(field[0])
            else:
                table = '.'.join(field[:-1])
            field = field[-1]
        else:
            field = field[0]
            table = None
        table_info = self._get_table_info(table)
        table = table_info['table']
        recno = table_info['recno']
        record = table[recno-1]
        dbf.write(record, **{field: value})

    def skip(self, tablename, skipnum):
        table_info = self._get_table_info(tablename)
        table_info['recno'] += int(skipnum)

    def delete_record(self, tablename, scope, num, for_cond=None, while_cond=None, recall=False):
        save_current_table = self.current_table
        if not for_cond:
            for_cond = lambda: True
        if not while_cond:
            while_cond = lambda: True
        self.select(tablename)
        table_info = self._get_table_info()
        table = table_info['table']
        recno = table_info['recno']
        reccount = len(table)
        if scope.lower() == 'rest':
            records = table[recno-1:reccount]
        else:
            records = table[recno-1:recno-1+num]
        for record in records:
            if not while_cond():
                break
            if for_cond():
                if recall:
                    dbf.delete(record)
                else:
                    dbf.undelete(record)
            table_info['recno'] += 1
        table_info['recno'] = recno
        self.current_table = save_current_table

    def pack(self, pack, tablename, workarea):
        if tablename:
            table = dbf.Table(tablename)
            table.open()
            table.pack()
            table.close()
        else:
            table = self._get_table(workarea)
            table.pack()

    def reindex(self, compact_flag):
        table = self._get_table()
        table.reindex()

    def index_on(self, field, indexname, order, tag_flag, compact_flag, unique_flag):
        pass

    def close_tables(self, all_flag):
        for i, table in enumerate(self.open_tables):
            if table['name'] is not None:
                self.use(None, i, None)

    def recno(self):
        try:
            return self.open_tables[self.current_table]['recno']
        except:
            return 0

    def reccount(self):
        try:
            return len(self.open_tables[self.current_table]['table'])
        except:
            return 0

    def recsize(self, workarea=None):
        table = self._get_table(workarea)
        return table.record_length

    def bof(self, workarea=None):
        table_info = self._get_table_info(workarea)
        return table_info['recno'] == 0

    def eof(self, workarea=None):
        table_info = self._get_table_info(workarea)
        return table_info['recno'] == len(table_info['table'])

    def deleted(self, workarea=None):
        table_info = self._get_table_info(workarea)
        dbf.is_deleted(table_info['table'][table_info['recno']])

class _Variable(object):
    def __init__(self, db):
        self.public_scopes = []
        self.local_scopes = []

        self.db = db

    def _get_scope(self, key):
        if len(self.local_scopes) > 0 and key in self.local_scopes[-1]:
            return self.local_scopes[-1]
        for scope in reversed(self.public_scopes):
            if key in scope:
                return scope

    def __contains__(self, key):
        try:
            self[key]
            return True
        except:
            return False

    def __getitem__(self, key):
        scope = self._get_scope(key)
        if scope is not None:
            return scope[key]
        table_info = self.db._get_table_info()
        if table_info['name'] is not None and key in table_info['table'].field_names:
            return table_info['table'][table_info['recno']-1][key]
        else:
            raise NameError('name {} is not defined'.format(key))

    def __setitem__(self, key, val):
        scope = self._get_scope(key)
        if scope is None:
            scope = self.local_scopes[-1]
        scope[key] = val

    def __delitem__(self, key):
        scope = self._get_scope(key)
        del scope[key]

    def add_private(self, *keys):
        for key in keys:
            self.public_scopes[-1][key] = False

    def add_public(self, *keys):
        for key in keys:
            self.public_scopes[0][key] = False

    def pushscope(self):
        self.public_scopes.append({})
        self.local_scopes.append({})

    def popscope(self):
        self.public_scopes.pop()
        self.local_scopes.pop()

    def release(self, mode='Normal', skeleton=None):
        if mode == 'Extended':
            pass
        elif mode == 'Like':
            pass
        elif mode == 'Except':
            pass
        else:
            var_names = []
            for var in self.local_scopes[-1]:
                var_names.append(var)
            for var in self.public_scopes[-1]:
                var_names.append(var)
            for var in var_names:
                del self[var]


class _Function(object):
    def __init__(self):
        self.functions = {}

    def __getitem__(self, key):
        if key in self.functions:
            return self.functions[key]['func']
        for scope in variable.public_scopes:
            if key in scope and isinstance(scope[key], Array):
                return scope[key]
        raise Exception('{} is not a procedure'.format(key))

    def __setitem__(self, key, val):
        self.functions[key] = {'func': val, 'source': None}

    def __repr__(self):
        return repr(self.functions)

    def pop(self, key):
        return self.functions.pop(key)

    def set_procedure(self, *procedures, **kwargs):
        for procedure in procedures:
            module = __import__(procedure)
            for obj_name in dir(module):
                obj = getattr(module, obj_name)
                if isinstance(obj, types.FunctionType):
                    self.functions[obj_name] = {'func': obj, 'source': procedure}

    def release_procedure(self, *procedures, **kwargs):
        release_keys = []
        for key in self.functions:
            if self.functions[key]['source'] in procedures:
                release_keys.append(key)
        for key in release_keys:
            self.functions.pop(key)

    def dll_declare(self, dllname, funcname, alias):
        # need something here to determine more about the dll file.
        try:
            dll = ctypes.CDLL(dllname)
        except:
            dll = ctypes.CDLL(ctypes.util.find_library(dllname))
        func = getattr(dll, funcname)
        alias = alias or funcname
        self.functions[alias] = {'func': func, 'source': dllname}

def alias(workarea):
    pass

def alltrim(string):
    return string.strip()

def asc(string):
    return ord(string[0])

def atline(search, string):
    found = string.find(search)
    if found == -1:
        return 0
    return string[:found].count('\r') + 1

def capslock(on=None):
    pass

def cdx(index, workarea):
    pass

def chr(num):
    return __builtin__.chr(int(num))

def chrtran(expr, fchrs, rchrs):
     return ''.join(rchrs[fchrs.index(c)] if c in fchrs else c for c in expr)

def ctod(string):
    return dt.datetime.strptime(string, '%m/%d/%Y').date()

def ddeinitiate(a, b):
    pass

def ddesetoption(a, b):
    pass

def ddeterminate(a):
    pass

def ddesetservice(a, b, c=False):
    pass

def ddesettopic(a, b, c):
    pass

def delete_file(string, recycle=False):
    pass

def directory(path, flag):
    return os.path.isdir(directory)

def dtoc(dateval, index_format=False):
    if index_format == 1:
        return dateval.strftime('%Y%m%d')
    return dateval.strftime('%m/%d/%Y')

def error(txt):
    raise Exception(txt)

def fdate(filename, datetype=0):
    if datetype not in (0, 1):
        raise ValueError('datetype is invalid')
    mod_date = dt.datetime.fromtimestamp(os.path.getmtime(filename))
    return mod_date if datetype else mod_date.date()

def ftime(filename):
    return fdate(filename, 1).time()

def file(string):
     return os.path.isfile(string.lower())

def filetostr(filename):
    with open(filename) as fid:
        return fid.read().decode('ISO-8859-1')

def getwordcount(string, delim=None):
    return len(string.split(delim))

def getwordnum(string, index, delim=None):
    str_list = string.split(delim)
    if 0 <= index <= len(str_list):
        return str_list[index-1]
    return ''

def home(location=0):
    pass

def inkey(seconds=0, hide_cursor=False):
    pass

def isblank(expr):
    try:
        return not expr.strip()
    except:
        return expr is None

def lineno(flag=None):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    return exc_tb.tb_lineno

def message(flag=None):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    if flag is None:
        return exc_obj.message
    return traceback.extract_tb(exc_tb)[0][3]

def messagebox(message, flags, title):
    print(message)
    print(flags)
    print(title)

def num_to_str(num, length=10, decimals=0):
    length = int(length)
    decimals = int(decimals)
    if num == int(num):
        string = str(int(num))
        if length >= len(string):
            return ' ' * (length-len(string)) + string
        return '*' * length
    else:
        string = '{:f}'.format(num)
        integer, mantissa = string.split('.')
        if decimals:
            if len(mantissa) <= decimals:
                mantissa += '0' * (decimals - len(mantissa))
            else:
                if int(mantissa[decimals:]) > 0:
                    mantissa = str(int(mantissa[:decimals]) + 1)
                    if len(mantissa) > decimals:
                        integer += 1
                        mantissa = '0' * decimals
                mantissa = mantissa[:decimals]
            string = integer + '.' + mantissa
        else:
            string = integer
        if length >= len(string):
            return ' ' * (length-len(string)) + string
        else:
            string = '{:e}'.format(num)
            if length >= len(string):
                return ' ' * (length-len(string)) + string
            string, exp = string.split('e')
            exp = 'e' + exp
            if length <= len(exp):
                return '*' * length
            return string[:length-len(exp)] + exp

def program(level=None):
    trace = traceback.extract_stack()[:-1]
    if level is None:
        level = -1
    elif level < 0:
        return len(trace) - 1
    elif level == 0:
        level = 1
    if level >= len(trace):
        return ''
    prg = trace[level][2]
    if prg == '_program_main':
        prg = re.sub(r'.py$', '', trace[level][0])
    return prg.upper()

def quarter(datetime, start_month=1):
    if not datetime:
        return 0
    month = (datetime.month - start_month) % 12
    return (month - (month % 3)) // 3 + 1

def quit(message=None, flags=None, title=None):
    sys.exit()

def ratline(search, string):
    found = string.rfind(search)
    if found == -1:
        return 0
    return string[:found].count('\r') + 1

def reccount():
    return db.reccount()

def recno():
    return db.recno()

def recsize(workarea=None):
    return db.recsize(workarea)

def rgb(red, green, blue):
    return (red, green, blue)

def seconds():
    now = dt.datetime.now()
    return (now - dt.datetime.combine(now, dt.time(0, 0))).seconds

def space(num):
    return ' ' * int(num)

def strtofile(string, filename, flag=0):
    flag = int(flag)
    if flag not in (0, 1, 2, 4):
        raise ValueError('invalid flag')

    mode = 'ab' if flag == 1 else 'wb'

    with open(filename, mode) as fid:
        if flag == 2:
            fid.write(string.encode('utf-16'))
        elif flag == 4:
            fid.write(b'\xef\xbb\xbf')
            fid.write(string.encode('utf-8'))
        else:
            fid.write(string)

def strtran(string, old, new='', start=0, maxreplace=None, flags=0):
    retstr = ''
    while start > 0:
        try:
            ind = string.find(old) + len(old)
            retstr += string[:ind]
            string = string[ind:]
        except:
            break
        start -= 1
    if maxreplace:
        retstr += string.replace(old, new, maxreplace)
    else:
        retstr += string.replace(old, new)
    return retstr

def stuff(string, start, num_replaced, repl):
    return string[:start-1] + repl + string[start-1+num_replaced:]

def substr(string, start, chars):
    return string[start-1:start-1+chars]

def vfp_sys(funcnum, *args):
    if funcnum == 16:
        import imp
        if hasattr(sys, "frozen") or hasattr(sys, "importers") or imp.is_frozen("__main__"):
            return os.path.dirname(sys.executable)
        return os.path.dirname(sys.argv[0])

def val(string):
    return float(string)

def version(ver_type=4):
    if ver_type == 5:
        return 900

def wait(msg, to=None, window=[-1, -1], nowait=False, noclear=False, timeout=-1):
    pass

def select(tablename=None):
    if tablename is None:
        tablename = int(set('compatible') == 'on')
    if tablename == 0:
        return db.current_table + 1
    elif tablename == 1:
        try:
            return next(i+1 for i, table in enumerate(db.open_tables) if table['name'] is None)
        except:
            return 0
    else:
        try:
            db.select(tablename)
        except:
            pass
        return db.current_table + 1

def set(setword, *args, **kwargs):
    setword = setword.lower()
    settings = SET_PROPS[setword]
    if not kwargs.get('set_value', False):
        return settings[args[0]] if args else settings[0]
    if setword == 'bell':
        if args[0].lower() not in ('to', 'on', 'off'):
            raise ValueError('Bad argument: {}'.format(args[0]))
        if args[0] == 'TO':
            settings[1] = '' if len(args) == 1 else args[1]
        else:
            settings[0] = args[0].upper()
    elif setword in ('cursor', 'deleted', 'exact', 'near', 'status', 'status bar', 'unique'):
        if args[0].lower() not in ('on', 'off'):
            raise ValueError('Bad argument: {}'.format(args[0]))
        settings[0] = args[0].upper()
    elif setword == 'refresh':
        settings = args
    SET_PROPS[setword] = settings

def do_command(command, module, *args, **kwargs):
    mod = __import__(module)
    cmd = getattr(mod, command)
    cmd(*args, **kwargs)

def call_if_callable(expr):
    if callable(expr):
        return expr()
    return expr

def create_object(objtype, *args):
    pass

def clearall():
    pass

def array(arrayname, dim1, dim2=1, public=False):
    arr = Array(dim1, dim2)
    if public:
        variable.public_scopes[0][arrayname] = arr
    else:
        variable.public_scopes[-1][arrayname] = arr

db = _Database_Context()
variable = _Variable(db)
function = _Function()
error_func = None
variable.pushscope()
variable.add_public('_vfp')
variable['_vfp'] = MainWindow()
