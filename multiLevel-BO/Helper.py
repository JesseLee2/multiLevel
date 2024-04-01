

import xml.etree.cElementTree as ET
import logging
import os

def getSegmentsSet():
    segsSet = {  
        1 : { 'Tdel' : 9.394e-11, 'mux_trans_size' : 1.9613025792, 'buf_size' : 19.6353043302, 'Rmetal' : 259.5614, 'Cmetal' : 3.5491e-15 },
        2 : { 'Tdel' : 9.394e-11, 'mux_trans_size' : 1.9613025792, 'buf_size' : 19.6353043302, 'Rmetal' : 259.5614, 'Cmetal' : 3.5491e-15 },                                                   
        3 : { 'Tdel' : 1.144e-10, 'mux_trans_size' : 1.741, 'buf_size' : 22.2307453173, 'Rmetal' : 259.4815, 'Cmetal' : 3.548e-15 },                                                           
        4 : { 'Tdel' : 1.424e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 25.5612499137, 'Rmetal' : 259.0515, 'Cmetal' : 3.5421e-15 },                                                  
        5 : { 'Tdel' : 1.743e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 26.216569918, 'Rmetal' : 259.8, 'Cmetal' : 3.5523e-15 },                                                      
        6 : { 'Tdel' : 2.121e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 26.4225783752, 'Rmetal' : 259.7362, 'Cmetal' : 3.5515e-15 },                                                  
        7 : { 'Tdel' : 2.538e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 27.0706280249, 'Rmetal' : 259.9992, 'Cmetal' : 3.5551e-15 },                                                  
        8 : { 'Tdel' : 3.017e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 28.6171271982, 'Rmetal' : 259.2413, 'Cmetal' : 3.5447e-15 },                                                  
        9 : { 'Tdel' : 3.564e-10, 'mux_trans_size' : 1.50823186576, 'buf_size' : 27.5631656927, 'Rmetal' : 259.9267, 'Cmetal' : 3.5541e-15 },                                                  
        10 : { 'Tdel' : 4.32e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 27.4439345149, 'Rmetal' : 259.8155, 'Cmetal' : 3.5526e-15 },                                                  
        11 : { 'Tdel' : 4.929e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 32.6284510555, 'Rmetal' : 259.7325, 'Cmetal' : 3.5514e-15 },                                                 
        12 : { 'Tdel' : 5.772e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 28.3655846906, 'Rmetal' : 259.3041, 'Cmetal' : 3.5456e-15 },                                                 
        13 : { 'Tdel' : 6.502e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 28.0303217563, 'Rmetal' : 259.5707, 'Cmetal' : 3.5492e-15 },                                                 
        14 : { 'Tdel' : 7.269e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 30.4416927491, 'Rmetal' : 259.6215, 'Cmetal' : 3.5499e-15 },                                                 
        15 : { 'Tdel' : 8.046e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 31.1285424055, 'Rmetal' : 259.4418, 'Cmetal' : 3.5474e-15 },                                                 
        16 : { 'Tdel' : 8.946e-10, 'mux_trans_size' : 1.25595750289, 'buf_size' : 32.5794230402, 'Rmetal' : 260.4216, 'Cmetal' : 3.5608e-15 },
    }

    return segsSet


def mux_trans_sizes():
    size_map = {}
    size_map["gsb_mux"] = 2.96345056513
    size_map["imux_mux"] = 1.25595750289
    size_map["1"] = 2.57691500578
    size_map["2"] = 2.772
    size_map["3"] = 1.9613025792
    size_map["4"] = 1.25595750289
    size_map["5"] = 1.50823186576
    size_map["6"] = 1.50823186576
    size_map["7"] = 3.15180029303
    size_map["8"] = 1.741
    size_map["9"] = 2.96345056513
    size_map["10"] = 2.772
    size_map["11"] = 2.772
    size_map["12"] = 2.772
    return size_map

def getOriginSeg(root):
    return_list = []
    seglist = root.getroot().find("segmentlist")
    for seg in seglist.findall("segment"):
        return_list.append(seg)
    return return_list

class bendSegmentation():
    switch_type = ["U", "D"]

    def __init__(self, _Rmetal=None, _Cmetal=None, _freq=None, _len=None, _bend_list=None, _driver=None, _net_idx=None, _name=None, _driver_para=None, _num_one_stage_driven = None,  _num_two_stage_driven = None, _num_three_stage_driven = None):
        self.Rmetal = _Rmetal
        self.Cmetal = _Cmetal
        self.freq = _freq
        self.length = _len
        self.bend_list = _bend_list
        self.driver = _driver
        self.net_idx = _net_idx
        self.name = _name
        self.driver_para = _driver_para
        self.is_shortSeg = False if _len and _len > 6 else True
        self.num_one_stage_driven = _num_one_stage_driven
        self.num_two_stage_driven = _num_two_stage_driven
        self.num_three_stage_driven = _num_three_stage_driven
        self.num = 0

    
    def __eq__(self, seg):
        if self.Rmetal == seg.Rmetal and \
           self.Cmetal == seg.Cmetal and \
           self.freq == seg.freq and \
           self.length == seg.length and \
           "".join(self.bend_list) == "".join(seg.bend_list) and \
           self.driver == seg.driver :
           return True
        
        return False

    def show(self, logger=None):
        if logger == None:
            print("\t\tSegmentation_"+ str(self.net_idx) +": " + str(self.freq) + "-" + str(self.length) + "(" + " ".join(self.bend_list) + ")-" + \
                    "(" + self.name  + ")-" + self.driver + "_RC(" + self.Rmetal + "," + self.Cmetal + ")")
            print("\t\t\tDriver_parameter: ("+ self.driver_para[0] + "," + self.driver_para[1] + "," + self.driver_para[2] + ")")
            print("\t\t\tnum that drive through three stage: "+ str(self.num_three_stage_driven) + ", two stage: " + str(self.num_two_stage_driven) + ", one stage: " + str(self.num_one_stage_driven))
        else:
            logger.info("\t\tSegmentation_"+ str(self.net_idx) +": " + str(self.freq) + "-" + str(self.length) + "(" + " ".join(self.bend_list) + ")-" + \
                            "(" + self.name  + ")-" + self.driver + "_RC(" + self.Rmetal + "," + self.Cmetal + ")")
            logger.info("\t\t\tDriver_parameter: ("+ self.driver_para[0] + "," + self.driver_para[1] + "," + self.driver_para[2] + ")")
            logger.info("\t\t\tnum that drive through three stage: "+ self.num_three_stage_driven + ", two stage: " + self.num_two_stage_driven + ", one stage: " + self.num_one_stage_driven)

class From_inf():
    def __init__(self, fromElem = None):
        if fromElem != None:
            self.type = fromElem.get("type")
            self.name = fromElem.get("name")
            self.num_foreach = int(fromElem.get("num_foreach", 1))
            if fromElem.get("total_froms") == None:
                print(self.type)
                print(self.name)
                print(str(self.num_foreach))
            self.total_froms = int(fromElem.get("total_froms"))
            self.pin_types = fromElem.get("pin_types", "")
            self.reuse = int(fromElem.get("reuse", 1))
            self.switchpoint = int(fromElem.get("switchpoint", 0))

        else:
            self.type = None
            self.name = None
            self.num_foreach = 0
            self.total_froms = 0
            self.pin_types = ""
            self.reuse = 1
            self.switchpoint = 0

    def __eq__(self, _from):
        if self.type == _from.type and \
           self.name == _from.name and \
           self.num_foreach == _from.num_foreach and \
           self.total_froms == _from.total_froms and \
           self.pin_types == _from.pin_types and \
           self.reuse == _from.reuse and \
           self.switchpoint == _from.switchpoint :
           return True
        
        return False

    def show(self, logger=None):
        if logger == None:
            print("\t\tfrom_type: " + self.type + "; " + "from_name: " + self.name + "; " + "num_foreach: " + str(self.num_foreach) + "; " + "total_froms: " + str(self.total_froms) + "; " + "reuse: " + str(self.reuse) + "; " + "pin_types:" + self.pin_types + "; " + "switchpoint:" + str(self.switchpoint))
        else:
            logger.info("\t\tfrom_type: " + self.type + "; " + "from_name: " + self.name + "; " + "num_foreach: " + str(self.num_foreach) + "; " + "total_froms: " + str(self.total_froms) + "; " + "reuse: " + str(self.reuse) + "; " + "pin_types:" + self.pin_types + "; " + "switchpoint:" + str(self.switchpoint))

def check_circle(bend_list):

    if "".join(bend_list) == "-" * len(bend_list):
        return False

    visited_points = [(0, 0), (1,0)]
    point = [1,0]
    dir_now = "r"

    for s in bend_list:
        if s == '-':
            if dir_now == "r":
                point[0] += 1
            elif dir_now == "l":
                point[0] -= 1
            elif dir_now == "u":
                point[1] += 1
            elif dir_now == "d":
                point[1] -= 1
        elif s == "U":
            if dir_now == "r":
                point[1] += 1
                dir_now = "u"
            elif dir_now == "u":
                point[0] -= 1
                dir_now = "l"
            elif dir_now == "l":
                point[1] -= 1
                dir_now = "d"
            elif dir_now == "d":
                point[0] += 1
                dir_now = "r"
        elif s == "D":
            if dir_now == "r":
                point[1] -= 1
                dir_now = "d"
            elif dir_now == "d":
                point[0] -= 1
                dir_now = "l"
            elif dir_now == "l":
                point[1] += 1
                dir_now = "u"
            elif dir_now == "u":
                point[0] += 1
                dir_now = "r"
            
        if (point[0], point[1]) in visited_points:
            return True
        else:
            visited_points.append((point[0], point[1]))

    for i in range(len(bend_list)-1):
        cur_b = bend_list[i]
        next_b = bend_list[i+1]
        if cur_b == '-':
            continue
        if cur_b == next_b:
            return True
        
    return False

def modifyArch_V3_bent(segs, gsbArchFroms, archTree, omux_changed = False):
    gsb = gsbArchFroms[0]
    to_mux_nums = gsbArchFroms[1]
    imux = gsbArchFroms[2]
    omux = gsbArchFroms[3]

    # delete the <segmentlist>
    archTree["root"].getroot().remove(archTree["root"].find("segmentlist"))

    # add  <segmentlist> and modify the freq of the origin segments
    rate_bend_segment = 0.0
    seglist = ET.SubElement(archTree["root"].getroot(), "segmentlist")
    for seg in segs:
        rate_bend_segment += float(seg.freq)
        segElem = ET.SubElement(seglist, "segment")
        segElem.set("freq", str(seg.freq))
        segElem.set("name", seg.name)
        segElem.set("length", str(seg.length))
        segElem.set("type", "unidir")
        # segElem.set("Rmetal", seg.Rmetal)
        # segElem.set("Cmetal", seg.Cmetal)
        segElem.set("Rmetal", "0.000000")
        segElem.set("Cmetal", "0.000000e+00")

        mux = ET.SubElement(segElem, "mux")
        mux.set("name", seg.driver)

        sb = ET.SubElement(segElem, "sb")
        sb.set("type", "pattern")
        sb.text = " ".join(["0"] * (seg.length - 1))
        sb.text = "1 " + sb.text + " 1"
        sb.text = ' '.join(sb.text.split())

        cb = ET.SubElement(segElem, "cb")
        cb.set("type", "pattern")
        cb.text = " ".join(["0"] * (seg.length - 2)) if seg.length >=2 else ""
        cb.text = "1 " + cb.text + " 1" if seg.length >=2 else "1"
        cb.text = ' '.join(cb.text.split())

        # print(seg.name)
        # print(seg.bend_list)
        if seg.length > 1 and seg.bend_list != None and seg.bend_list != ["-"] * (seg.length - 1):
            bend = ET.SubElement(segElem, "bend")
            bend.set("type", "pattern")
            bend.text = " ".join(seg.bend_list)

    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    if omux_changed:
        omuxElem = gsb_arch.find("omux")
        omuxElem.set("mux_nums", omux["mux_nums"])
        omuxElem.find("from").set("num_foreach", omux["num_foreach"])

    #remove multistage mux info
    if not gsb_arch.find("imux").find("multistage_muxs") is None:
        gsb_arch.find("imux").remove(gsb_arch.find("imux").find("multistage_muxs"))
    # if not gsb_arch.find("gsb").find("multistage_muxs") is None:
    #     gsb_arch.find("gsb").remove(gsb_arch.find("gsb").find("multistage_muxs"))
    
    lut_group = gsb_arch.find("imux").find("group")
    rmElems = lut_group.findall("from")
    for rmElem in rmElems:
        lut_group.remove(rmElem)
    imux_froms = list(imux.values())[0]
    for imux_from in imux_froms:
        fromElem = ET.SubElement(lut_group, "from")
        '''
        print("***************")
        print(imux_from.type)
        print(imux_from.name)
        print(imux_from.total_froms)
        print(imux_from.num_foreach)
        print(imux_from.reuse)
        print(imux_from.pin_types)'''
        
        fromElem.set("type", imux_from.type)
        fromElem.set("name", imux_from.name)
        fromElem.set("total_froms", str(imux_from.total_froms))
        fromElem.set("num_foreach", str(imux_from.num_foreach))
        fromElem.set("reuse", str(imux_from.reuse))
        if imux_from.type == "pb" or imux_from.type == "imux":
            fromElem.set("pin_types", imux_from.pin_types)


    gsbElem = gsb_arch.find("gsb")
    gsbElem.set("gsb_seg_group", str(len(gsb)))
    rmElems = gsbElem.findall("seg_group")
    for rmElem in rmElems:
        gsbElem.remove(rmElem)
    print(len(gsb.items()))
    for to_seg_name, gsb_froms in gsb.items():
        print(to_seg_name)
        seg_group = ET.SubElement(gsbElem, "seg_group")
        seg_group.set("name", to_seg_name)
        seg_group.set("track_nums", str(to_mux_nums[to_seg_name]))

        for gsb_from in gsb_froms:
            fromElem = ET.SubElement(seg_group, "from")
            fromElem.set("type", gsb_from.type)
            fromElem.set("name", gsb_from.name)
            fromElem.set("total_froms", str(gsb_from.total_froms))
            fromElem.set("num_foreach", str(gsb_from.num_foreach))
            fromElem.set("reuse", str(gsb_from.reuse))
            if gsb_from.type == "pb":
                fromElem.set("pin_types", gsb_from.pin_types)

def modifyArch_addMedium(archTree):
    # add  <segmentlist> and modify the freq of the origin segments
    seglist = archTree["root"].getroot().find("segmentlist")
    segs_include_medium = []
    segs_include_medium.append(bendSegmentation(0, 0, 0.0, 1, [], "imux_medium_mux", 0, "imux_medium", [0,0,0]))
    segs_include_medium.append(bendSegmentation(0, 0, 0.0, 1, [], "omux_medium_mux", 0, "omux_medium", [0,0,0]))
    segs_include_medium.append(bendSegmentation(0, 0, 0.0, 1, [], "gsb_medium_mux", 0, "gsb_medium", [0, 0, 0]))
    for seg in segs_include_medium:
        segElem = ET.SubElement(seglist, "segment")
        segElem.set("freq", str(seg.freq))
        segElem.set("name", seg.name)
        segElem.set("length", str(seg.length))
        segElem.set("type", "unidir")
        # segElem.set("Rmetal", seg.Rmetal)
        # segElem.set("Cmetal", seg.Cmetal)
        segElem.set("Rmetal", "0.000000")
        segElem.set("Cmetal", "0.000000e+00")

        mux = ET.SubElement(segElem, "mux")
        mux.set("name", seg.driver)

        sb = ET.SubElement(segElem, "sb")
        sb.set("type", "pattern")
        sb.text = " ".join(["0"] * (seg.length - 1))
        sb.text = "1 " + sb.text + " 1"
        sb.text = ' '.join(sb.text.split())

        cb = ET.SubElement(segElem, "cb")
        cb.set("type", "pattern")
        cb.text = " ".join(["0"] * (seg.length - 2)) if seg.length >=2 else ""
        cb.text = "1 " + cb.text + " 1" if seg.length >=2 else "1"
        cb.text = ' '.join(cb.text.split())


class TwoStageMuxFrom_inf():
    def __init__(self, _type, _name, _from_details, _switchpoint = 0):
        self.type = _type
        self.name = _name
        self.from_details = _from_details
        self.switchpoint = _switchpoint

    def show(self):
        print("\t\tfrom_type=" + self.type + "\t" + "from_name=" + self.name + "\t"
              "from_details=" + self.from_details + "\t" + "switchpoint=" + str(self.switchpoint))
    
    def to_arch(self, mux_from_arch):
        a_from = ET.SubElement(mux_from_arch, "from")
        a_from.set("type", self.type)
        a_from.set("name", self.name)
        a_from.set("from_detail", self.from_details)
        a_from.set("switchpoint", str(self.switchpoint))

    def count_detail_nums(self):
        return len(self.from_details.split(" "))
    
class ArchError(Exception):
    pass


def logger_init(logger, logdir='./logfiles', logfile='./logfiles/logger_test.log'):

    # Log等级总开关
    logger.setLevel(logging.INFO)

    # 创建log目录
    if not os.path.exists(logdir):
        os.mkdir(logdir)

    # 创建一个handler，用于写入日志文件
    # 以append模式打开日志文件
    fh = logging.FileHandler(logfile, mode='a')

    # 输出到file的log等级的开关
    fh.setLevel(logging.INFO)

    # 再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()

    # 输出到console的log等级的开关
    ch.setLevel(logging.INFO)

    # 定义handler的输出格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")

    # formatter = logging.Formatter("%(asctime)s [%(thread)u] %(levelname)s: %(message)s")
    # 为文件输出设定格式
    fh.setFormatter(formatter)
    # 控制台输出设定格式
    #ch.setFormatter(formatter)

    # 设置文件输出到logger
    logger.addHandler(fh)
    # 设置控制台输出到logger
    logger.addHandler(ch)