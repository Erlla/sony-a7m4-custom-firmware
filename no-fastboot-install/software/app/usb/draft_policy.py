from product_integrity import pinned, state_path

class DraftOnlyError(RuntimeError):
    code = 'INSTALLER_NOT_READY'

def require_device_access(operation):
    raise DraftOnlyError(f'{operation}: M4安装器尚未完成验收，此入口未开放；只读诊断已单独验证。需先完成M4加载器、模块上传、NOR同步与启动状态合同的后续评审。')

def require_native_installation():
    require_device_access('USB安装/恢复')
