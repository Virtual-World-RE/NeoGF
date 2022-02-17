#!/usr/bin/env python3
from pathlib import Path
from struct import unpack
from enum import IntFlag

__version__ = "0.0.1"
__author__ = "rigodron, algoflash, GGLinnk"
__license__ = "MIT"
__status__ = "developpement"


class HSDModelEmptyFileError(Exception) : pass
class HSDModelInvalidModelHeaderError(Exception) : pass


# new
class ProjectionTypeEnum(IntFlag):
    PERSPECTIVE = 1
    FRUSTRUM = 2
    ORTHO = 3


class LObjFlagsEnum(IntFlag):
    AMBIANT = 0
    INFINITE = 1
    POINT = 2
    SPOT = 3
    DIFFUSE = 4
    SPECULAR = 8
    ALPHA = 16
    HIDDEN = 32
    RAW_PARAM = 64
    DIFF_DIRTY = 128
    SPEC_DIRTY = 256


class LObjAttenuationFlagsEnum(IntFlag):
    LIGHT_ATTN_NONE = 0
    LIGHT_ATTN = 1


class JObjFlagsEnum(IntFlag):
    NULL = 0
    SKELETON = 1
    SKELETON_ROOT = 2
    ENVELOPE_MODEL = 4
    CLASSICAL_SCALING = 8
    HIDDEN = 0x10
    PTCL = 0x20
    MTX_DIRTY = 0x40
    LIGHTING = 0x80
    TEXGEN = 0x100
    BILLBOARD = 0x200
    VBILLBOARD = 0x400
    HBILLBOARD = 0x600
    RBILLBOARD = 0x800
    INSTANCE = 0x1000
    PBILLBOARD = 0x2000
    SPLINE = 0x4000
    FLIP_IK = 0x8000
    SPECULAR = 0x10000
    USE_QUATERNION = 0x20000
    OPA = 0x40000
    XLU = 0x80000
    TEXEDGE = 0x100000
    JOINT1 = 0x200000
    JOINT2 = 0x400000
    EFFECTOR = 0x600000
    USER_DEFINED_MTX = 0x800000
    MTX_INDEPEND_PARENT = 0x1000000
    MTX_INDEPEND_SRT = 0x2000000
    MTX_SCALE_COMPENSATE = 0x4000000
    ROOT_OPA = 0x10000000
    ROOT_XLU = 0x20000000
    ROOT_TEXEDGE = 0x40000000


class RenderFlagsEnum(IntFlag):
    USER = 0x80000000
    CONSTANT = 1
    VERTEX = 2
    BOTH = 3
    DIFFUSE = 4
    SPECULAR = 8
    TEX0 = 0x10
    TEX1 = 0x20
    TEX2 = 0x40
    TEX3 = 0x80
    TEX4 = 0x100
    TEX5 = 0x200
    TEX6 = 0x400
    TEX7 = 0x800
    TOON = 0x1000
    ALPHA_MAT = 0x2000
    ALPHA_VTX = 0x4000
    ALPHA_BOTH = 0x6000
    ZOFST = 0x1000000
    EFFECT = 0x2000000
    SHADOW = 0x4000000
    ZMODE_ALWAYS = 0x8000000
    DF_ALL = 0x10000000
    NO_ZUPDATE = 0x20000000
    XLU = 0x40000000


class GXTexGenSrcEnum(IntFlag):
    GX_TEXMAP0 = 0x0
    GX_TEXMAP1 = 0x1
    GX_TEXMAP2 = 0x2
    GX_TEXMAP3 = 0x3
    GX_TEXMAP4 = 0x4
    GX_TEXMAP5 = 0x5
    GX_TEXMAP6 = 0x6
    GX_TEXMAP7 = 0x7
    GX_MAX_TEXMAP = 0x8
    GX_TEXMAP_NULL = 0x9
    GX_TEXMAP_DISABLE = 0xA


class TexMapIdEnum(IntFlag):
    GX_TG_POS = 0x0
    GX_TG_NRM = 0x1
    GX_TG_BINRM = 0x2
    GX_TG_TANGENT = 0x3
    GX_TG_TEX0 = 0x4
    GX_TG_TEX1 = 0x5
    GX_TG_TEX2 = 0x6
    GX_TG_TEX3 = 0x7
    GX_TG_TEX4 = 0x8
    GX_TG_TEX5 = 0x9
    GX_TG_TEX6 = 0xA
    GX_TG_TEX7 = 0xB
    GX_TG_TEXCOORD0 = 0xC
    GX_TG_TEXCOORD1 = 0xD
    GX_TG_TEXCOORD2 = 0xE
    GX_TG_TEXCOORD3 = 0xF
    GX_TG_TEXCOORD4 = 0x10
    GX_TG_TEXCOORD5 = 0x11
    GX_TG_TEXCOORD6 = 0x12
    GX_TG_COLOR0 = 0x13
    GX_TG_COLOR1 = 0x14


class AlphaOperationEnum(IntFlag):
    NONE = 0x00
    ALPHAMASK = 0x10
    BLEND = 0x20
    MODULATE = 0x30
    REPLACE = 0x40
    PASS = 0x50
    ADD = 0x60
    SUB = 0x70


class ColorOperationEnum(IntFlag):
    NONE = 0
    ALPHA_MASK = 1
    RGB_MASK = 2
    BLEND = 3
    MODULATE = 4
    REPLACE = 5
    PASS = 6
    ADD = 7
    SUB = 8


class CoordTypeEnum(IntFlag):
    UV = 0
    REFLECTION = 1
    HILIGHT = 2
    SHADOW = 3
    TOON = 4
    GRADATION = 5


class MagFilterEnum(IntFlag):
    GX_NEAR = 0
    GX_LINEAR = 1
    GX_NEAR_MIP_NEAR = 2
    GX_LIN_MIP_NEAR = 3
    GX_NEAR_MIP_LIN = 4
    GX_LIN_MIP_LIN = 5


class WrapEnum(IntFlag):
    CLAMP = 0
    REPEAT = 1
    MIRROR = 2


class PObjFlagsEnum(IntFlag):
    UNKNOWN0 = 1
    UNKNOWN1 = 2
    ANIM = 8
    SHAPE_ANIM = 0x1000
    ENVELOPE = 0x2000
    CULLBACK = 0x4000
    CULLFRONT = 0x8000


class HSDNode:
    __data_block_offset = None
    def __init__(self, offset:int):
        self.__data_block_offset = offset


class Rotation:
    __x = None
    __y = None
    __z = None
    def __init__(self, x:float, y:float, z:float):
        self.__x = x
        self.__y = y
        self.__z = z


class Scale:
    __x = None
    __y = None
    __z = None
    def __init__(self, x:float, y:float, z:float):
        self.__x = x
        self.__y = y
        self.__z = z


class Translation:
    __x = None
    __y = None
    __z = None
    def __init__(self, x:float, y:float, z:float):
        self.__x = x
        self.__y = y
        self.__z = z


class MObj:
    SERIALIZED_LEN = 0x18
    __unknown = None
    __flags = None
    __tobj_offset = None
    __material_offset = None
    __unknown_2 = None
    def __init__(self, datas:bytes):
        if len(datas) != self.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in MObj constructor: {len(datas)}")
        self.__unknown         = int.from_bytes(datas[:4], "big")
        self.__flags           = int.from_bytes(datas[4:8], "big")
        self.__tobj_offset     = int.from_bytes(datas[8:12], "big")
        self.__material_offset = int.from_bytes(datas[12:16], "big")
        self.__unknown_2       = int.from_bytes(datas[16:24], "big")
    def __str__(self, depth:int):
        return f"{'  '*depth + '|-'}MObj:{self.__unknown:08x}:{self.__flags:08x}:{self.__tobj_offset:08x}:{self.__material_offset:08x}:{self.__unknown_2:016x}\n"


class PObj:
    SERIALIZED_LEN = 0x18
    __unknown = None
    __next_offset = None
    __vertex_attr_list_offset = None
    __flags = None
    __display_list_length = None # * 0x20 for getting length
    __display_list_offset = None
    __weight_list_offset = None
    # datas & objects
    __next_pobj = None
    __display_list = None
    def __init__(self, datas:bytes):
        if len(datas) != self.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in PObj constructor: {len(datas)}")
        self.__unknown                 = int.from_bytes(datas[:4], "big")
        self.__next_offset             = int.from_bytes(datas[4:8], "big")
        self.__vertex_attr_list_offset = int.from_bytes(datas[8:12], "big")
        self.__flags                   = int.from_bytes(datas[12:14], "big")
        self.__display_list_length     = int.from_bytes(datas[14:16], "big")
        self.__display_list_offset     = int.from_bytes(datas[16:20], "big")
        self.__weight_list_offset      = int.from_bytes(datas[20:24], "big")
    def __str__(self, depth:int):
        buffer_str = f"{'  '*depth + '|-'}PObj:{self.__unknown:08x}:{self.__next_offset:08x}:{self.__vertex_attr_list_offset:08x}:{self.__flags:04x}:{self.__display_list_length:04x}:{self.__display_list_offset:08x}:{self.__weight_list_offset:08x}\n"
        if self.has_next():
            buffer_str += self.__next_pobj.__str__(depth)
        return buffer_str
    def has_next(self): return self.__next_offset != 0
    def next_offset(self): return self.__next_offset
    def display_list_length(self): return self.__display_list_length
    def display_list_offset(self): return self.__display_list_offset
    def set_next_pobj(self, pobj): self.__next_pobj = pobj
    def set_display_list(self, display_list:list): self.__display_list = display_list


class DObj:
    SERIALIZED_LEN = 0x10
    __unknown = None
    __next_offset = None
    __mobj_offset = None
    __pobj_offset = None
    # Objects
    __next_dobj = None
    __mobj = None
    __pobj = None
    def __init__(self, datas:bytes):
        if len(datas) != self.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in DObj constructor: {len(datas)}")
        self.__unknown     = int.from_bytes(datas[:4], "big")
        self.__next_offset = int.from_bytes(datas[4:8], "big")
        self.__mobj_offset = int.from_bytes(datas[8:12], "big")
        self.__pobj_offset = int.from_bytes(datas[12:16], "big")
    def __str__(self, depth:int):
        buffer_str = f"{'  '*depth + '|-'}DObj:{self.__unknown:08x}:{self.__next_offset:08x}:{self.__mobj_offset:08x}:{self.__pobj_offset:08x}\n"
        if self.has_mobj():
            buffer_str += self.__mobj.__str__(depth + 1)
        if self.has_pobj():
            buffer_str += self.__pobj.__str__(depth + 1)
        if self.has_next_dobj():
            buffer_str += self.__next_dobj.__str__(depth)
        return buffer_str
    def has_next_dobj(self): return self.__next_offset != 0
    def has_mobj(self):      return self.__mobj_offset != 0
    def has_pobj(self):      return self.__pobj_offset != 0
    def next_offset(self): return self.__next_offset
    def mobj_offset(self): return self.__mobj_offset
    def pobj_offset(self): return self.__pobj_offset
    def set_next_dobj(self, dobj): self.__next_dobj = dobj
    def set_mobj(self, mobj:MObj):      self.__mobj = mobj
    def set_pobj(self, pobj:PObj):      self.__pobj = pobj


class LObj:
    SERIALIZED_LEN = 0x1c
    __class_name = None # ??
    __next_offset = None
    __flags = None # LObjFlagsEnum
    __attenuation_flags = None # LObjAttenuationFlagsEnum
    __color_r = None
    __color_g = None
    __color_b = None
    __color_alpha = None
    __lobj_point_offset = None
    __infinite_data = None
    __point_spot_data = None
    def __init__(self, datas:bytes):
        if len(datas) != LObj.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in LObj constructor: {len(datas)}")
        self.__class_name =        int.from_bytes(datas[:4], "big")
        self.__next_offset =       int.from_bytes(datas[4:8], "big")
        self.__flags =             int.from_bytes(datas[8:10], "big")
        self.__attenuation_flags = int.from_bytes(datas[10:12], "big")
        self.__color_r =           int.from_bytes(datas[12:13], "big")
        self.__color_g =           int.from_bytes(datas[13:14], "big")
        self.__color_b =           int.from_bytes(datas[14:15], "big")
        self.__color_alpha =       int.from_bytes(datas[15:16], "big")
        self.__lobj_point_offset = int.from_bytes(datas[16:20], "big")
        self.__infinite_data =     int.from_bytes(datas[20:24], "big")
        self.__point_spot_data =   int.from_bytes(datas[24:28], "big")


# new
class WObj:
    SERIALIZED_LEN = 0x14
    __unknown0 = None
    __v1 = None
    __v2 = None
    __v3 = None
    __unknown1 = None
    def __init__(self, datas:bytes):
        if len(datas) != WObj.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in WObj constructor: {len(datas)}")
        self.__unknown0 = int.from_bytes(datas[:4], "big")
        self.__v1 = unpack(">f", datas[4:8])
        self.__v2 = unpack(">f", datas[8:12])
        self.__v3 = unpack(">f", datas[12:16])
        self.__unknown1 = int.from_bytes(datas[16:20], "big")


# new
class CObj:
    SERIALIZED_LEN = 0x38
    __flags = None
    __projection_type = None
    __viewport_left = None
    __viewport_right = None
    __viewport_top = None
    __viewport_bottom = None
    __proj_width = None
    __proj_height = None
    __eye_offset = None # WObj
    __target_offset = None # WObj
    __roll = None
    __unknown = None
    __near_clip = None # float
    __far_clip = None # float
    __field_of_view = None # float
    __aspect = None # float
    def __init__(self, datas:bytes):
        if len(datas) != CObj.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in CObj constructor: {len(datas)}")
        self.__flags           = int.from_bytes(datas[:4], "big")
        self.__projection_type = int.from_bytes(datas[4:8], "big")
        self.__viewport_left   = int.from_bytes(datas[8:10], "big")
        self.__viewport_right  = int.from_bytes(datas[10:12], "big")
        self.__viewport_top    = int.from_bytes(datas[12:14], "big")
        self.__viewport_bottom = int.from_bytes(datas[14:16], "big")
        self.__proj_width      = int.from_bytes(datas[16:20], "big")
        self.__proj_height     = int.from_bytes(datas[20:24], "big")
        self.__eye_offset      = int.from_bytes(datas[24:28], "big")
        self.__target_offset   = int.from_bytes(datas[28:32], "big")
        self.__roll            = int.from_bytes(datas[32:36], "big")
        self.__unknown         = int.from_bytes(datas[36:40], "big")
        self.__near_clip       = unpack(">f", datas[40:44])
        self.__far_clip        = unpack(">f", datas[44:48])
        self.__field_of_view   = unpack(">f", datas[48:52])
        self.__aspect          = unpack(">f", datas[52:56])


class JObj:#(HSDNode):
    SERIALIZED_LEN = 0x40
    __unknown = None
    __flags = None
    __child_offset = None
    __next_offset = None
    __dobj_offset = None
    __rotation = None
    __scale = None
    __translation = None
    # Objects
    __child_jobj = None
    __next_jobj = None
    __dobj = None
    def __init__(self, datas:bytes):
        if len(datas) != JObj.SERIALIZED_LEN:
            raise Exception(f"Invalid data length in JObj constructor: {len(datas)}")
        self.__unknown      = int.from_bytes(datas[:4], "big")
        self.__flags        = int.from_bytes(datas[4:8], "big")
        self.__child_offset = int.from_bytes(datas[8:12], "big")
        self.__next_offset  = int.from_bytes(datas[12:16], "big")
        self.__dobj_offset  = int.from_bytes(datas[16:20], "big")
        self.__rotation     = Rotation(
            unpack(">f", datas[20:24]),
            unpack(">f", datas[24:28]),
            unpack(">f", datas[28:32]))
        self.__scale        = Scale(
            unpack(">f", datas[32:36]),
            unpack(">f", datas[40:44]),
            unpack(">f", datas[44:48]))
        self.__translation  = Translation(
            unpack(">f", datas[48:52]),
            unpack(">f", datas[52:56]),
            unpack(">f", datas[56:60]))
    def __str__(self, depth:int):
        buffer_str = f"{'  '*depth + '|-'}JObj:{self.__unknown:08x}:{self.__flags:08x}:{self.__child_offset:08x}:{self.__next_offset:08x}:{self.__dobj_offset:08x}\n"
        if self.has_child():
            buffer_str += self.__child_jobj.__str__(depth + 1)
        if self.has_next():
            buffer_str += self.__next_jobj.__str__(depth)
        if self.has_dobj():
            buffer_str += self.__dobj.__str__(depth + 1)
        return buffer_str
    def has_child(self): return self.__child_offset != 0
    def has_next(self):  return self.__next_offset != 0
    def has_dobj(self):  return self.__dobj_offset != 0
    def child_offset(self): return self.__child_offset
    def next_offset(self):  return self.__next_offset
    def dobj_offset(self):  return self.__dobj_offset
    def set_child_jobj(self, jobj): self.__child_jobj = jobj
    def set_next_jobj(self, jobj):  self.__next_jobj = jobj
    def set_dobj(self, dobj):       self.__dobj = dobj


class JObjDesc:
    SERIALIZED_LEN = 0x10
    __jobj_offset = None
    __joint_animations_offset = None
    __material_animations_offset = None
    __shape_animations_offset = None
    # Objects
    __jobj = None
    def __init__(self, datas:bytes):
        self.__jobj_offset                = int.from_bytes(datas[:4], "big")
        self.__joint_animations_offset    = int.from_bytes(datas[4:8], "big")
        self.__material_animations_offset = int.from_bytes(datas[8:12], "big")
        self.__shape_animations_offset    = int.from_bytes(datas[12:16], "big")
    def __str__(self, depth:int):
        return f"{'  '*depth + '|-'}JObjDesc:{self.__jobj_offset:08x}:{self.__joint_animations_offset:08x}:{self.__material_animations_offset:08x}:{self.__shape_animations_offset:08x}\n{self.__jobj.__str__(depth + 1)}"
    def jobj_offset(self): return self.__jobj_offset
    def set_jobj(self, jobj:JObj): self.__jobj = jobj


# RootNode contains SObj offset when parsing scene_data
class SObj:
    SERIALIZED_LEN = 0x10
    __jobj_descs_list_offset = None
    __cameras_list_offset = None
    __lights_list_offset = None
    __fog = None
    # Objects
    __jobj_descs_list = []
    __cameras_list = []
    __lights_list = []
    def __init__(self, datas:bytes):
        if len(datas) != SObj.SERIALIZED_LEN:
            raise Exception("Invalid SObj length.")
        self.__jobj_descs_list_offset = int.from_bytes(datas[:4], "big")
        self.__cameras_list_offset = int.from_bytes(datas[4:8], "big")
        self.__lights_list_offset = int.from_bytes(datas[8:12], "big")
        self.__fog = int.from_bytes(datas[12:16], "big")

        """if self.__fog != 0:
            print(self.__fog)
            raise Exception("Fog prensent in SObj.")
        """
    def __str__(self, depth:int):
        buffer_str = f"{'  '*depth + '|-'}SObj:{self.__jobj_descs_list_offset:08x}:{self.__cameras_list_offset:08x}:{self.__lights_list_offset:08x}:{self.__fog:08x}\n"
        for jobj_desc in self.__jobj_descs_list:
            buffer_str += jobj_desc.__str__(depth + 1)
        for camera in self.__cameras_list:
            buffer_str += camera.__str__(depth + 1)
        for ligth in self.__lights_list:
            buffer_str += ligth.__str__(depth + 1)
        return buffer_str
    def jobj_descs_list_offset(self): return self.__jobj_descs_list_offset
    def cameras_list_offset(self):    return self.__cameras_list_offset
    def lights_list_offset(self):     return self.__lights_list_offset
    def set_jobj_descs_list(self, jobj_descs_list:list): self.__jobj_descs_list = jobj_descs_list
    def set_cameras_list(self,    cameras_list:list):    self.__cameras_list = cameras_list
    def set_lights_list(self,     lights_list:list):     self.__lights_list = lights_list


class RootNode:
    SERIALIZED_LEN = 8
    __sobj_offset = None
    __name_offset = None
    # Objects
    __name = None
    __sobj = None
    def __init__(self, datas:bytes):# offset:int, string_offset:int, name:str, sobj:SObj):
        self.__sobj_offset = int.from_bytes(datas[:4], "big")
        self.__name_offset = int.from_bytes(datas[4:8], "big")
    def __str__(self):
        return f"RootNode:{self.__name}:{self.__sobj_offset:08x}:{self.__name_offset:08x}\n{self.__sobj.__str__(1)}"
    def name_offset(self): return self.__name_offset
    def sobj_offset(self): return self.__sobj_offset
    def set_name(self, name:str ): self.__name = name
    def set_sobj(self, sobj:SObj): self.__sobj = sobj


class HSDTree:
    __data_block = None
    __relocation_table = None # not used yet
    __root0_node = None
    __string_table = None
    def __init__(self, data_block:bytes, relocation_table:list, root0_node_data:bytes, string_table:bytes):
        self.__data_block = data_block
        self.__relocation_table = relocation_table
        self.__string_table = string_table

        self.__root0_node = RootNode(root0_node_data)
        self.__root0_node.set_name(self.__string_table[self.__root0_node.name_offset():].split(b"\x00")[0].decode("utf-8"))
        self.__root0_node.set_sobj(self.__add_sobj(self.__root0_node.sobj_offset()))
    def __str__(self):
        return str(self.__root0_node)[:-1]
    def __add_sobj(self, offset:int):
        sobj = SObj(self.__data_block[offset:offset+SObj.SERIALIZED_LEN])

        jobj_descs_list = []
        list_offset = sobj.jobj_descs_list_offset()
        jobj_desc_offset = int.from_bytes(self.__data_block[list_offset:list_offset+4], "big")

        while jobj_desc_offset != 0:
            jobj_descs_list.append( self.__add_jobj_desc(jobj_desc_offset) )
            list_offset += 4
            jobj_desc_offset = int.from_bytes(self.__data_block[list_offset:list_offset+4], "big")

        sobj.set_jobj_descs_list(jobj_descs_list)
        return sobj
    def __add_jobj_desc(self, offset:int):
        jobj_desc = JObjDesc(self.__data_block[offset: offset+JObjDesc.SERIALIZED_LEN])
        jobj_desc.set_jobj(self.__add_jobj(jobj_desc.jobj_offset()))
        return jobj_desc
    def __add_jobj(self, offset:int):
        new_jobj = JObj(self.__data_block[offset:offset+JObj.SERIALIZED_LEN])
        if new_jobj.has_child():
            new_jobj.set_child_jobj( self.__add_jobj(new_jobj.child_offset()) )
        if new_jobj.has_next():
            new_jobj.set_next_jobj( self.__add_jobj(new_jobj.next_offset()) )
        if new_jobj.has_dobj():
            new_jobj.set_dobj( self.__add_dobj(new_jobj.dobj_offset()) )
        return new_jobj
    def __add_dobj(self, offset:int):
        new_dobj = DObj(self.__data_block[offset: offset+DObj.SERIALIZED_LEN])
        if new_dobj.has_next_dobj():
            new_dobj.set_next_dobj( self.__add_dobj(new_dobj.next_offset()) )
        if new_dobj.has_mobj():
            new_dobj.set_mobj( self.__add_mobj(new_dobj.mobj_offset()) )
        if new_dobj.has_pobj():
            new_dobj.set_pobj( self.__add_pobj(new_dobj.pobj_offset()) )
        return new_dobj
    def __add_mobj(self, offset:int):
        return MObj(self.__data_block[offset: offset+MObj.SERIALIZED_LEN])
    def __add_pobj(self, offset:int):
        new_pobj = PObj(self.__data_block[offset: offset+PObj.SERIALIZED_LEN])
        if new_pobj.has_next():
            new_pobj.set_next_pobj( self.__add_pobj(new_pobj.next_offset()) )
        new_pobj.set_display_list( bytearray(self.__data_block[new_pobj.display_list_offset(): new_pobj.display_list_offset() + new_pobj.display_list_length()*0x20]) )
        return new_pobj


class HSDModel:
    # Header (0x20 octets or 0x120)
    __content_length = None # length without firsts 0x100 bytes
    __data_block_length = None
    __relocations_count = None
    __root0_nodes_count = None
    __root1_nodes_count = None
    # data_block
    __data_block = None
    # Relocation table
    __relocation_table = None
    # root_nodes
    __root0_nodes_data = None
    __root1_nodes_data = None
    # string table
    __string_table = None

    def __init__(self, mdl_path:Path):
        mdl_data = mdl_path.read_bytes()
        if not mdl_data:
            raise HSDModelEmptyFileError("Empty file.")

        # Header format check
        header_len = 0
        if int.from_bytes(mdl_data[:4], "big") == 0x100:
            header_len = 0x120
            if int.from_bytes(mdl_data[4:8],   "big") != 0x20 or\
               int.from_bytes(mdl_data[8:0xc], "big") != 0xc0 or\
               mdl_data[0xc:0x20]   != b"\x00"*0x14 or\
               mdl_data[0xa0:0xc0]  != b"\x00"*0x20 or\
               mdl_data[0xe0:0x100] != b"\x00"*0x20:
                raise HSDModelInvalidModelHeaderError(f"Invalid header Error {mdl_path}")
        elif int.from_bytes(mdl_data[:4], "big") == mdl_path.stat().st_size:
            header_len = 0x20
        else:
            raise HSDModelInvalidModelHeaderError(f"Invalid header Error {mdl_path}")

        hsd_header_offset = header_len - 0x20
        
        if mdl_data[hsd_header_offset+0x14:hsd_header_offset+0x20] != b"\x00"*12:
            raise HSDModelInvalidModelHeaderError(f"Invalid header Error {mdl_path}")

        # Header parsing
        self.__content_length     = int.from_bytes(mdl_data[hsd_header_offset     :hsd_header_offset+0x4], "big")
        self.__data_block_length  = int.from_bytes(mdl_data[hsd_header_offset+ 0x4:hsd_header_offset+0x8], "big")
        self.__relocations_count  = int.from_bytes(mdl_data[hsd_header_offset+ 0x8:hsd_header_offset+0xc], "big")
        self.__root0_nodes_count  = int.from_bytes(mdl_data[hsd_header_offset+ 0xc:hsd_header_offset+0x10], "big")
        self.__root1_nodes_count  = int.from_bytes(mdl_data[hsd_header_offset+0x10:hsd_header_offset+0x14], "big")

        relocation_table_offset = header_len + self.__data_block_length
        root0_nodes_offset = relocation_table_offset + 4*self.__relocations_count
        root1_nodes_offset  = root0_nodes_offset + 8*self.__root0_nodes_count
        string_table_offset = root1_nodes_offset + 8*self.__root1_nodes_count
        file_length = hsd_header_offset + self.__content_length

        if string_table_offset > file_length:
            raise Exception(f"Invalid string_table_offset: {mdl_path}.")
        if file_length != mdl_path.stat().st_size:
            raise Exception(f"Invalid file_length: {mdl_path}.")

        # Root Nodes raw parsing
        if self.__root0_nodes_count != 1 and self.__root1_nodes_count != 0:
            raise Exception("Invalid root nodes count.")
        self.__root0_nodes_data = mdl_data[root0_nodes_offset:root0_nodes_offset+8*self.__root0_nodes_count]
        
        self.__data_block = mdl_data[header_len:relocation_table_offset]
        self.__relocation_table = [int.from_bytes(mdl_data[i:i+4], "big") for i in range(relocation_table_offset, root0_nodes_offset, 4)]
        self.__relocation_table.sort()
        self.__string_table = mdl_data[string_table_offset:]
        if self.__string_table != b"scene_data\x00":
            raise Exception(f"Model not handled {self.__string_table} - expecting scene_data")

        """ logging.debug
        """
        print(f"header       : 0x00000000->0x{header_len:08x}")
        print(f"datas        : 0x{header_len:08x}->0x{relocation_table_offset:08x}")
        print(f"relocs       : 0x{relocation_table_offset:08x}->0x{root0_nodes_offset:08x}")
        print(f"root0_nodes  : 0x{root0_nodes_offset:08x}->0x{root1_nodes_offset:08x}")
        print(f"root1_nodes  : 0x{root1_nodes_offset:08x}->0x{string_table_offset:08x}")
        print(f"string_table : 0x{string_table_offset:08x}->0x{file_length:08x}")
        hsd_tree = HSDTree(self.__data_block, self.__relocation_table, self.__root0_nodes_data, self.__string_table)
        print(hsd_tree)
    def stats(self):
        print("#"*90+"\n# Header infos\n"+"#"*90)
        print(f"content_length   : {self.__content_length}")
        print(f"data_block_length: {self.__data_block_length}")
        print(f"relocations_count: {self.__relocations_count}")
        print(f"self.__root0_nodes_count : {self.__root0_nodes_count}")
        print(f"self.__root1_nodes_count : {self.__root1_nodes_count}")
        print("#"*90+"\n# Relocation Table infos\n"+"#"*90)
        reloc_str_buffer = ""
        for i in range(len(self.__relocation_table)):
            reloc_str_buffer += f"{self.__relocation_table[i]:08x} | "
            if (i+1) % 8 == 0:
                reloc_str_buffer = reloc_str_buffer[:-3] + "\n"
        print(reloc_str_buffer)


file_path = Path("mdl_arc")
hsd_mdl = HSDModel( file_path )

"""

with Path("invalid_header.txt").open("w") as ih_file:
    for file_path in list(Path("afs_data/root").glob("*_mdl*"))+\
            list(Path("pzzu").glob("**/*_mdl*"))+\
            list(Path("arzd").glob("*_mdl*"))+\
            list(Path("afs_data/root").glob("tdc*"))+\
            [Path("afs_data/root/collision.arc")]:
        if file_path.suffix == ".arz": continue
        try:
            hsd_mdl = HSDModel( file_path )
        except HSDModelInvalidModelHeaderError:
            ih_file.write(f"{file_path}\n")
        except HSDModelEmptyFileError: pass
"""
#print(len(list(Path("afs_data/root").glob("*_mdl*"))))
#hsd_mdl.stats()
