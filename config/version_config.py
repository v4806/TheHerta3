"""
版本控制模块

提供第三代和第四代功能切换的基础设施：
- Properties_VersionControl: Blender属性组，包含第四代测试开关
- VersionManager: 版本管理器，提供版本判断方法

使用方法：
- 默认使用第三代代码路径
- 开启enable_gen4_mode后使用第四代代码路径
"""
import bpy


class Properties_VersionControl(bpy.types.PropertyGroup):
    """
    版本控制属性组
    
    用于在Blender场景中存储版本切换设置
    """
    
    enable_gen4_mode: bpy.props.BoolProperty(
        name="启用第四代功能(测试)",
        description="开启后将使用第四代代码路径执行导入/导出操作。关闭时使用第三代代码路径，确保向后兼容性。",
        default=False
    )  # type: ignore

    @classmethod
    def is_gen4_mode_enabled(cls) -> bool:
        """检查第四代模式是否启用"""
        try:
            return bpy.context.scene.properties_version_control.enable_gen4_mode
        except AttributeError:
            return False

    @classmethod
    def set_gen4_mode(cls, enabled: bool):
        """设置第四代模式开关"""
        try:
            bpy.context.scene.properties_version_control.enable_gen4_mode = enabled
        except AttributeError:
            pass


class VersionManager:
    """
    版本管理器
    
    提供版本判断和切换的静态方法
    - GEN3 = 3: 第三代版本常量
    - GEN4 = 4: 第四代版本常量
    """
    GEN3 = 3
    GEN4 = 4
    
    _current_version = None
    
    @classmethod
    def get_current_version(cls) -> int:
        """获取当前版本号（GEN3或GEN4）"""
        if cls._current_version is not None:
            return cls._current_version
        return cls.GEN4 if Properties_VersionControl.is_gen4_mode_enabled() else cls.GEN3
    
    @classmethod
    def set_version(cls, version: int):
        """手动设置版本号"""
        if version in (cls.GEN3, cls.GEN4):
            cls._current_version = version
    
    @classmethod
    def is_gen4(cls) -> bool:
        """检查是否为第四代模式"""
        return cls.get_current_version() == cls.GEN4
    
    @classmethod
    def is_gen3(cls) -> bool:
        """检查是否为第三代模式"""
        return cls.get_current_version() == cls.GEN3
    
    @classmethod
    def reset(cls):
        """重置版本状态，下次调用时重新从属性读取"""
        cls._current_version = None


def register():
    """注册版本控制属性组"""
    bpy.utils.register_class(Properties_VersionControl)
    bpy.types.Scene.properties_version_control = bpy.props.PointerProperty(type=Properties_VersionControl)


def unregister():
    """注销版本控制属性组"""
    del bpy.types.Scene.properties_version_control
    bpy.utils.unregister_class(Properties_VersionControl)
