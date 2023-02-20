import json
import os
import re
import requests
import sys
import math

import bs4 as bs
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool, QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QInputDialog

import mainWindow
from Constant import Constants
from Variable import Variable


def check_is_single_file(url, pre_params: Variable):
    r = requests.get(url, headers=pre_params.get_headers())
    soup = bs.BeautifulSoup(r.text, 'html.parser')
    # check if iframe exists
    if soup.find('iframe')['src']:
        return Constants.SINGLE_FILE
    else:
        return Constants.MULTI_FILE


class UpdateSignal(QObject):
    update_text_signal = pyqtSignal(str)
    update_progressBar_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()

    def update_text(self, text):
        self.update_text_signal.emit(text)

    def update_progressBar(self, value):
        self.update_progressBar_signal.emit(value)


class Worker(QRunnable, QObject):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self):
        # print(*self.args, **self.kwargs)
        self.fn(*self.args, **self.kwargs)


def check_password(response):
    soup = bs.BeautifulSoup(response.text, 'html.parser')
    # check if <input class="input" id="pwd" name="pwd" type="text" value=""/> exists
    if soup.find('input', {'id': 'pwd', 'name': 'pwd', 'type': 'text', 'value': ''}):
        return Constants.NEED_PWD
    # check if <input type="text" name="pwd" class="passwdinput" id="pwd" value="" placeholder="输入密码"/> exists
    elif soup.find('input', {'id': 'pwd', 'name': 'pwd', 'type': 'text', 'value': '', 'placeholder': '输入密码'}):
        return Constants.NEED_PWD
    else:
        return Constants.NO_NEED_PWD


def get_file_pwd(url, pre_params: Variable):
    # print("Trying to bypass password...")
    r = requests.get(url, headers=pre_params.get_headers())
    if check_password(r) == Constants.NEED_PWD:
        action = re.findall(r'action=([\S]*?)&', r.text)[0]
        sign = re.findall(r'sign=([\S]{15,})&', r.text)[0]
        data = {
            'action': action,
            'sign': sign,
            'p': pre_params.get_password(),
        }
        # print(data)
        r = requests.post(Constants.AJAX_URL, data=data, headers=pre_params.get_headers())
        response = json.loads(r.text)
        # print(response)
        if response['zt'] == 1:
            url = response['dom'] + '/file/' + response['url']
        else:
            url = 0
        return [url, response['inf']]


def get_file(pre_params: Variable):
    headers = pre_params.get_headers()
    file_url = pre_params.get_file_url_with_name()
    updater: UpdateSignal = pre_params.get_updater()
    # print('Start Getting File Url...')
    for i in file_url:
        url = Constants.PREFIX + i[0]
        r = requests.get(url, headers=pre_params.get_headers())
        if check_password(r) == Constants.NEED_PWD:
            # print('Password Required!')
            # print('Trying to get password...')
            url = get_file_pwd(url, pre_params)[0]
            if url == 0:
                # print('Password Error!')
                continue
            else:
                i[0] = url
                continue
        soup = bs.BeautifulSoup(r.text, 'html.parser')
        redirect_url = "https://www.lanzoux.com" + soup.find('iframe')['src']
        r = requests.get(redirect_url, headers=headers)
        wsk_sign = re.findall(r'wsk_sign[ ]??=[ ]??\'(\S*?)\';', r.text)[0]
        ws_sign = re.findall(r'ws_sign[ ]??=[ ]??\'(\S*?)\';', r.text)[0]
        ajaxdata = re.findall(r'ajaxdata[ ]??=[ ]??\'(\S*?)\';', r.text)[0]
        action = re.findall(r'\'action\'[ ]??:[ ]??\'([\w]*?)\',', r.text)[0]
        sign = re.findall(r'\'sign\'[ ]??:[ ]??\'([\S]*?)\',', r.text)[0]
        data = {
            'action': action,
            'sign': sign,
            'ves': 1,
            'signs': ajaxdata,
            'websignkey': wsk_sign,
            'websign': ws_sign,
        }
        # print(data)
        r = requests.post(Constants.AJAX_URL, headers=headers, data=data)
        response = json.loads(r.text)
        if response['zt'] == 1:
            file_down_url = response['dom'] + '/file/' + response['url']
            updater.update_text('Get %s Url Success!' % i[1])
            # print('Get Url Success!', file_down_url)
            i[0] = file_down_url
        else:
            # print('Get Url Failed!')
            updater.update_text('Get %s Url Failed!' % i[1])
            return
    # print(file_url)
    return file_url


# download file
def download_file(pre_params: Variable):
    # print('Start Downloading...')
    # print('Target Directory: ' + pre_params.get_dir())
    target_directory = pre_params.get_dir()
    headers = pre_params.get_headers()
    updater: UpdateSignal = pre_params.get_updater()
    # check if target directory exists
    if not os.path.exists(target_directory):
        os.makedirs(target_directory)
    # File Url List
    file_url = pre_params.get_file_url_with_name()
    total, index = len(file_url), 0.0
    # print('Total: %d' % total)
    for i in file_url:
        name = i[1]
        url = i[0]
        # print('Downloading ' + name + ' from ' + url)
        # if file already exists, pass
        if os.path.exists(target_directory + name):
            # print('File %s Already Exists!' % name)
            updater.update_text('%s Already Exists!' % name)
            index += 1.0
            progress = index / total
            # print('Progress: %f%%' % progress)
            updater.update_progressBar(int(progress * 100))
            continue
        # if url didn't start with http, pass
        if not url.startswith('http'):
            # print('Download %s Failed!' % name)
            updater.update_text('Download %s Failed!' % name)
            continue
        r = requests.get(url, headers=headers)
        with open(target_directory + name, 'wb') as f:
            f.write(r.content)
        # print(name + ' Downloaded!')
        updater.update_text('%s Downloaded!' % name)
        index += 1.0
        progress = index / total
        # print('Progress: %f%%' % progress)
        updater.update_progressBar(int(progress * 100))
    updater.update_text('Download Finished!')


def get_files_url(pre_params: Variable):
    # print('Start Getting Files Url...')
    url = pre_params.get_url()
    r = requests.get(url, headers=pre_params.get_headers())
    headers = pre_params.get_headers()
    password = pre_params.get_password()
    updater: UpdateSignal = pre_params.get_updater()
    params = re.findall(r'var [\w]{6} = \'([\w]+?)\';', r.text)
    fid = re.findall(r'\'fid\':(\d+?),', r.text)[0]
    uid = re.findall(r'\'uid\':\'(\d+?)\',', r.text)[0]
    # rep = re.findall(r'\'rep\':\'(\d+?)\',', r.text)[0]
    pgs = re.findall(r'pgs[ ]*?=[ ]*?(\d+?);', r.text)[0]
    lx = re.findall(r'\'lx\':(\d+?),', r.text)[0]
    # up = re.findall(r'\'up\':(\d+?),', r.text)[0]
    # ls = re.findall(r'\'ls\':(\d+?),', r.text)[0]
    data = {
        'lx': lx,
        'fid': fid,
        'uid': uid,
        'pg': pgs,
        't': params[0],
        'k': params[1],
    }
    if check_password(r) == Constants.NEED_PWD:
        data['pwd'] = password
    # print(data)
    updater.update_text("Getting File Url...")
    r = requests.post(Constants.FILE_MORE_AJAX_URL, headers=headers, data=data)
    response = json.loads(r.text)
    if response['zt'] == 1:
        file_url = []
        for i in response['text']:
            file_url.append([i['id'], i['name_all']])
    else:
        # print('Get Url Failed!')
        return
    pre_params.set_file_url_with_name(file_url)
    file_url = get_file(pre_params)
    pre_params.set_file_url_with_name(file_url)
    updater.update_text("File Url Got!")
    updater.update_text("-"*50)
    updater.update_text("Start Downloading...")
    download_file(pre_params)


def update_progress_bar(ui: mainWindow.Ui_MainWindow, progress: int):
    ui.progressBar.setValue(progress)


def update_text_browser(ui: mainWindow.Ui_MainWindow, text: str):
    ui.textBrowser.append(text)


def get_dir(ui: mainWindow.Ui_MainWindow):
    directory = QFileDialog.getExistingDirectory(None, "Select Directory")
    ui.DirText.setText(directory)


def start_click(ui: mainWindow.Ui_MainWindow):
    # print('Start Clicked!')
    ui.progressBar.setValue(0)
    ui.progressBar.setMinimum(0)
    ui.progressBar.setMaximum(100)
    ui.progressBar.setTextVisible(True)
    ui.textBrowser.setText('')
    url = ui.LinkText.text()
    dir = ui.DirText.text() + os.sep
    password = ui.PwdText.text()
    updater: UpdateSignal = UpdateSignal()
    updater.update_text_signal.connect(lambda text: update_text_browser(ui, text))
    updater.update_progressBar_signal.connect(lambda progress: update_progress_bar(ui, progress))
    pre_params = Variable(url, password, dir, updater)
    # get_files_url(pre_params)
    worker = Worker(get_files_url, pre_params)
    ui.threadpool = QThreadPool()
    ui.threadpool.start(worker)
    ui.progressBar.setVisible(True)


if '__main__' == __name__:
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    ui = mainWindow.Ui_MainWindow()
    ui.setupUi(main_window)
    pwd = os.path.join(os.getcwd(), 'Download')
    ui.DirText.setText(pwd)
    ui.progressBar.setVisible(False)
    ui.DirBtn.clicked.connect(lambda: get_dir(ui))
    ui.StartBtn.clicked.connect(lambda: start_click(ui))
    main_window.show()
    sys.exit(app.exec_())
