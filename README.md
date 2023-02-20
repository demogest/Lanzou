# Intro

light weight tool to download multiple files within one share link

一个用来批量下载同一蓝奏云分享链接中大量文件的小工具

# Dependencies

have a look at *requirements.txt*

# Usage

1. Clone this repo

   ```shell
   git clone https://github.com/demogest/Lanzou.git
   ```

2. Install dependencies

   ```shell
   pip install -r requirements.txt
   ```

3. Run main.py

   ```shell
   python ./main.py
   ```

4. Input the share link and password(if have)

5. click select to choose the directory or leave default

6. click start button and wait until complete

Or you can just download binary file which packed by pyinstaller from release page.

# Notice

- Once you click the start button, the download procedure won't stop until complete, even if you close the GUI
- This tool didn't adapt to link that only have one file.