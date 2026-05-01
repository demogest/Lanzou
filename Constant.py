from lanzou_downloader.config import DEFAULT_HEADERS, LanzouConfig


class _Constant:
    class ConstError(TypeError):
        pass

    class ConstCaseError(ConstError):
        pass

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise self.ConstError("Can't change const.%s" % name)
        if not name.isupper():
            raise self.ConstCaseError('const name "%s" is not all uppercase' % name)
        self.__dict__[name] = value


Constants = _Constant()
_config = LanzouConfig()
Constants.HEADERS = DEFAULT_HEADERS.copy()
Constants.NEED_PWD = 1
Constants.NO_NEED_PWD = 0
Constants.PWD_ERROR = -1
Constants.SINGLE_FILE = 2
Constants.MULTI_FILE = 3
Constants.PREFIX = _config.prefix
Constants.AJAX_URL = _config.ajax_url
Constants.FILE_MORE_AJAX_URL = _config.file_more_ajax_url
