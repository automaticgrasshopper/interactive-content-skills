#!/bin/bash
# 互动影视 Lab · 本地服务器一键启动（仅本机访问，不对外发布）
# 双击本文件即可：启动本地前台(localhost:8000) + 自动打开分镜工作台。
# 关掉这个终端窗口 = 关掉服务器。

# 切到脚本所在目录（仓库根）
cd "$(dirname "$0")" || exit 1

PORT=8000
# 端口被占则顺延找一个空的
while lsof -i :$PORT >/dev/null 2>&1; do
  PORT=$((PORT+1))
done

URL="http://localhost:$PORT/h5/"

echo "======================================================"
echo "  互动影视 Lab · 本地前台已启动"
echo "  地址： $URL"
echo "  提示： 这是只在本机运行的临时前台，别人访问不到。"
echo "        关掉本窗口即停止服务器。"
echo "======================================================"
echo ""

# 稍等半秒再开浏览器，确保服务器起来了
( sleep 0.8; open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL" ) &

# 前台运行 http server（Ctrl+C 或关窗口即停）
python3 -m http.server $PORT
