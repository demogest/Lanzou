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
Constants.HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/80.0.3987.132 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,'
              'application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
Constants.NEED_PWD = 1
Constants.NO_NEED_PWD = 0
Constants.PWD_ERROR = -1
Constants.SINGLE_FILE = 2
Constants.MULTI_FILE = 3
Constants.PREFIX = 'https://www.lanzoux.com/'
Constants.AJAX_URL = 'https://www.lanzoux.com/ajaxm.php'
Constants.FILE_MORE_AJAX_URL = 'https://www.lanzoux.com/filemoreajax.php'
