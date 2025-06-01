@echo off
echo 正在安装SRT翻译工具所需的依赖包...
echo.

pip install srt
pip install tkinterdnd2
pip install requests
pip install ollama
pip install charset-normalizer

echo.
echo 依赖包安装完成！
echo 现在可以运行 python AI_Trans.py 启动翻译工具
pause 