import os
import os.path as osp
import logging
import logging.handlers
import sys
import time
import textwrap


class StreamHandlerCustom(logging.StreamHandler):

    def __init__(self, stream=None):
        super().__init__(stream)

    def handle(self, record):
        super().handle(record)
        self.flush()


def init(output_dir=os.getcwd()):

    logging.addLevelName(60, 'STATUS')

    debug_file_handler = logging.handlers.WatchedFileHandler(osp.join(output_dir,
                                                                      'debug.out'), 'w')
    debug_file_handler.setFormatter(logging.Formatter('%(module)s: %(lineno)d: %(levelname)s: %(message)s'))
    debug_file_handler.set_name('debug-file-handler')
    debug_file_handler.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(debug_file_handler)

    stream_handler = StreamHandlerCustom(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    stream_handler.set_name('stream-handler')
    stream_handler.setLevel(logging.INFO)
    logging.getLogger('').addHandler(stream_handler)

    logging.getLogger('').setLevel(logging.DEBUG)

    status_file_handler = logging.handlers.WatchedFileHandler(osp.join(output_dir,
                                                                       'status.out'), 'w')
    status_file_handler.setFormatter(logging.Formatter('%(message)s'))
    status_file_handler.set_name('status-file-handler')
    status_file_handler.setLevel(60)
    logging.getLogger('.status-logger').addHandler(status_file_handler)
    logging.getLogger('.status-logger').propagate = False

    logging.getLogger('.status-logger').log(60, 'NOTE: begin')


def shutdown():
    logging.getLogger('.status-logger').log(60, 'NOTE: end')
    logging.shutdown()


class LogTaskStatus():
    ''' For Logging Task times and status PASS/FAIL/SKIP
    Format:
    PASS|FAIL|SKIP: <task-name> <task-msg>                                             <time-taken>
      ----------
      <task-msg-indetail-line1>
      <task-msg-indetail-line2>
      <task-msg-indetail-line3>
      ...
      ...
      ----------
    '''

    def __init__(self, task):

        self.task = str(task)
        self.exit_status = 0
        self.task_msg = None
        self.task_msg_indetail = None
        self.skip = False
        self.textwrapper = textwrap.TextWrapper(width=64,
                                                subsequent_indent='  ',
                                                break_on_hyphens=False)

    def __enter__(self):
        self.start_time = time.time()
        return self

    @classmethod
    def get_status_str(cls,
                       taskname,
                       skip,
                       exit_status,
                       task_msg,
                       time_spent):

        if skip:
            status_str = 'SKIP'
        else:
            status_str = 'PASS' if(exit_status == 0) else 'FAIL'

        if task_msg:
            task_str = '{0} ({1})'.format(taskname, task_msg)
        else:
            task_str = taskname

        return '{0}: {1:{text_width}} {2:{time_width}.6f}s'.format(status_str,
                                                                   task_str,
                                                                   time_spent,
                                                                   text_width=59,
                                                                   time_width=13)

    def get_formatted_msg(self, task_msg_indetail):
        '''  ----------
             Multiline Message
             ----------
        '''
        sep = '-' * 10
        return '''  {0}\n  {1}\n  {0}'''.format(sep, self.textwrapper.fill(task_msg_indetail))

    def skip_task(self, task_msg=None, task_msg_indetail=None):
        self.skip = True

        if task_msg:
            self.task_msg = task_msg

        if task_msg_indetail:
            self.task_msg_indetail = task_msg_indetail

    def update_task_status(self, exit_status, task_msg=None, task_msg_indetail=None):
        self.exit_status = exit_status

        if task_msg:
            self.task_msg = task_msg

        if task_msg_indetail:
            self.task_msg_indetail = task_msg_indetail

    def write(self):
        logging.getLogger('.status-logger').log(60,
                                                self.get_status_str(self.task,
                                                                    self.skip,
                                                                    self.exit_status,
                                                                    self.task_msg,
                                                                    self.end_time - self.start_time))

        if self.task_msg_indetail:
            logging.getLogger('.status-logger').log(60,
                                                    self.get_formatted_msg(self.task_msg_indetail))

    def __exit__(self, exception_type, value, traceback):
        self.end_time = time.time()

        if value:
            exit_status = value.errno if(hasattr(value, 'errno')) else 1
            self.update_task_status(exit_status, None, str(value))

        self.write()
