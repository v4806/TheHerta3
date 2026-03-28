"""
导出基类模块

提供统一的导出架构，支持第三代和第四代功能：
- ExportBaseV3: 第三代导出基类，包含公共导出逻辑
- BufferExportMixin: 缓冲区导出混入类
- VersionAwareExportFactory: 版本感知导出工厂

使用方法：
- 第三代模式：直接使用各游戏类型的ModModel类
- 第四代模式：通过VersionAwareExportFactory创建导出器
"""
import os
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

from ..config.main_config import GlobalConfig
from ..config.version_config import VersionManager
from ..helper.ssmt4_utils import SSMT4Utils, ImportConfigHelper
from ..common.m_ini_builder import M_IniBuilder
from ..common.m_ini_helper import M_IniHelper
from ..base.m_global_key_counter import M_GlobalKeyCounter


class ExportBaseV3(ABC):
    """
    第三代导出基类
    
    提供公共的导出逻辑和版本感知功能
    """
    
    def __init__(self, blueprint_model):
        """
        初始化导出器
        
        Args:
            blueprint_model: 蓝图模型实例
        """
        self.blueprint_model = blueprint_model
        self.drawib_drawibmodel_dict: Dict = {}
        self._version = VersionManager.get_current_version()
    
    @property
    def is_gen4_mode(self) -> bool:
        """检查是否为第四代模式"""
        return VersionManager.is_gen4()
    
    def get_unique_str_for_draw_ib(self, draw_ib: str) -> str:
        """
        获取DrawIB对应的unique_str（用于SSMT4格式）
        
        Args:
            draw_ib: DrawIB名称
            
        Returns:
            str: unique_str，如果不是SSMT4格式则返回空字符串
        """
        import_json_dict = SSMT4Utils.check_and_try_generate_import_json()
        return SSMT4Utils.find_ssmt4_unique_str(draw_ib, import_json_dict)
    
    def get_buffer_prefix(self, draw_ib: str, unique_str: str = "") -> str:
        """
        获取缓冲区文件名前缀
        
        Args:
            draw_ib: DrawIB名称
            unique_str: SSMT4格式的unique_str
            
        Returns:
            str: 缓冲区文件名前缀
        """
        return unique_str if unique_str else draw_ib
    
    def generate_buffer_files(self, output_folder: str):
        """生成缓冲区文件（子类必须实现）"""
        raise NotImplementedError("Subclasses must implement generate_buffer_files")
    
    def generate_ini_file(self):
        """生成INI配置文件（子类必须实现）"""
        raise NotImplementedError("Subclasses must implement generate_ini_file")
    
    def copy_texture_files(self):
        """复制纹理文件到输出目录"""
        from ..config.properties_generate_mod import Properties_GenerateMod
        if Properties_GenerateMod.forbid_auto_texture_ini():
            return
        for drawib_model in self.drawib_drawibmodel_dict.values():
            M_IniHelper.move_slot_style_textures(draw_ib_model=drawib_model)
    
    @abstractmethod
    def export(self):
        """执行导出操作（子类必须实现）"""
        pass


class BufferExportMixin:
    """
    缓冲区导出混入类
    
    提供静态方法用于写入各类缓冲区文件
    """
    
    @staticmethod
    def write_buffer_files(drawib_model, output_folder: str, buffer_prefix: str = ""):
        """
        写入缓冲区文件
        
        Args:
            drawib_model: DrawIB模型实例
            output_folder: 输出文件夹路径
            buffer_prefix: 缓冲区文件名前缀
        """
        from ..helper.buffer_export_helper import BufferExportHelper
        
        prefix = buffer_prefix or drawib_model.draw_ib
        
        # 写入索引缓冲区
        if drawib_model.combine_ib:
            ib_filename = prefix + "-Index.buf"
            ib_filepath = os.path.join(output_folder, ib_filename)
            BufferExportHelper.write_buf_ib_r32_uint(drawib_model.ib, ib_filepath)
        else:
            for submesh_model in drawib_model.submesh_model_list:
                ib = drawib_model.submesh_ib_dict.get(submesh_model.unique_str, [])
                ib_filename = submesh_model.unique_str + "-Index.buf"
                ib_filepath = os.path.join(output_folder, ib_filename)
                BufferExportHelper.write_buf_ib_r32_uint(ib, ib_filepath)
        
        # 写入分类缓冲区
        for category, category_buf in drawib_model.category_buffer_dict.items():
            category_buf_filename = prefix + "-" + category + ".buf"
            category_buf_filepath = os.path.join(output_folder, category_buf_filename)
            with open(category_buf_filepath, 'wb') as file_obj:
                category_buf.tofile(file_obj)
        
        # 写入形态键缓冲区
        for shapekey_name, shapekey_buf in drawib_model.shapekey_name_bytelist_dict.items():
            shapekey_buf_filename = prefix + "-Position." + shapekey_name + ".buf"
            shapekey_buf_filepath = os.path.join(output_folder, shapekey_buf_filename)
            with open(shapekey_buf_filepath, 'wb') as file_obj:
                shapekey_buf.tofile(file_obj)


class VersionAwareExportFactory:
    """
    版本感知导出工厂
    
    根据当前版本设置创建对应的导出器实例
    """
    
    @staticmethod
    def create_exporter(logic_name: str, blueprint_model):
        """
        创建导出器实例
        
        Args:
            logic_name: 游戏逻辑名称（如GIMI、WWMI等）
            blueprint_model: 蓝图模型实例
            
        Returns:
            对应版本的导出器实例
        """
        if VersionManager.is_gen4():
            return VersionAwareExportFactory._create_gen4_exporter(logic_name, blueprint_model)
        else:
            return VersionAwareExportFactory._create_gen3_exporter(logic_name, blueprint_model)
    
    @staticmethod
    def _create_gen4_exporter(logic_name: str, blueprint_model):
        """创建第四代导出器"""
        from . import gimi, wwmi, srmi, himi, zzmi, efmi, identityv, snowbreak, unity, yysls
        
        exporter_map = {
            "GIMI": gimi.ModModelGIMI,
            "WWMI": wwmi.ModModelWWMI,
            "SRMI": srmi.ModModelSRMI,
            "HIMI": himi.ModModelHIMI,
            "ZZMI": zzmi.ModModelZZMI,
            "EFMI": efmi.ModModelEFMI,
            "IdentityV2": identityv.ModModelIdentityV,
            "SnowBreak": snowbreak.ModModelSnowBreak,
            "UnityVS": unity.ModModelUnity,
            "UnityCS": unity.ModModelUnity,
            "YYSLS": yysls.ModModelYYSLS,
        }
        
        exporter_class = exporter_map.get(logic_name)
        if exporter_class:
            return exporter_class()
        
        raise ValueError(f"Unknown logic name for Gen4: {logic_name}")
    
    @staticmethod
    def _create_gen3_exporter(logic_name: str, blueprint_model):
        """创建第三代导出器"""
        from . import gimi, wwmi, srmi, himi, zzmi, efmi, identityv, snowbreak, unity, yysls
        
        exporter_map = {
            "GIMI": gimi.ModModelGIMI,
            "WWMI": wwmi.ModModelWWMI,
            "SRMI": srmi.ModModelSRMI,
            "HIMI": himi.ModModelHIMI,
            "ZZMI": zzmi.ModModelZZMI,
            "EFMI": efmi.ModModelEFMI,
            "IdentityV2": identityv.ModModelIdentityV,
            "SnowBreak": snowbreak.ModModelSnowBreak,
            "UnityVS": unity.ModModelUnity,
            "UnityCS": unity.ModModelUnity,
            "YYSLS": yysls.ModModelYYSLS,
        }
        
        exporter_class = exporter_map.get(logic_name)
        if exporter_class:
            return exporter_class()
        
        raise ValueError(f"Unknown logic name for Gen3: {logic_name}")
