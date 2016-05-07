import os.path as osp
import logging
import logging.handlers


from . import assess
from .logger import LogTaskStatus
from . import confreader
from . import install_os_dependencies
from . import results_parser
from . import utillib
from . import build


def main(input_dir,
         output_dir,
         build_dir,
         tool_dir,
         results_dir):

    with LogTaskStatus('all') as status_dot_out:
        try:
            run_conf_file = osp.join(input_dir, 'run.conf')

            if not osp.isfile(run_conf_file):
                raise utillib.FileNotFoundException(run_conf_file)

            param = confreader.read_conf_into_dict(run_conf_file)

            if 'goal' not in param:
                raise KeyError('{0} param not found in {1} file'.format('goal',
                                                                        osp.basename(run_conf_file)))

            goal = param['goal']

            swamp_goals = ['build',
                           'build+assess',
                           'build+assess+parse',
                           'assess',
                           'assess+parse',
                           'parse']

            logging.info('GOAL: %s', goal)

            if goal not in swamp_goals:
                raise ValueError('Unknown goal {0}, it should be one of {1}'.format(goal,
                                                                                    swamp_goals))

            install_os_dependencies.install(input_dir)

            if goal in swamp_goals[:3]:
                exit_code = _build_assess_parse(goal,
                                                input_dir,
                                                output_dir,
                                                build_dir,
                                                tool_dir,
                                                results_dir)
            elif goal in swamp_goals[3:5]:
                raise NotImplementedError
            elif goal == swamp_goals[5]:
                exit_code = results_parser.just_parse(input_dir, output_dir)

        except (BaseException, Exception) as err:
            logging.exception(err)
            if hasattr(err, 'errno'):
                exit_code = err.errno
            else:
                exit_code = 1

        status_dot_out.update_task_status(exit_code)

    return exit_code

def _build_assess_parse(goal, input_root_dir, output_root_dir,
                        build_root_dir, tool_root_dir,
                        results_root_dir):

    (exit_code, build_summary_file) = build.build(input_root_dir,
                                                  output_root_dir,
                                                  build_root_dir)

    if (exit_code == 0) and ('assess' in goal):

        build_summary_file = osp.join(build_root_dir, build_summary_file)
        (exit_code, assessment_summary_file) = assess.assess(input_root_dir,
                                                             output_root_dir,
                                                             tool_root_dir,
                                                             results_root_dir,
                                                             build_summary_file)

        if (exit_code == 0) and ('parse' in goal):
            exit_code = results_parser.parse_results(input_root_dir,
                                                     assessment_summary_file,
                                                     results_root_dir,
                                                     output_root_dir)

    return exit_code
