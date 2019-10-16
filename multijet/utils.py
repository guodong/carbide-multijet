import logging
import datetime as dt


class MyFormatter(logging.Formatter):
    converter = dt.datetime.fromtimestamp

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = "%s,%03d" % (t, record.msecs)
        return s


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)
# handler = logging.FileHandler("/etc/quagga/multijet2.log")
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = MyFormatter(fmt='%(asctime)s %(created).6f %(message)s', datefmt='%Y-%m-%d,%H:%M:%S.%f')
handler.setFormatter(formatter)
logger.addHandler(handler)


def log(msg, level='info'):
    if level == 'info':
        logger.info(msg)


def debug(msg):
    logger.debug(msg)