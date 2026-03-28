'''
SRMI
'''
import os
import bpy

from ..config.main_config import GlobalConfig
from ..utils.json_utils import JsonUtils
from ..utils.config_utils import ConfigUtils
from ..common.draw_ib_model import DrawIBModel
from ..helper.ssmt4_utils import SSMT4Utils

from ..base.m_global_key_counter import M_GlobalKeyCounter
from ..blueprint.blueprint_model import BluePrintModel

from ..common.m_ini_builder import M_IniBuilder,M_IniSection,M_SectionType
from ..config.properties_generate_mod import Properties_GenerateMod
from ..common.m_ini_helper import M_IniHelper,M_IniHelper

from ..common.m_ini_helper_gui import M_IniHelperGUI


class ModModelSRMI:
    def __init__(self):
        # (1) 统计全局分支模型
        self.branch_model = BluePrintModel()

        # (2) 抽象每个DrawIB为DrawIBModel
        self.drawib_drawibmodel_dict:dict[str,DrawIBModel] = {}
        self.parse_draw_ib_draw_ib_model_dict()

        # (3) 这些属性用于ini生成
        self.vlr_filter_index_indent = ""
        self.texture_hash_filter_index_dict = {}

    def parse_draw_ib_draw_ib_model_dict(self):
        '''
        根据obj的命名规则，推导出DrawIB并抽象为DrawIBModel
        支持第三代(SSMT3)和第四代(SSMT4)格式
        
        第三代格式：物体名称为 DrawIB-Component.Alias，文件夹结构为 DrawIB/TYPE_xxx/
        第四代格式：物体名称为 DrawIB-IndexCount-FirstIndex.Alias，文件夹结构为 DrawIB-IndexCount-FirstIndex/TYPE_xxx/
        '''
        draw_ib_gametypename_dict = SSMT4Utils.check_and_try_generate_import_json()
        
        for draw_ib in self.branch_model.draw_ib__component_count_list__dict.keys():
            unique_str = SSMT4Utils.find_ssmt4_unique_str(draw_ib, draw_ib_gametypename_dict)
            
            if unique_str:
                print(f"检测到 SSMT4 格式: draw_ib={draw_ib}, unique_str={unique_str}")
            
            draw_ib_model = DrawIBModel(draw_ib=draw_ib, branch_model=self.branch_model, unique_str=unique_str)
            self.drawib_drawibmodel_dict[draw_ib] = draw_ib_model


    
    def add_vertex_limit_raise_section(self,config_ini_builder:M_IniBuilder,draw_ib_model:DrawIBModel):
        '''
        VertexLimitRaise部分，用于突破顶点数限制
        '''
        d3d11GameType = draw_ib_model.d3d11GameType
        draw_ib = draw_ib_model.draw_ib

        if d3d11GameType.GPU_PreSkinning:
            vertexlimit_section = M_IniSection(M_SectionType.TextureOverrideVertexLimitRaise)

            vertexlimit_section.append("[TextureOverride_" + draw_ib + "_" + draw_ib_model.draw_ib_alias + "_Draw" + "]")
            vertexlimit_section.append("hash = " + draw_ib_model.import_config.vertex_limit_hash)

            if draw_ib_model.draw_number > draw_ib_model.import_config.original_vertex_count:
                vertexlimit_section.append("override_byte_stride = " + str(d3d11GameType.CategoryStrideDict["Position"]))
                vertexlimit_section.append("override_vertex_count = " + str(draw_ib_model.draw_number))
                # 这里步长为4，是因为override_byte_stride * override_vertex_count 后要除以 4来得到 uav的num_elements
                vertexlimit_section.append("uav_byte_stride = 4")
                vertexlimit_section.new_line()

            config_ini_builder.append_section(vertexlimit_section)

    
    def add_resource_texture_sections(self,ini_builder,draw_ib_model:DrawIBModel):
        '''
        Add texture resource.
        只有槽位风格贴图会用到，因为Hash风格贴图有专门的方法去声明这个。
        '''
        if Properties_GenerateMod.forbid_auto_texture_ini():
            return 
        
        resource_texture_section = M_IniSection(M_SectionType.ResourceTexture)
        for partname, texture_markup_info_list in draw_ib_model.import_config.partname_texturemarkinfolist_dict.items():
            for texture_markup_info in texture_markup_info_list:
                if texture_markup_info.mark_type == "Slot":
                    resource_texture_section.append("[" + texture_markup_info.get_resource_name() + "]")
                    resource_texture_section.append("filename = Texture/" + texture_markup_info.mark_filename)
                    resource_texture_section.new_line()

        ini_builder.append_section(resource_texture_section)


    def add_texture_override_vb_sections(self,config_ini_builder:M_IniBuilder,draw_ib_model:DrawIBModel):
        d3d11GameType = draw_ib_model.d3d11GameType
        draw_ib = draw_ib_model.draw_ib

        if d3d11GameType.GPU_PreSkinning:
            texture_override_vb_section = M_IniSection(M_SectionType.TextureOverrideVB)
            texture_override_vb_section.append("; " + draw_ib)
            
            unique_str = getattr(draw_ib_model, 'unique_str', "")
            
            for category_name in d3d11GameType.OrderedCategoryNameList:
                category_hash = draw_ib_model.import_config.category_hash_dict[category_name]
                category_slot = d3d11GameType.CategoryExtractSlotDict[category_name]

                texture_override_vb_namesuffix = "VB_" + draw_ib + "_" + draw_ib_model.draw_ib_alias + "_" + category_name

                if category_name != "Position":
                    texture_override_vb_section.append("[TextureOverride_" + texture_override_vb_namesuffix + "]")
                    texture_override_vb_section.append("hash = " + category_hash)

                    if category_name != "Texcoord":
                        texture_override_vb_section.append("handling = skip")

                filterindex_indent_prefix = ""
                if category_name == d3d11GameType.CategoryDrawCategoryDict["Texcoord"]:
                    if self.vlr_filter_index_indent != "":
                        texture_override_vb_section.append("if vb0 == " + str(3000 + M_GlobalKeyCounter.generated_mod_number))

                for original_category_name, draw_category_name in d3d11GameType.CategoryDrawCategoryDict.items():
                    position_category_slot = d3d11GameType.CategoryExtractSlotDict["Position"]
                    blend_category_slot = d3d11GameType.CategoryExtractSlotDict["Blend"]
                     
                    if category_name == draw_category_name:
                        if original_category_name == "Position":
                            pass
                        elif original_category_name == "Blend":
                            if unique_str:
                                blend_resource_name = "Resource_" + unique_str.replace("-", "_") + "_Blend"
                                position_resource_name = "Resource_" + unique_str.replace("-", "_") + "_Position"
                                position_cs_resource_name = "Resource_" + unique_str.replace("-", "_") + "_PositionCS"
                                blend_cs_resource_name = "Resource_" + unique_str.replace("-", "_") + "_BlendCS"
                            else:
                                blend_resource_name = "Resource" + draw_ib + "Blend"
                                position_resource_name = "Resource" + draw_ib + "Position"
                                position_cs_resource_name = "Resource" + draw_ib + "PositionCS"
                                blend_cs_resource_name = "Resource" + draw_ib + "BlendCS"
                            
                            texture_override_vb_section.append("vb2 = " + blend_resource_name)
                            texture_override_vb_section.append("if DRAW_TYPE == 1")
                            texture_override_vb_section.append("  vb0 = " + position_resource_name)
                            texture_override_vb_section.append("draw = " + str(draw_ib_model.draw_number) + ", 0")
                            texture_override_vb_section.append("endif")
                            texture_override_vb_section.append("if DRAW_TYPE == 8")
                            texture_override_vb_section.append("  Resource\\SRMI\\PositionBuffer = ref " + position_cs_resource_name)
                            texture_override_vb_section.append("  Resource\\SRMI\\BlendBuffer = ref " + blend_cs_resource_name)
                            texture_override_vb_section.append("  $\\SRMI\\vertex_count = " + str(draw_ib_model.draw_number))
                            texture_override_vb_section.append("endif")
                            
                        else:
                            category_original_slot = d3d11GameType.CategoryExtractSlotDict[original_category_name]
                            if unique_str:
                                resource_name = "Resource_" + unique_str.replace("-", "_") + "_" + original_category_name
                            else:
                                resource_name = "Resource" + draw_ib + original_category_name
                            texture_override_vb_section.append(filterindex_indent_prefix + category_original_slot + " = " + resource_name)

                if category_name == d3d11GameType.CategoryDrawCategoryDict["Texcoord"]:
                    if self.vlr_filter_index_indent != "":
                        texture_override_vb_section.append("endif")
                
                if category_name == d3d11GameType.CategoryDrawCategoryDict["Position"]:
                    if len(self.branch_model.keyname_mkey_dict.keys()) != 0:
                        texture_override_vb_section.append("$active" + str(M_GlobalKeyCounter.generated_mod_number) + " = 1")

                        if Properties_GenerateMod.generate_branch_mod_gui():
                            texture_override_vb_section.append("$ActiveCharacter = 1")

                texture_override_vb_section.new_line()
            config_ini_builder.append_section(texture_override_vb_section)
            
            
    def add_texture_override_ib_sections(self,config_ini_builder:M_IniBuilder,draw_ib_model:DrawIBModel):
        texture_override_ib_section = M_IniSection(M_SectionType.TextureOverrideIB)
        draw_ib = draw_ib_model.draw_ib
        d3d11GameType = draw_ib_model.d3d11GameType

        unique_str = getattr(draw_ib_model, 'unique_str', "")
        
        if unique_str:
            for component_model in draw_ib_model._component_model_list:
                component_name = component_model.component_name
                first_index = getattr(component_model, 'first_index', 0)
                component_index = component_name.replace("Component ", "")
                
                style_part_name = "Component" + component_index
                ib_resource_name = draw_ib_model.PartName_IBResourceName_Dict.get(component_index, "")
                texture_override_ib_namesuffix = "IB_" + draw_ib + "_" + draw_ib_model.draw_ib_alias + "_" + style_part_name
                
                texture_override_ib_section.append("[TextureOverride_" + texture_override_ib_namesuffix + "]")
                texture_override_ib_section.append("hash = " + draw_ib)
                texture_override_ib_section.append("match_first_index = " + str(first_index))
                texture_override_ib_section.append("handling = skip")

                if self.vlr_filter_index_indent != "":
                    texture_override_ib_section.append("if vb0 == " + str(3000 + M_GlobalKeyCounter.generated_mod_number))

                ib_buf = draw_ib_model.componentname_ibbuf_dict.get(component_name, None)
                if ib_buf is None or len(ib_buf) == 0:
                    texture_override_ib_section.new_line()
                else:
                    texture_override_ib_section.append(self.vlr_filter_index_indent + "ib = " + ib_resource_name)
                    
                    if not Properties_GenerateMod.forbid_auto_texture_ini():
                        texture_markup_info_list = None
                        if component_model.final_ordered_draw_obj_model_list:
                            first_obj = component_model.final_ordered_draw_obj_model_list[0]
                            obj_full_name = f"{first_obj.draw_ib}-{first_obj.index_count}-{first_obj.first_index}"
                            print(f"调试: obj_full_name={obj_full_name}, is_ssmt4={first_obj.is_ssmt4}")
                            print(f"调试: partname_texturemarkinfolist_dict keys={list(draw_ib_model.import_config.partname_texturemarkinfolist_dict.keys())}")
                            texture_markup_info_list = draw_ib_model.import_config.partname_texturemarkinfolist_dict.get(obj_full_name, None)
                        if texture_markup_info_list is None:
                            texture_markup_info_list = draw_ib_model.import_config.partname_texturemarkinfolist_dict.get(component_index, None)
                        if texture_markup_info_list is None:
                            texture_markup_info_list = draw_ib_model.import_config.partname_texturemarkinfolist_dict.get("1", None)
                        print(f"调试: texture_markup_info_list={texture_markup_info_list}")
                        if texture_markup_info_list is not None:
                            for texture_markup_info in texture_markup_info_list:
                                if texture_markup_info.mark_type == "Slot":
                                    texture_override_ib_section.append(self.vlr_filter_index_indent + texture_markup_info.mark_slot + " = " + texture_markup_info.get_resource_name())
                    
                    if not d3d11GameType.GPU_PreSkinning:
                        for category_name in d3d11GameType.OrderedCategoryNameList:
                            category_hash = draw_ib_model.import_config.category_hash_dict[category_name]
                            category_slot = d3d11GameType.CategoryExtractSlotDict[category_name]

                            for original_category_name, draw_category_name in d3d11GameType.CategoryDrawCategoryDict.items():
                                if original_category_name == draw_category_name:
                                    category_original_slot = d3d11GameType.CategoryExtractSlotDict[original_category_name]
                                    if unique_str:
                                        resource_name = "Resource_" + unique_str.replace("-", "_") + "_" + original_category_name
                                    else:
                                        resource_name = "Resource" + draw_ib + original_category_name
                                    texture_override_ib_section.append(self.vlr_filter_index_indent + category_original_slot + " = " + resource_name)
                    
                    drawindexed_str_list = M_IniHelper.get_drawindexed_str_list(component_model.final_ordered_draw_obj_model_list)
                    for drawindexed_str in drawindexed_str_list:
                        texture_override_ib_section.append(drawindexed_str)
                    
                    if self.vlr_filter_index_indent:
                        texture_override_ib_section.append("endif")
                        texture_override_ib_section.new_line()
        else:
            for count_i,part_name in enumerate(draw_ib_model.import_config.part_name_list):
                match_first_index = draw_ib_model.import_config.match_first_index_list[count_i]

                style_part_name = "Component" + part_name
                ib_resource_name = "Resource_" + draw_ib+ "_" + style_part_name

                texture_override_ib_namesuffix = "IB_" + draw_ib  + "_" + draw_ib_model.draw_ib_alias  + "_" + style_part_name
                texture_override_ib_section.append("[TextureOverride_" + texture_override_ib_namesuffix + "]")
                texture_override_ib_section.append("hash = " + draw_ib)
                texture_override_ib_section.append("match_first_index = " + match_first_index)
                texture_override_ib_section.append("handling = skip")

                if self.vlr_filter_index_indent != "":
                    texture_override_ib_section.append("if vb0 == " + str(3000 + M_GlobalKeyCounter.generated_mod_number))

                ib_buf = draw_ib_model.componentname_ibbuf_dict.get("Component " + part_name,None)
                if ib_buf is None or len(ib_buf) == 0:
                    texture_override_ib_section.new_line()
                    continue

                texture_override_ib_section.append(self.vlr_filter_index_indent + "ib = " + ib_resource_name)

                if not Properties_GenerateMod.forbid_auto_texture_ini():
                    texture_markup_info_list = draw_ib_model.import_config.partname_texturemarkinfolist_dict.get(part_name,None)
                    if texture_markup_info_list is not None:
                        for texture_markup_info in texture_markup_info_list:
                            if texture_markup_info.mark_type == "Slot":
                                texture_override_ib_section.append(self.vlr_filter_index_indent + texture_markup_info.mark_slot + " = " + texture_markup_info.get_resource_name())

                if not d3d11GameType.GPU_PreSkinning:
                    for category_name in d3d11GameType.OrderedCategoryNameList:
                        category_hash = draw_ib_model.import_config.category_hash_dict[category_name]
                        category_slot = d3d11GameType.CategoryExtractSlotDict[category_name]

                        for original_category_name, draw_category_name in d3d11GameType.CategoryDrawCategoryDict.items():
                            if original_category_name == draw_category_name:
                                category_original_slot = d3d11GameType.CategoryExtractSlotDict[original_category_name]
                                texture_override_ib_section.append(self.vlr_filter_index_indent + category_original_slot + " = Resource" + draw_ib + original_category_name)

                component_name = "Component " + part_name 

                component_model = draw_ib_model.component_name_component_model_dict[component_name]
                drawindexed_str_list = M_IniHelper.get_drawindexed_str_list(component_model.final_ordered_draw_obj_model_list)
                for drawindexed_str in drawindexed_str_list:
                    texture_override_ib_section.append(drawindexed_str)
                
                if self.vlr_filter_index_indent != "":
                    texture_override_ib_section.append("endif")
                    texture_override_ib_section.new_line()


        config_ini_builder.append_section(texture_override_ib_section)

    def add_unity_cs_resource_vb_sections(self,config_ini_builder:M_IniBuilder,draw_ib_model:DrawIBModel):
        '''
        Add Resource VB Section (HSR3.2)
        '''
        resource_vb_section = M_IniSection(M_SectionType.ResourceBuffer)
        
        buffer_folder_name = GlobalConfig.get_buffer_folder_name()
        
        unique_str = getattr(draw_ib_model, 'unique_str', "")

        for category_name in draw_ib_model.d3d11GameType.OrderedCategoryNameList:
            if unique_str:
                resource_name = "Resource_" + unique_str.replace("-", "_") + "_" + category_name
                buf_filename = unique_str + "-" + category_name + ".buf"
            else:
                resource_name = "Resource" + draw_ib_model.draw_ib + category_name
                buf_filename = draw_ib_model.draw_ib + "-" + category_name + ".buf"
            
            resource_vb_section.append("[" + resource_name + "]")
            resource_vb_section.append("type = Buffer")
            resource_vb_section.append("stride = " + str(draw_ib_model.d3d11GameType.CategoryStrideDict[category_name]))
            resource_vb_section.append("filename = " + buffer_folder_name + "/" + buf_filename)
            resource_vb_section.new_line()
        
        for category_name in draw_ib_model.d3d11GameType.OrderedCategoryNameList:
            if category_name == "Position" or category_name == "Blend":
                if unique_str:
                    resource_name = "Resource_" + unique_str.replace("-", "_") + "_" + category_name + "CS"
                    buf_filename = unique_str + "-" + category_name + ".buf"
                else:
                    resource_name = "Resource" + draw_ib_model.draw_ib + category_name + "CS"
                    buf_filename = draw_ib_model.draw_ib + "-" + category_name + ".buf"
                
                resource_vb_section.append("[" + resource_name + "]")
                resource_vb_section.append("type = StructuredBuffer")
                resource_vb_section.append("stride = " + str(draw_ib_model.d3d11GameType.CategoryStrideDict[category_name]))
                resource_vb_section.append("filename = " + buffer_folder_name + "/" + buf_filename)
                resource_vb_section.new_line()

        for partname, ib_filename in draw_ib_model.PartName_IBBufferFileName_Dict.items():
            ib_resource_name = draw_ib_model.PartName_IBResourceName_Dict.get(partname, None)
            resource_vb_section.append("[" + ib_resource_name + "]")
            resource_vb_section.append("type = Buffer")
            resource_vb_section.append("format = DXGI_FORMAT_R32_UINT")
            resource_vb_section.append("filename = " + buffer_folder_name + "/" + ib_filename)
            resource_vb_section.new_line()
        
        config_ini_builder.append_section(resource_vb_section)
    


    def generate_unity_cs_config_ini(self):
        '''
        test
        '''
        config_ini_builder = M_IniBuilder()

        M_IniHelper.generate_hash_style_texture_ini(ini_builder=config_ini_builder,drawib_drawibmodel_dict=self.drawib_drawibmodel_dict)



        for draw_ib, draw_ib_model in self.drawib_drawibmodel_dict.items():

   
            # [TextureOverrideVertexLimitRaise]
            self.add_vertex_limit_raise_section(config_ini_builder=config_ini_builder,draw_ib_model=draw_ib_model) 
            # [TextureOverrideVB]
            self.add_texture_override_vb_sections(config_ini_builder=config_ini_builder,draw_ib_model=draw_ib_model) 
            # [TextureOverrideIB]
            self.add_texture_override_ib_sections(config_ini_builder=config_ini_builder,draw_ib_model=draw_ib_model) 

            # Resource.ini
            self.add_unity_cs_resource_vb_sections(config_ini_builder=config_ini_builder,draw_ib_model=draw_ib_model)
            self.add_resource_texture_sections(ini_builder=config_ini_builder,draw_ib_model=draw_ib_model)

            M_IniHelper.move_slot_style_textures(draw_ib_model=draw_ib_model)

            M_GlobalKeyCounter.generated_mod_number = M_GlobalKeyCounter.generated_mod_number + 1

        M_IniHelper.add_branch_key_sections(ini_builder=config_ini_builder,key_name_mkey_dict=self.branch_model.keyname_mkey_dict)
        M_IniHelper.add_shapekey_ini_sections(ini_builder=config_ini_builder,drawib_drawibmodel_dict=self.drawib_drawibmodel_dict)
        M_IniHelperGUI.add_branch_mod_gui_section(ini_builder=config_ini_builder,key_name_mkey_dict=self.branch_model.keyname_mkey_dict)

        config_ini_builder.save_to_file(GlobalConfig.path_generate_mod_folder() + GlobalConfig.workspacename + ".ini")
        