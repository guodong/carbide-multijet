import os, errno


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def nsenter_run(pid, cmd):
    c = 'nsenter -t ' + str(pid) + ' -n -m -p ' + cmd
    os.system(c)
