
PKG_ROOT_DIRNAME = "pkg1"

LANG_EXT_MAPPING = {'javascript': ['.js'],
                    'html': ['.html', '.htm'],
                    'css': ['.css'],
                    'xml': ['.xml'],
                    'php': ['.php'],
                    'perl': ['.pl', '.pm'],
                    'python-2': ['.py'],
                    'python-3': ['.py']}


class EmptyPackageError(Exception):

    def __init__(self, pkg_dir, summary_file):
        Exception.__init__(self)
        self.pkg_dir = pkg_dir
        self.summary_file = summary_file
        self.exit_code = 2

    def __str__(self):
        return "No files with '.js', '.html', '.css' or '.xml' extenstion found in %s" % self.pkg_dir


class CommandFailedError(Exception):

    def __init__(self, command, exit_code, summary_file, outfile, errfile):
        Exception.__init__(self)
        self.command = ' '.join(command) if isinstance(command, list) else command
        self.exit_code = exit_code
        self.summary_file = summary_file
        self.outfile = outfile
        self.errfile = errfile

    def __str__(self):

        disp_str = "Command '{0}' failed with exit-code '{1}'".format(self.command,
                                                                      self.exit_code)

        if self.outfile and self.errfile:
            disp_str += ", See "

            if self.outfile:
                disp_str += "'{0}'".format(self.outfile)

                if self.errfile:
                    disp_str += ", "

            if self.errfile:
                disp_str += "'{0}'".format(self.errfile)

            disp_str += " for errors"

        return disp_str


def get_file_extentions(pkg_lang):
    '''pkg_lang is a string (straight from package.conf['package-language']'''
    if isinstance(pkg_lang, str):
        pkg_lang = pkg_lang.split()

    return list({ext for lang in pkg_lang for ext in LANG_EXT_MAPPING[lang] \
                 if lang in LANG_EXT_MAPPING})
