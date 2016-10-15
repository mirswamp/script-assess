import os
import os.path as osp
import glob
import subprocess
import sys
import datetime
import time
import re
import shlex
import uuid
from collections import namedtuple
import logging


if 'PermissionError' in __builtins__:
    PermissionException = PermissionError
else:
    class PermissionException(OSError):
        pass

if 'FileNotFoundError' in __builtins__:
    FileNotFoundException = FileNotFoundError
else:
    class FileNotFoundException(OSError):
        pass

if 'NotADirectoryError' in __builtins__:
    NotADirectoryException = NotADirectoryError
else:
    class NotADirectoryException(OSError):
        pass

if 'IsADirectoryError' in __builtins__:
    IsADirectoryException = IsADirectoryError
else:
    class IsADirectoryException(OSError):
        pass


class UnpackArchiveError(Exception):

    def __init__(self, filename):
        Exception.__init__(self)
        self.filename = filename
        self.exit_code = 5

    def __str__(self):
        return "Unpacking archive '{0}' failed".format(self.filename)


def datetime_iso8601():
    return datetime.datetime.isoformat(datetime.datetime.now())


def posix_epoch():
    return str(time.time())


def _unpack_archive_xz(archive, dirpath):

    xz_proc = subprocess.Popen(['xz', '--decompress', '--stdout', archive],
                               stdout=subprocess.PIPE,
                               stderr=sys.stderr)

    tar_proc = subprocess.Popen(['tar', '-x'],
                                stdin=xz_proc.stdout,
                                stdout=sys.stdout,
                                stderr=sys.stderr,
                                cwd=dirpath)

    xz_proc.stdout.close()
    tar_proc.communicate()

    return tar_proc.returncode


def unpack_archive(archive, dirpath, createdir=True):
    '''
    Unarchives/Extracts the file \'archive\' in the directory \'dirpath\'.
    Expects \'dirpath\' to be already present.
    Throws FileNotFoundException and NotADirectoryException if
    archive or dirpath not found
    ValueError if archive format is not supported.
    '''

    if not osp.isfile(archive):
        raise FileNotFoundException(archive)

    if not osp.isdir(dirpath):
        if createdir:
            os.makedirs(dirpath)
        else:
            raise NotADirectoryException(dirpath)

    archive = osp.abspath(archive)
    dirpath = osp.abspath(dirpath)

    cmd_template_dict = {'.tar.gz': 'tar -x -z -f %s',
                         '.tgz': 'tar -x -z -f %s',
                         '.tar.Z': 'tar -x -Z -f %s',
                         '.tar.bz2': 'tar -x -j -f %s',
                         '.tar': 'tar -x -f %s',
                         '.zip': 'unzip -qq -o %s',
                         '.jar': 'unzip -qq -o %s',
                         '.war': 'unzip -qq -o %s',
                         '.ear': 'unzip -qq -o %s',
                         '.phar': 'phar extract -f %s'}

    if any((archive.endswith(ext) for ext in cmd_template_dict)):
        cmd = [cmd_template_dict[ext] % archive
               for ext in cmd_template_dict if archive.endswith(ext)][0]
        return run_cmd(cmd, cwd=dirpath, description='UNPACK ARCHIVE')[0]
    elif archive.endswith('.tar.xz'):
        return _unpack_archive_xz(archive, dirpath)
    else:
        raise ValueError('Format not supported')


def run_cmd_old(cmd,
                outfile=sys.stdout,
                errfile=sys.stderr,
                infile=None,
                cwd='.',
                shell=False,
                env=None):
    '''argument cmd should be a list'''
    
    def openfile(filename, mode):
        open(filename, mode) if(isinstance(filename, str)) else filename

    out = openfile(outfile, 'w')
    err = openfile(errfile, 'w')
    inn = openfile(infile, 'r')

    if isinstance(cmd, str):
        shell = True

    environ = dict(os.environ) if env is None else env

    try:
        popen = subprocess.Popen(cmd,
                                 stdout=out,
                                 stderr=err,
                                 stdin=inn,
                                 shell=shell,
                                 cwd=cwd,
                                 env=environ)
        popen.wait()
        return (popen.returncode, environ)
    except subprocess.CalledProcessError as err:
        return (err.returncode, environ)
    finally:
        def closefile(filename, fileobj):
            fileobj.close() if(isinstance(filename, str)) else None

        closefile(outfile, out)
        closefile(errfile, err)
        closefile(infile, inn)


def run_cmd(cmd,
            outfile=sys.stdout,
            errfile=sys.stderr,
            infile=None,
            cwd='.',
            shell=False,
            env=None,
            description='UNKNOWN'):
    '''argument cmd should be a list'''
    
    def openfile(filename, mode):
        return open(filename, mode) if(isinstance(filename, str)) else filename

    def closefile(filename, fileobj):
        if isinstance(filename, str):
            fileobj.close()

    out = openfile(outfile, 'w')
    err = openfile(errfile, 'w')
    inn = openfile(infile, 'r')

    if isinstance(cmd, str):
        shell = True

    environ = dict(os.environ) if env is None else env
    environ['PWD'] = osp.abspath(cwd)
    
    try:
        logging.info('%s COMMAND %s', description, cmd)
        logging.info('%s WORKING DIR %s', description, environ['PWD'])

        popen = subprocess.Popen(cmd,
                                 stdout=out,
                                 stderr=err,
                                 stdin=inn,
                                 shell=shell,
                                 cwd=environ['PWD'],
                                 env=environ)
        popen.wait()
        exit_code = popen.returncode
    except subprocess.CalledProcessError as err:
        exit_code = err.returncode
    finally:
        logging.info('%s EXIT CODE %s', description, exit_code)
        logging.info('%s ENVIRONMENT %s', description, environ)

        closefile(outfile, out)
        closefile(errfile, err)
        closefile(infile, inn)
        
    return (exit_code, environ)


def os_path_join(basepath, subdir):
    if subdir.startswith('/'):
        return osp.normpath(osp.join(basepath, subdir[1:]))
    else:
        return osp.normpath(osp.join(basepath, subdir))


def glob_glob(path, pattern):
    return glob.glob(os_path_join(path, pattern))


def get_cpu_type():
    '64-bit or 32-bit'
    try:
        output = subprocess.check_output(['getconf', 'LONG_BIT'])
        return int(output.decode('utf-8').strip())
    except subprocess.CalledProcessError:
        return None


def max_cmd_size():
    # expr `getconf ARG_MAX` - `env|wc -c` - `env|wc -l` \* 4 - 2048
    #arg_max = subprocess.check_output(['getconf', 'ARG_MAX'])
    #arg_max = int(arg_max.decode(encoding='utf-8').strip())
    # if arg_max > 131072:
    arg_max = 131072
    env_len = len(''.join([str(k) + ' ' + str(os.environ[k]) for k in os.environ.keys()]))
    env_num = len(os.environ.keys())  # for null ptr
    arg_max = arg_max - env_len - env_num * 4 - 2048  # extra caution
    return arg_max


def max_cmd_size_new():
    cmd = 'expr `getconf ARG_MAX` - `env|wc -c` - `env|wc -l` \* 4 - 2048'
    return int(subprocess.check_output(cmd, shell=True).decode(encoding='utf-8').strip())


def platform():
    platname = os.uname()
    return platname[3] if(isinstance(platname, tuple)) else platname.version


def write_to_file(filename, obj):
    '''write a dictionary or list object to a file'''

    with open(filename, 'w') as fobj:

        if isinstance(obj, dict):
            for key in obj.keys():
                print('{0}={1}'.format(key, obj[key]), file=fobj)

        if isinstance(obj, list):
            for entity in obj:
                print(entity, file=fobj)


PARAM_REGEX = re.compile(r'<(?P<name>[a-zA-Z][a-zA-Z_-]*)(?:[%](?P<sep>[^>]+))?>')


def string_substitute(string_template, symbol_table):
    '''Substitues environment variables and
    config parameters in the string.
    quotes the string and returns it'''

    new_str = string_template
    for match in PARAM_REGEX.finditer(string_template):
        name = match.groupdict()['name']
        sep = match.groupdict()['sep']

        if name in symbol_table:
            value = symbol_table[name]
            if not isinstance(value, str):
                if sep is None:
                    value = value[0]
                else:
                    value = sep.join(value)
        else:
            value = ''

        f = '<{0}>' if sep is None else '<{0}%{1}>'
        new_str = new_str.replace(f.format(match.groupdict()['name'],
                                           match.groupdict()['sep']),
                                  value, 1)

    return osp.expandvars(new_str)


def expandvar(var, kwargs):
    return string_substitute(var, kwargs)


def rmfile(filename):
    if osp.isfile(filename):
        os.remove(filename)


# Copied from Python3.3 Standard Libary shlex.py
_find_unsafe = re.compile(r'[^\w@%+=:,./-]', re.ASCII).search


def _quote(s):
    """Return a shell-escaped version of the string *s*."""
    if not s:
        return "''"
    if _find_unsafe(s) is None:
        return s

    # use single quotes, and put single quotes into double quotes
    # the string $'b is then quoted as '$'"'"'b'
    return "'" + s.replace("'", "'\"'\"'") + "'"


def quote_str(s):
    if hasattr(shlex, 'quote'):
        return shlex.quote(s)
    else:
        return _quote(s)


def get_uuid():
    return str(uuid.uuid4())


def ordered_list(_list):

    _set = set()
    new_list = list()

    for item in _list:
        if item not in _set:
            _set.add(item)
            new_list.append(item)

    return new_list

######

FileFilters = namedtuple('FileFilters', ['exclude_dirs', 'exclude_files',
                                         'include_dirs', 'include_files'])


def expand_patterns(root_dir, pattern_list):
    for pattern in pattern_list:
        if '**' in pattern:
            head, _, tail = pattern.partition('**')
            tail = tail[1:] if tail.startswith('/') else tail
            if tail in ['', '*.*', '*']:
                yield glob_glob(root_dir, head)
            else:
                for dirpath, _, _ in os.walk(os_path_join(root_dir, head)):
                    yield glob_glob(dirpath, tail)
        else:
            yield glob_glob(root_dir, pattern)


def get_file_filters(root_dir, patterns):
    '''Returns an FileFilters object'''

    '''patterns is expected to be a list or filepath'''
    if isinstance(patterns, str):
        with open(patterns) as fobj:
            patterns = [p for p in fobj]
    elif patterns is None:
        patterns = []

    patterns = {p.strip().strip('\n') for p in patterns
                if p and not p.isspace() and not p.strip().startswith('#')}

    ex_dir_list = set()
    ex_file_list = set()

    for fileset in expand_patterns(root_dir,
                                   (p for p in patterns
                                    if not p.startswith('!'))):
        if fileset:
            for _file in fileset:
                if osp.isdir(_file):
                    ex_dir_list.add(osp.normpath(_file))
                else:
                    ex_file_list.add(osp.normpath(_file))

    in_dir_list = set()
    in_file_list = set()

    for fileset in expand_patterns(root_dir,
                                   (p[1:] for p in patterns
                                    if p.startswith('!'))):
        if fileset:
            for _file in fileset:
                if osp.isdir(_file):
                    in_dir_list.add(osp.normpath(_file))
                else:
                    in_file_list.add(osp.normpath(_file))

    return FileFilters(ex_dir_list, ex_file_list, in_dir_list, in_file_list)


def filter_out(root_dir, file_filters, file_types):
    '''
    This is a generator function.
    os.walk with directories in file_filters.exclude_dirs and
    file_filters.exclude_files and hidden (begin with .) are ignored
    '''

    def is_dirpath_in(dirpath, dir_list):
        return any(dirpath.startswith(path) for path in dir_list) \
            if dir_list else False

    hidden_dir_list = []

    for dirpath, _, filenames in os.walk(root_dir):

        if osp.basename(dirpath).startswith('.'):
            hidden_dir_list.append(dirpath)
        elif not (is_dirpath_in(osp.join(dirpath, ''), file_filters.exclude_dirs) or
                  is_dirpath_in(osp.join(dirpath, ''), hidden_dir_list)):
            filepaths = {osp.normpath(osp.join(dirpath, _file))
                         for _file in filenames
                         if not _file.startswith('.') and
                         (osp.splitext(_file)[1] in file_types)}
            filepaths = filepaths.difference(file_filters.exclude_files)
            if filepaths:
                for _file in filepaths:
                    yield _file


def filter_in(file_filters, file_types):
    '''
    This is a generator function.
    '''

    for include_dir in file_filters.include_dirs:
        for dirpath, _, filenames in os.walk(include_dir):
            for _file in filenames:
                if osp.splitext(_file)[1] in file_types:
                    yield osp.join(dirpath, _file)

    for _file in file_filters.include_files:
        if osp.isfile(_file) and \
           osp.splitext(_file)[1] in file_types:
            yield _file


def get_file_list(root_dir, patterns, file_types):

    file_filters = get_file_filters(root_dir, patterns)

    file_list = list()
    file_list.extend(filter_out(root_dir, file_filters, file_types))
    file_list.extend(filter_in(file_filters, file_types))

    return file_list


def filter_file_list(file_list, root_dir, patterns):

    file_filters = get_file_filters(root_dir, patterns)

    new_file_list = set(file_list).difference(file_filters.exclude_files)

    def is_file_in(filepath, dir_list):
        return any(filepath.startswith(osp.join(path, ''))
                   for path in dir_list) if dir_list else False

    new_file_list = new_file_list.difference({_file for _file in new_file_list
                                              if is_file_in(_file, file_filters.exclude_dirs)})

    return list(new_file_list)
