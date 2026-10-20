"""相机须已进入fastboot；从卡槽1的BODYDATA.DAT启动原厂恢复。"""
import argparse
from datetime import datetime
import uuid
from pathlib import Path
import sys

from .common import root_dir

from .sd_recovery import (ToolError, read_config, check_resources,
                          hardware_lock, RecoveryTransport, recover, check_connection)


def main(argv=None):
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-connection', action='store_true',
                        help='只枚举fastboot并查询型号，不读写分区、不重启')
    parser.add_argument('--sessions', type=Path, default=root_dir() / 'local' / 'sd-recovery' / 'sessions',
                        help='本次备份与日志的本地父目录（默认 local/sd-recovery/sessions）')
    args = parser.parse_args(argv)
    check_resources()
    config = read_config()
    folder = args.sessions / (datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    if args.check_connection:
        print('只检查fastboot连接：不读写分区、不重启。', flush=True)
        print('检查日志：' + str(folder), flush=True)
        with hardware_lock():
            result = check_connection(RecoveryTransport(folder), folder)
        print('连接正常，型号：' + result['identity']['product'], flush=True)
        print('本次没有执行救砖。需要恢复时，请保持fastboot就绪后运行恢复入口。', flush=True)
        return 0
    print('恢复来源：相机卡槽1根目录的 BODYDATA.DAT', flush=True)
    print('请使用电量充足的原厂电池，保持供电，安装期间不要拔卡。', flush=True)
    print('本次备份与日志：' + str(folder), flush=True)
    with hardware_lock():
        recover(RecoveryTransport(folder), folder, config)
    print('\n已发出SD恢复启动。请等待相机完成原厂更新并恢复取景。', flush=True)
    print('脚本不能确认机内安装结果；完成后请核对版本并检查正常开关机。', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ToolError, OSError, ValueError, KeyError, KeyboardInterrupt) as error:
        print('\n停止 [' + getattr(error, 'code', type(error).__name__) + ']：' + str(error), flush=True)
        if getattr(error, 'hint', ''):
            print('建议：' + error.hint, flush=True)
        print('若已创建会话，详情见 local/sd-recovery/sessions（或 --sessions 指定目录）的 result.json；写后读回失败时不会重启或自动重试。', flush=True)
        raise SystemExit(2)
