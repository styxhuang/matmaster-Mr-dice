#!/bin/bash

# 检查参数
if [ $# -eq 0 ]; then
    echo "Usage: $0 {test|uat|prod}"
    echo "  test - 使用测试环境配置"
    echo "  uat  - 使用UAT环境配置"
    echo "  prod - 使用生产环境配置"
    exit 1
fi

ENV=$1

# 验证环境参数
if [[ "$ENV" != "test" && "$ENV" != "uat" && "$ENV" != "prod" ]]; then
    echo "错误: 无效的环境参数 '$ENV'"
    echo "支持的环境: test, uat, prod"
    exit 1
fi

echo "MOFdb SQL数据库部署环境: $ENV"

# 停止服务 - 精确匹配
pkill -f "server.py.*50001"
pkill -f "adk web.*50002"

# 重启 MOF Server
source /home/Mr-Dice/bohrium_setup_env.sh
cd /home/Mr-Dice/mofdbsql_database/Mofdb_Server

# 根据环境参数加载对应的配置文件
case $ENV in
    "test")
        source /home/Mr-Dice/export_test_env.sh
        echo "已加载测试环境配置"
        ;;
    "uat")
        source /home/Mr-Dice/export_uat_env.sh
        echo "已加载UAT环境配置"
        ;;
    "prod")
        source /home/Mr-Dice/export_prod_env.sh
        echo "已加载生产环境配置"
        ;;
esac

nohup python server.py --port 50001 > server.log 2>&1 &

# 重启 Agent
cd /home/Mr-Dice/mofdbsql_database
nohup adk web --port 50002 --host 0.0.0.0 > agent_web.log 2>&1 &