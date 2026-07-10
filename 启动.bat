@echo off
chcp 65001 >nul
rem 互动影视 Lab · 本地服务器一键启动（Windows 版，仅本机访问）
rem 双击本文件即可：启动本地前台 + 自动打开工作台。关掉本窗口 = 关掉服务器。

rem 切到脚本所在目录（仓库根）
cd /d "%~dp0"

rem 找一个没被占用的端口（从 8000 起顺延）
set PORT=8000
:findport
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  set /a PORT+=1
  goto findport
)

set URL=http://localhost:%PORT%/h5/index.html

echo ======================================================
echo   互动影视 Lab · 本地前台已启动
echo   地址： %URL%
echo   提示： 这是只在本机运行的临时前台，别人访问不到。
echo         关掉本窗口即停止服务器。
echo ======================================================
echo.

rem 检测 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
  echo [错误] 没有检测到 Python。
  echo         请先安装 Python 3（https://www.python.org/downloads/，安装时勾选 Add to PATH），
  echo         或改用 Node：在本目录执行  npx serve -l %PORT%
  echo.
  pause
  exit /b 1
)

rem 稍等再开浏览器，确保服务器起来了；优先 Chrome，没有则用默认浏览器
start "" cmd /c "timeout /t 1 >nul & (start chrome "%URL%" || start "" "%URL%")"

rem 前台运行 http server（关窗口即停）
python -m http.server %PORT%
