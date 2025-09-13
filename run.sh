#!/bin/bash

# MCP 服务管理脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp-server.pid"
APP_PATH="/root/mcp/xhs_mcp/venv/bin/python"
APP_SCRIPT="mcp_server_playwright.py"
LOG_FILE="$SCRIPT_DIR/mcp-server.log"

start_server() {
    echo "🚀 启动 MCP 服务..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "✅ 服务已在运行，PID: $PID"
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi

    cd "$SCRIPT_DIR"
#    $APP_PATH $APP_SCRIPT &
    nohup $APP_PATH $APP_SCRIPT > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "✅ 服务启动完成，PID: $(cat "$PID_FILE")"
}

stop_server() {
    echo "🛑 停止 MCP 服务..."
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ 没有找到运行的服务"
        return 1
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        # 先尝试优雅停止
        kill -TERM "$PID" 2>/dev/null
        sleep 2

        # 检查是否还在运行
        if ps -p "$PID" > /dev/null; then
            echo "⚠️  服务仍在运行，强制停止..."
            kill -9 "$PID"
            sleep 1
        fi

        rm -f "$PID_FILE"
        echo "✅ 服务已停止"
    else
        echo "❌ 进程不存在，清理 PID 文件"
        rm -f "$PID_FILE"
    fi
}

restart_server() {
    echo "🔄 重启 MCP 服务..."
    stop_server
    sleep 1
    start_server
}

check_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "✅ 服务正在运行，PID: $PID"
            return 0
        else
            echo "❌ PID 文件存在但服务未运行"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo "❌ 服务未运行"
        return 1
    fi
}

# 显示使用说明
show_usage() {
    echo "使用方法: $0 {start|stop|restart|status}"
    echo "  start    - 启动服务"
    echo "  stop     - 停止服务"
    echo "  restart  - 重启服务"
    echo "  status   - 查看服务状态"
}

# 主逻辑
case "${1:-}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        check_status
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

exit 0