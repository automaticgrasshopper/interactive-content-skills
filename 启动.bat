@echo off
chcp 65001 >nul
rem 互动影视节奏工作台 · 本地服务器一键启动（Windows 版，仅本机访问）
rem 双击本文件即可：启动本地前台 + 自动打开工作台。关掉本窗口 = 关掉服务器。
rem
rem 【为什么固定 8000？】浏览器的记录(localStorage)按"协议+域名+端口"隔离。
rem 端口一变就是另一份存储、旧记录读不到。所以这里锁死 8000 不再顺延，
rem 保证你每次打开都落在同一处、记录永远都在。

rem 切到脚本所在目录（仓库根）
cd /d "%~dp0"

set PORT=8000

rem 端口被占：不再顺延，直接提示（避免记录跟着端口分家）
netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo ======================================================
  echo   [警告] 端口 %PORT% 已被占用，无法启动。
  echo.
  echo   为了让记录始终存在同一处，本工具固定使用 %PORT%，不会自动换端口。
  echo   可能原因：已经开着一个本工作台窗口，或别的程序占用了 %PORT%。
  echo.
  echo   处理办法（任选其一）：
  echo    1^) 如果已经开着本工作台，直接用那个窗口即可，别重复开；
  echo    2^) 找到并关掉占用 %PORT% 的程序后，再双击本文件。
  echo ======================================================
  echo.
  pause
  exit /b 1
)

set URL=http://localhost:%PORT%/h5/index.html

echo ======================================================
echo   互动影视节奏工作台 · 本地前台已启动
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

rem 前台运行带“datapacks 直写接口”的本地服务器（关窗口即停）
rem 导出记录会直接落进 h5\datapacks\，免手选文件夹
python serve.py %PORT%
