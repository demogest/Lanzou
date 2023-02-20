from Constant import Constants


class Variable:
    # Headers
    __headers = Constants.HEADERS

    # Init
    def __init__(self, url, password, dir, updater):
        self.__url = url
        self.__password = password
        self.__dir = dir
        self.__file_url_with_name = []
        self.__headers['Referer'] = self.__url
        self.__updater = updater

    # Getters
    def get_url(self):
        return self.__url

    def get_password(self):
        return self.__password

    def get_dir(self):
        return self.__dir

    def get_file_url_with_name(self):
        return self.__file_url_with_name

    def get_headers(self):
        return self.__headers

    def get_updater(self):
        return self.__updater

    # Setters
    def set_file_url_with_name(self, file_url_with_name):
        self.__file_url_with_name = file_url_with_name

    def set_headers(self, headers):
        self.__headers = headers

    def set_password(self, password):
        self.__password = password

    def set_url(self, url):
        self.__url = url
        self.__headers['Referer'] = self.__url

    def set_dir(self, dir):
        self.__dir = dir

    def set_updater(self, updater):
        self.__updater = updater

    # Methods
    def add_file_url_with_name(self, file_url_with_name):
        self.__file_url_with_name.append(file_url_with_name)

    def add_headers(self, headers):
        self.__headers.update(headers)

    def remove_headers(self, headers):
        for i in headers:
            self.__headers.pop(i)

    def remove_file_url_with_name(self, file_name):
        for i in self.__file_url_with_name:
            if i[1] == file_name:
                self.__file_url_with_name.remove(i)
                return True
        return False

    def clear_file_url_with_name(self):
        self.__file_url_with_name = []

    def clear_headers(self):
        self.__headers = Constants.HEADERS

    def clear(self):
        self.__file_url_with_name = []
        self.__headers = Constants.HEADERS
        self.__password = ''
        self.__url = ''
        self.__dir = ''

    def __str__(self):
        return f'Url: {self.__url}\nPassword: {self.__password}\nDir: {self.__dir}\nFile Url With Name: {self.__file_url_with_name}\nHeaders: {self.__headers}'

    def __repr__(self):
        return f'Url: {self.__url}\nPassword: {self.__password}\nDir: {self.__dir}\nFile Url With Name: {self.__file_url_with_name}\nHeaders: {self.__headers}'
