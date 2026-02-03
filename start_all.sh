#!/bin/bash

pkill -9 -f "python server.py"

# 默认值
ENV="test"
DATABASE="all"
NOHUP="true"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENV="$2"
            shift 2
            ;;
        -db|--database)
            DATABASE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [-e|--env ENVIRONMENT] [-db|--database DATABASE]"
            echo ""
            echo "Options:"
            echo "  -e, --env ENVIRONMENT    环境选择: test, uat, prod (默认: test)"
            echo "  -db, --database DATABASE 数据库选择: bohriumpublic, mofdbsql, openlam, optimade, all (默认: all)"
            echo "  -nohup, --nohup VALUE    是否后台运行: true, false (默认: true)"
            echo "  -h, --help               显示此帮助信息"
            echo ""
            echo "Examples:"
            echo "  $0                                    # 启动所有数据库服务（测试环境）"
            echo "  $0 -e uat                            # 启动所有数据库服务（UAT环境）"
            echo "  $0 -db bohriumpublic                 # 只启动Bohrium public服务（测试环境）"
            echo "  $0 -e prod -db mofdbsql             # 只启动MOFdb SQL服务（生产环境）"
            echo "  $0 --env uat --database openlam     # 只启动OpenLAM服务（UAT环境）"
            echo "  $0 --nohup false                    # 以前台方式运行所有服务"
            exit 0
            ;;
        -nohup|--nohup)
            NOHUP="$2"
            shift 2
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            echo "使用 '$0 --help' 查看帮助信息"
            exit 1
            ;;
    esac
done

# 验证环境参数
if [[ "$ENV" != "test" && "$ENV" != "uat" && "$ENV" != "prod" ]]; then
    echo "错误: 无效的环境参数 '$ENV'"
    echo "支持的环境: test, uat, prod"
    exit 1
fi

# 验证数据库参数
if [[ "$DATABASE" != "bohriumpublic" && "$DATABASE" != "mofdbsql" && "$DATABASE" != "openlam" && "$DATABASE" != "optimade" && "$DATABASE" != "all" ]]; then
    echo "错误: 无效的数据库参数 '$DATABASE'"
    echo "支持的数据库: bohriumpublic, mofdbsql, openlam, optimade, all"
    exit 1
fi

echo "启动环境: $ENV"
echo "启动数据库: $DATABASE"
echo "后台运行: $NOHUP"

pkill -f "python"

source /home/Mr-Dice/bohrium_setup_env.sh

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

# 根据是否后台运行，设置命令前后缀
if [[ "$NOHUP" == "true" ]]; then
    RUN_PREFIX="nohup "
    RUN_SUFFIX=" 2>&1 &"
elif [[ "$NOHUP" == "false" ]]; then
    RUN_PREFIX=""
    RUN_SUFFIX=""
else
    echo "错误: 无效的nohup参数 '$NOHUP'"
    echo "支持的nohup参数: true, false"
    exit 1
fi

# 非后台模式下，禁止一次性启动全部服务，避免前台阻塞造成"卡住"体验
if [[ "$NOHUP" == "false" && "$DATABASE" == "all" ]]; then
    echo "错误: 非后台模式(--nohup false)下不能使用 -db all。请指定单个数据库或改为后台运行。"
    exit 1
fi

# 根据数据库参数启动对应的服务
case $DATABASE in
    "bohriumpublic"|"all")
        cd /home/Mr-Dice/bohriumpublic_database/Bohriumpublic_Server
        if [[ "$NOHUP" == "true" ]]; then
            ${RUN_PREFIX}python server.py --port 50001 > server_50001.log 2>&1 &
            echo "Bohrium public server started, log: $(pwd)/server_50001.log"
        else
            python server.py --port 50001
        fi
        ;;
esac

case $DATABASE in
    "mofdbsql"|"all")
        cd /home/Mr-Dice/mofdbsql_database/Mofdb_Server
        if [[ "$NOHUP" == "true" ]]; then
            ${RUN_PREFIX}python server.py --port 50002 > server_50002.log 2>&1 &
            echo "MOFdb SQL server started, log: $(pwd)/server_50002.log"
        else
            python server.py --port 50002
        fi
        ;;
esac

case $DATABASE in
    "openlam"|"all")
        cd /home/Mr-Dice/openlam_database/Openlam_Server
        if [[ "$NOHUP" == "true" ]]; then
            ${RUN_PREFIX}python server.py --port 50003 > server_50003.log 2>&1 &
            echo "OpenLAM server started, log: $(pwd)/server_50003.log"
        else
            python server.py --port 50003
        fi
        ;;
esac

case $DATABASE in
    "optimade"|"all")
        cd /home/Mr-Dice/optimade_database/Optimade_Server
        if [[ "$NOHUP" == "true" ]]; then
            ${RUN_PREFIX}python server.py --port 50004 > server_50004.log 2>&1 &
            echo "Optimade server started, log: $(pwd)/server_50004.log"
        else
            python server.py --port 50004
        fi
        ;;
esac

ps -ef | grep "python"