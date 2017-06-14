from __future__ import print_function

import os
import ntpath
import time
import re
import tempfile
import shutil

import dbf

import antlr4

import autopep8

from VisualFoxpro9Lexer import VisualFoxpro9Lexer
from VisualFoxpro9Parser import VisualFoxpro9Parser
from VisualFoxpro9Visitor import VisualFoxpro9Visitor

from vfp2py_convert_visitor import PythonConvertVisitor

SEARCH_PATH = ['.']

def which(filename):
    '''find file on path'''
    for path in SEARCH_PATH:
        testpath = os.path.join(path, filename)
        if os.path.isfile(testpath):
            return testpath
    return filename

class Tic():
    def __init__(self):
        self.start = time.time()

    def tic(self):
        self.start = time.time()

    def toc(self):
        return time.time()-self.start

class CodeStr(unicode):
    def __repr__(self):
        return unicode(self)

    def __add__(self, val):
        return CodeStr('{} + {}'.format(self, repr(val)))

    def __sub__(self, val):
        return CodeStr('{} - {}'.format(self, repr(val)))

    def __mul__(self, val):
        return CodeStr('{} * {}'.format(self, repr(val)))

class PreprocessVisitor(VisualFoxpro9Visitor):
    def __init__(self):
        self.tokens = None
        self.memory = {}

    def visitPreprocessorCode(self, ctx):
        retval = []
        for child in ctx.getChildren():
            toks = self.visit(child)
            if toks:
                retval += toks
            elif toks is None:
                print('toks was None')
        return retval

    def visitPreprocessorDefine(self, ctx):
        name = ctx.identifier().getText().lower()
        namestart, _ = ctx.identifier().getSourceInterval()
        _, stop = ctx.getSourceInterval()
        tokens = ctx.parser._input.tokens[namestart+1:stop]
        while len(tokens) > 0 and tokens[0].type == ctx.parser.WS:
            tokens.pop(0)
        self.memory[name] = tokens
        return []

    def visitPreprocessorUndefine(self, ctx):
        name = ctx.identifier().getText().lower()
        self.memory.pop(name)
        return []

    def visitPreprocessorInclude(self, ctx):
        visitor = PythonConvertVisitor('')
        visitor.scope = {}
        filename = visitor.visit(ctx.specialExpr())
        if isinstance(filename, CodeStr):
            filename = eval(filename)
        filename = which(filename)
        include_visitor = preprocess_file(filename)
        self.memory.update(include_visitor.memory)
        return include_visitor.tokens

    def visitPreprocessorIf(self, ctx):
        if ctx.IF():
            visitor = PythonConvertVisitor('')
            visitor.scope = {}
            ifexpr = eval(repr(visitor.visit(ctx.expr())))
        else:
            name = ctx.identifier().getText().lower()
            ifexpr = name in self.memory
        if ifexpr:
            return self.visit(ctx.ifBody)
        elif ctx.ELSE():
            return self.visit(ctx.elseBody)
        else:
            return []

    def visitNonpreprocessorLine(self, ctx):
        start, stop = ctx.getSourceInterval()
        hidden_tokens = ctx.parser._input.getHiddenTokensToLeft(start)
        retval = []
        process_tokens = (hidden_tokens if hidden_tokens else []) + ctx.parser._input.tokens[start:stop+1]
        hidden_tokens = []
        for tok in process_tokens:
            if tok.text.lower() in self.memory:
                retval += self.memory[tok.text.lower()]
            else:
                if tok.type == ctx.parser.COMMENT:
                    tok.text = '*' + tok.text[2:] + '\n'
                    hidden_tokens.append(tok)
                    continue
                elif tok.type == ctx.parser.LINECOMMENT:
                    if tok.text.strip():
                        tok.text = re.sub(r';[ \t]*\r*\n', '\n', tok.text.strip())
                        lines = tok.text.split('\n')
                        lines = [re.sub(r'^\s*\*?', '*', line) + '\n' for line in lines]
                        tok.text = ''.join(lines)
                retval.append(tok)
        return hidden_tokens + retval

def add_indents(struct, num_indents):
    retval = []
    for item in struct:
        if isinstance(item, list):
            retval.append(add_indents(item, num_indents+1))
        elif item:
            retval.append(' '*4*num_indents + repr(item))
        else:
            retval.append('')
    return '\n'.join(retval)

def preprocess_code(data):
    input_stream = antlr4.InputStream(data)
    lexer = VisualFoxpro9Lexer(input_stream)
    stream = MultichannelTokenStream(lexer)
    parser = VisualFoxpro9Parser(stream)
    tree = parser.preprocessorCode()
    visitor = PreprocessVisitor()
    visitor.tokens = visitor.visit(tree)
    return visitor

def preprocess_file(filename):
    import codecs
    fid = codecs.open(filename, 'r', 'ISO-8859-1')
    data = fid.read()
    fid.close()

    return preprocess_code(data)

class MultichannelTokenStream(antlr4.CommonTokenStream):
    def __init__(self, lexer, channel=antlr4.Token.DEFAULT_CHANNEL):
        super(MultichannelTokenStream, self).__init__(lexer)
        self.channels = [channel]

    def nextTokenOnChannel(self, i, channel):
        self.sync(i)
        if i>=len(self.tokens):
            return -1
        token = self.tokens[i]
        while token.channel not in self.channels:
            if token.type==antlr4.Token.EOF:
                return -1
            i += 1
            self.sync(i)
            token = self.tokens[i]
        return i

    def previousTokenOnChannel(self, i, channel):
        while i>=0 and self.tokens[i].channel not in self.channels:
            i -= 1
        return i

    def enableChannel(self, channel):
        if channel not in self.channels:
            self.channels.append(channel)

    def disableChannel(self, channel):
        if channel in self.channels:
            self.channels.remove(channel)

def find_file_ignore_case(filename, directories):
    for directory in directories:
        for testfile in os.listdir(directory):
            if testfile.lower() == filename.lower():
                return os.path.join(directory, testfile)

def memo_filename(filename, ext):
    directory = os.path.dirname(filename) or '.'
    basename = os.path.basename(filename)
    memofile = os.path.splitext(basename)[0] + '.' + ext
    return find_file_ignore_case(memofile, [directory])

def copy_obscured_dbf(filename, memo_ext, dbf_basename):
    memofile = memo_filename(filename, memo_ext)
    dbffile = dbf_basename + '.dbf'
    shutil.copy(filename, dbffile)
    if memofile:
        shutil.copy(memofile, dbf_basename + '.fpt')
    return dbffile

def convert_scx_to_vfp_code(scxfile):
    with tempfile.NamedTemporaryFile() as tmpfile:
        pass
    tmpfile = tmpfile.name
    dbffile = copy_obscured_dbf(scxfile, 'sct', tmpfile)

    table = dbf.Table(dbffile)
    table.open()

    children = [list() for record in table]
    names = [record.objname for record in table]
    for record in table:
        if record['class'].lower() == 'form':
            form = record.objname
        parent = record.parent
        if not parent:
            continue
        parent_ind = names.index(parent)
        children[parent_ind].append(record)

    code = [l.format(form, form) for l in ('local {}', '{} = createObject("{}")', '{}.show()')]
    for record, child in zip(table, children):
        if not record.objname or record.parent or record['class'].lower() == 'dataenvironment':
            continue

        code.append('DEFINE CLASS {} AS {}'.format(record.objname, record['class']))
        subcode = []
        for line in record.properties.split('\r\n'):
            subcode.append(line)
        for child_record in child:
            subcode.append('ADD OBJECT {} AS {}'.format(child_record.objname, child_record['class']))
            for line in child_record.properties.split('\r\n'):
                line = line.strip()
                if not line:
                    continue
                prop, value = line.split(' = ')
                if prop == 'Picture':
                    value = '"{}"'.format(value)
                elif prop.endswith('Color'):
                    value = 'RGB({})'.format(value)
                subcode.append(child_record.objname + '.' + prop + ' = ' + value)
            subcode.append('')

        for line in record.methods.split('\r\n'):
            subcode.append(line)
        subcode.append('')
        for child_record in child:
            for line in child_record.methods.split('\r\n'):
                if not line:
                    continue
                line = re.sub(r'PROCEDURE ', 'PROCEDURE {}.'.format(child_record.objname), line)
                subcode.append(line)
            subcode.append('')
        code.append(subcode)
        code.append('ENDDEFINE')
        code.append('')

    def add_indent(code, level):
        retval = ''
        for line in code:
            if isinstance(line, list):
                retval += add_indent(line, level+1)
            else:
                retval += '   '*level + line + '\n'
        return retval

    code = add_indent(code, 0)

    code = re.sub(r'(\n\s*)+\n+', '\n\n', code)
    return code

def find_full_path(pathname, start_directory):
    name_parts = ntpath.split(pathname)
    while ntpath.split(name_parts[0])[1]:
        name_parts = ntpath.split(name_parts[0]) + name_parts[1:]
    pathname = start_directory
    for part in name_parts:
        if part in ('..', '.', ''):
            pathname = os.path.abspath(os.path.join(pathname, part))
            continue
        next_part = find_file_ignore_case(part, [pathname])
        if next_part is None:
            badind = name_parts.index(part)
            return os.path.join(pathname, *name_parts[badind:]), True
        pathname = next_part
    return pathname, False

def read_vfp_project(pjxfile):
    directory = os.path.dirname(pjxfile)
    with tempfile.NamedTemporaryFile() as tmpfile:
        pass
    tmpfile = tmpfile.name
    dbffile = copy_obscured_dbf(pjxfile, 'pjt', tmpfile)

    table = dbf.Table(dbffile)
    table.open()

    files = {}
    main_file = ''
    for record in table[1:]:
        name, failed = find_full_path(record.name.rstrip('\x00'), directory)
        if failed:
            files[name] = None
        else:
            files[os.path.basename(name).lower()] = name
        if record.mainprog:
            main_file = os.path.basename(name).lower()

    return files, main_file

def convert_project(infile, directory):
    project_files, main_file = read_vfp_project(infile)
    global SEARCH_PATH
    search = SEARCH_PATH
    search += [project_files[name] for name in project_files]
    if not os.path.isdir(directory):
        os.mkdir(directory)
    directory = os.path.join(directory, os.path.basename(directory))
    if not os.path.isdir(directory):
        os.mkdir(directory)
    for name in project_files:
        outfile = directory
        args = [project_files[name], outfile] + search
        try:
            main(args)
        except:
            print('failed to convert {}'.format(name))
    if 'config.fpw' in project_files:
        with open(project_files['config.fpw']) as fid:
            import ConfigParser
            import io
            config_data = io.StringIO('[config]\r\n' + fid.read().decode('utf-8'))
        config = ConfigParser.RawConfigParser()
        config.readfp(config_data)
        config = {x[0]: x[1] for x in config.items('config')}
    else:
        config = {}
    name = os.path.splitext(main_file)[0]
    with open(os.path.join(directory, '__main__.py'), 'wb') as fid:
        import pprint
        pp = pprint.PrettyPrinter(indent=4)
        print('import {}'.format(name, name), file=fid)
        print(file=fid)
        print('config = {}'.format(pp.pformat(config)), file=fid)
        print(file=fid)
        print('{}._program_main()'.format(name), file=fid)
    with open(os.path.join(directory, '__init__.py'), 'wb') as fid:
        pass
    directory = os.path.dirname(directory)
    with open(os.path.join(directory, 'setup.py'), 'wb') as fid:
        pass

def prg2py_after_preproc(data, parser_start, input_filename):
    input_stream = antlr4.InputStream(data)
    lexer = VisualFoxpro9Lexer(input_stream)
    stream = MultichannelTokenStream(lexer)
    parser = VisualFoxpro9Parser(stream)
    visitor = PythonConvertVisitor(input_filename)
    output_tree = visitor.visit(getattr(parser, parser_start)())
    return add_indents(output_tree, 0)

def prg2py(data, parser_start='prg', prepend_data='procedure _program_main\n', input_filename=''):
    tokens = preprocess_code(data).tokens
    data = prepend_data + ''.join(token.text.replace('\r', '') for token in tokens)
    return prg2py_after_preproc(data, parser_start, input_filename)

def convert_file(infile, outfile):
    tic = Tic()
    if infile.lower().endswith('.pjx'):
        convert_project(infile, outfile)
        return
    elif infile.lower().endswith('.fpw'):
        return
    elif infile.lower().endswith('.h'):
        return
    elif infile.lower().endswith('.scx'):
        if os.path.isdir(outfile):
            name = (os.path.splitext(os.path.basename(infile).lower())[0] + '.py').lower()
            outfile = os.path.join(outfile, name)
        data = convert_scx_to_vfp_code(infile)
        tokens = preprocess_code(data).tokens
    elif infile.lower().endswith('.vcx'):
        print('.vcx files not currently supported')
        return
    elif infile.lower().endswith('.frx'):
        print('.frx files not currently supported')
        return
    elif infile.lower().endswith('.mnx'):
        print('.mnx files not currently supported')
        return
    elif infile.lower().endswith('.fll'):
        print('.fll files not currently supported')
        return
    elif infile.lower().endswith('.app'):
        print('.app can\'t be converted')
        return
    elif infile.lower().endswith('.prg'):
        if os.path.isdir(outfile):
            name = (os.path.splitext(os.path.basename(infile).lower())[0] + '.py').lower()
            outfile = os.path.join(outfile, name)
        tokens = preprocess_file(infile).tokens
    else:
        if os.path.isdir(outfile):
            name = os.path.basename(infile).lower()
            shutil.copy(infile, os.path.join(outfile, name))
        return
    print(tic.toc())
    tic.tic()
    data = 'procedure _program_main\n' + ''.join(token.text.replace('\r', '') for token in tokens)
    with tempfile.NamedTemporaryFile(suffix='.prg') as fid:
        pass
    with open(fid.name, 'wb') as fid:
        fid.write(data.encode('utf-8'))
    output = prg2py_after_preproc(data, 'prg', os.path.splitext(os.path.basename(infile))[0])
    print(tic.toc())
    with open(outfile, 'wb') as fid:
        fid.write(output.encode('utf-8'))
    autopep8.main([__file__, '--max-line-length', '2000', '--in-place', outfile])
