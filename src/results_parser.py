import os
import os.path as osp
import logging
import shutil

from .logger import LogTaskStatus
from . import utillib
from .import confreader
from .utillib import FileNotFoundException


def just_parse(input_root_dir, output_root_dir):

    results_conf_file = osp.join(input_root_dir, 'results.conf')
    results_conf = confreader.read_conf_into_dict(results_conf_file)

    if int(results_conf['exit-code']) != 0:
        return int(results_conf['exit-code'])

    results_archive = osp.join(input_root_dir, results_conf['results-archive'])

    cwd = os.getcwd()
    with LogTaskStatus('results-unarchive'):
        status = utillib.unpack_archive(results_archive, cwd)
        if status != 0:
            return status

    results_root_dir = osp.join(cwd, results_conf['results-dir'])
    assessment_summary_file = osp.join(results_root_dir,
                                       results_conf['assessment-summary-file'])

    return parse_results(input_root_dir,
                         assessment_summary_file,
                         results_root_dir,
                         output_root_dir)


def _get_results_parser(input_dir):

    with LogTaskStatus('resultparser-unarchive'):

        parser_dir = osp.join(os.getcwd(), 'result-parser')
        if not osp.isdir(parser_dir):
            os.mkdir(parser_dir)

        parser_conf_file = osp.join(input_dir, 'resultparser.conf')

        if not osp.isfile(parser_conf_file):
            raise FileNotFoundException(parser_conf_file)

        parser_attr = confreader.read_conf_into_dict(parser_conf_file)
        logging.info('RESULTS PARSER CONF: ' + str(parser_attr))

        parser_archive = osp.join(input_dir, parser_attr['result-parser-archive'])

        utillib.unpack_archive(parser_archive, parser_dir)

        parser_dir = osp.join(parser_dir, parser_attr['result-parser-dir'])
        parser_exe_file = osp.join(parser_dir, parser_attr['result-parser-cmd'])

        return parser_exe_file


def parse_results(input_dir, assessment_summary_file, results_dir, output_dir):

    command_template = '{EXECUTABLE}\
 --summary_file={PATH_TO_SUMMARY_FILE}\
 --input_dir={PATH_TO_RESULTS_DIR}\
 --output_file={OUTPUT_FILENAME}\
 --weakness_count_file={WEAKNESS_COUNT_FILENAME}'

    if not osp.isfile(assessment_summary_file):
        raise FileNotFoundException(assessment_summary_file)

    parser_exe_file = _get_results_parser(input_dir)

    try:
        parse_results_dir = osp.join(os.getcwd(), 'parsed_results')
        if not osp.isdir(parse_results_dir):
            os.mkdir(parse_results_dir)

        parse_results_logfile = osp.join(parse_results_dir, 'resultparser.log')
        parse_results_output_file = osp.join(parse_results_dir, 'parsed_result.xml')
        parse_weakness_count_file = osp.join(parse_results_dir, 'weakness_count.out')

        with LogTaskStatus('parse-results') as status_dot_out:

            if 'PERL5LIB' in os.environ:
                os.environ['PERL5LIB'] = '${0}:{1}'.format(os.environ['PERL5LIB'],
                                                           osp.dirname(parser_exe_file))
            else:
                os.environ['PERL5LIB'] = osp.dirname(parser_exe_file)

            command = command_template.format(EXECUTABLE=parser_exe_file,
                                              PATH_TO_SUMMARY_FILE=assessment_summary_file,
                                              PATH_TO_RESULTS_DIR=results_dir,
                                              PATH_TO_OUTPUT_DIR=parse_results_dir,
                                              OUTPUT_FILENAME=parse_results_output_file,
                                              WEAKNESS_COUNT_FILENAME=parse_weakness_count_file,
                                              LOGFILE=parse_results_logfile)

            exit_code, environ = utillib.run_cmd(command,
                                                 cwd=osp.dirname(parser_exe_file),
                                                 description='PARSE RESULTS')

            if exit_code == 0:
                weakness_count = ''
                if osp.isfile(parse_weakness_count_file):
                    with open(parse_weakness_count_file) as fobj:
                        weakness_count = ' '.join([line.strip('\n') for line in fobj])
                        status_dot_out.update_task_status(exit_code, '{0}'.format(weakness_count))
            else:
                status_dot_out.update_task_status(exit_code,
                                                  'Results Parser returned Exit Code: {0}'.format(exit_code))
    # NOTE: Not sure which part of the code will throw an exception. Handling exception map not be required
    except Exception as err:
        logging.exception(err)
        exit_code = 1
    finally:
        with LogTaskStatus('parsed_results-archive'):
            shutil.make_archive(osp.join(output_dir,
                                         osp.basename(parse_results_dir)),
                                'gztar',
                                osp.dirname(parse_results_dir),
                                osp.basename(parse_results_dir))

        parse_results_conf_dict = dict()
        parse_results_conf_dict['parsed-results-dir'] = osp.basename(parse_results_dir)
        parse_results_conf_dict['parsed-results-file'] = osp.basename(parse_results_output_file)
        parse_results_conf_dict['parsed-results-archive'] = '{0}.tar.gz'.format(osp.basename(parse_results_dir))

        utillib.write_to_file(osp.join(output_dir, 'parsed_results.conf'),
                              parse_results_conf_dict)

    if exit_code != 0:
        raise Exception('Exit Code Not 0')
    else:
        return 0
