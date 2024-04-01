
import os
import xml.etree.cElementTree as ET
import re
from xml.dom import minidom
from Helper import *
import random
from functools import partial
from hyperopt import hp, fmin, mix, tpe, rand, space_eval, STATUS_OK, STATUS_FAIL
from hyperopt.mongoexp import MongoTrials, Trials
from generateTwoStageV200 import *


def prettify2(elem):
    """
        Return a pretty-printed XML string for the Element.
    """
    rough_string = ET.tostring(elem, 'utf-8').decode("utf-8")
    rough_string = re.sub(">\s*<", "><", rough_string)
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t", encoding="utf-8")

def readArch2(archfile):
    archTree = {}
    archTree["root"] = ET.parse(archfile)
    return archTree

def writeArch2(elem, outfile):
    f = open(outfile, "wb+")
    f.write(prettify2(elem))
    f.close()


def genArch(variables):
    # Constants
    PbTotalNum = 8
    OxbarTotalNum = 8
    IMUXTotalNum0 = 16
    IMUXTotalNum1 = 48
    OpinTypes = ["o", "q", "mux_o"]
    OpinTypeProbs = [1 / 3.0, 1 / 3.0, 1 / 3.0]
    IpinTypes = ["i", "x"]
    IpinTypeProbs = [0.5, 0.5]
    # Variable definitions
    maxSegLen   = 16
    numAddition = 4 # opin = 2, imux = 2, 
    varSegNums  = list(variables[0:maxSegLen])
    varBendProb = list(variables[maxSegLen:(2 * maxSegLen)])
    varBendPos  = list(variables[(2 * maxSegLen):(3 * maxSegLen)])
    varBendType = list(variables[(3 * maxSegLen):(4 * maxSegLen)])
    varOneStagePorp = list(variables[(4 * maxSegLen):(5 * maxSegLen)])
    varTwoStagePorp = list(variables[(5 * maxSegLen):(6 * maxSegLen)])
    varThreeStagePorp = list(variables[(6 * maxSegLen):(7 * maxSegLen)])
    
    
    # ratio***StageDriven: [len: the ratio of the num that should be driven through *** stages to the total num of current seg]
    # the sum of the same index of the three lists should be one
    # pre process the num that the seg should be driven by different stages: normalized to 1

    ratioOneStageDriven = []
    ratioTwoStageDriven = []
    ratioThreeStageDriven = []
    for length in range(maxSegLen):
        sumOfVar = varOneStagePorp[length] + varTwoStagePorp[length] + varThreeStagePorp[length]
        oneStagePorp = varOneStagePorp[length] / sumOfVar
        twoStagePorp = varTwoStagePorp[length] / sumOfVar
        threeStagePorp = varThreeStagePorp[length] / sumOfVar
        # we controls the ratio of the seg that drives through three-stage mux below 0.3
        if oneStagePorp > 0.3:
            oneStagePorp = 0.3
            twoStagePorp = 0.7 * twoStagePorp / (twoStagePorp + threeStagePorp)
            threeStagePorp = 0.7 * threeStagePorp / (twoStagePorp + threeStagePorp)
        ratioOneStageDriven.append(oneStagePorp)
        ratioTwoStageDriven.append(twoStagePorp)
        ratioThreeStageDriven.append(threeStagePorp)
         

    # New Segments
    # -> Basic parameters
    tile_length = 30
    segRmetal = 7.862 * tile_length
    segCmetal = round(0.215 * tile_length / 2, 5) / pow(10, 15)
    segDrivers = getSegmentsSet()
    # -> Limits of segment quantities
    numSegmentSteps = list(map(lambda x: x * 2, [length for length in range(1, maxSegLen + 1)]))
    minSegmentSteps = [8, 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    maxSegmentSteps = [15, 12, 8, 8, 5, 5, 0, 3, 2, 2, 2, 2, 0, 0, 0, 0]
    # maxSegmentSteps = [10, 5, 5, 5, 3, 3, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1]
    # -> Segment quantity offsets
    segNumOffset = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    for idx in range(len(varSegNums)): 
        varSegNums[idx] = max(0.0, (varSegNums[idx] - segNumOffset[idx]) / (1.0 - segNumOffset[idx])) 
        
    # -> -> Validity
    valid = True
    # -> -> Generate segments
    # -> -> -> Numbers of segments
    segNums = []
    for idx in range(0, len(varSegNums)):
        portion = varSegNums[idx]
        segNums.append(round(minSegmentSteps[idx] + (maxSegmentSteps[idx] - minSegmentSteps[idx]) * portion) * numSegmentSteps[idx])
    totalSegNum = float(sum(segNums))
    type_to_num = {}
    for i in range(len(segNums)):
        if segNums[i] != 0:
            segType = 'l' + str(i + 1)
            type_to_num[segType] = segNums[i] // numSegmentSteps[i]


    segments = []
    for length in range(1, maxSegLen + 1):
        segment = bendSegmentation()
        segment.length = length
        segment.Rmetal = str(segRmetal)
        segment.Cmetal = str(segCmetal)
        segment.driver = str(length)
        segment.driver_para = (str(segDrivers[length]['Tdel']), str(
            segDrivers[length]['mux_trans_size']), str(segDrivers[length]['buf_size']))
        segment.is_shortSeg = False if length > 6 else True
        segment.freq = segNums[length - 1]
        segment.num = int(segment.freq) // int(length) // 2
        segment.net_idx = length
        segment.name = "l" + str(length)
        segment.bend_list = []
        segment.num_one_stage_driven = int(segment.num * ratioOneStageDriven[length-1])
        segment.num_two_stage_driven = int(segment.num * ratioTwoStageDriven[length-1])
        segment.num_three_stage_driven = int(segment.num * ratioThreeStageDriven[length-1])

        if segment.num_one_stage_driven + segment.num_two_stage_driven + segment.num_three_stage_driven < segment.num:
            numAssigned = segment.num_one_stage_driven + segment.num_two_stage_driven + segment.num_three_stage_driven
            for i in range(segment.num - numAssigned):
                if (i % 3 == 0):
                    segment.num_two_stage_driven += 1
                elif (i % 3 == 1):
                    segment.num_one_stage_driven += 1
                else:
                    segment.num_three_stage_driven += 1
        

        if length > 1: 
            segment.bend_list = ['-'] * (length - 1)
            if varBendProb[length - 1] > 0.5 and length > 2: 
                position = int(round((length - 2) * varBendPos[length - 1])) if length <= 6 else int(round((length/2 - 1) * varBendPos[length - 1]))
                bendType = "U" if varBendType[length - 1] > 0.5 else "D"
                segment.bend_list[position] = bendType
        segments.append(segment)

    tmplist = []
    for segment in segments: 
        if segment.freq > 0.0: 
            tmplist.append(segment)
            # print("Segment Quantity:", segment.length, ":", round(segment.freq))
    segments = tmplist
    # -> -> -> Validate the segments, such as check_circle(bend_list), 
    for segment in segments: 
        if len(segment.bend_list) > 0: 
            valid = valid and not check_circle(segment.bend_list)
    # print("Validity (after segment generation):", valid)
    # print("Generated segments: ")
    # list(map(lambda x: x.show(), segments))
    # -> -> -> Channel width
    chanWidth = int(totalSegNum)
    # print("Channel width: ", chanWidth)

    # New Driving Relations
    # -> Utilities
    def randomPick(itemList, probs, number):
        result = set()
        assert len(itemList) >= number, "Cannot randomly pick " + str(number) + " items in a list of " + str(len(itemList)) + " items. "
        while len(result) < number:  
            x = random.uniform(0, 1)
            c_prob = 0.0
            for item, prob in zip(itemList, probs):
                c_prob += prob
                if x < c_prob: 
                    break
            result.add(item)
        return list(result)
    # -> IMUX driving relations
    relationsIMUX = []
    # -> -> From segments
    for segment in segments:
        connection = From_inf()
        connection.type = "seg"
        connection.name = segment.name
        connection.total_froms = int(segNums[segment.length - 1] / segment.length / 2)
        connection.num_foreach = connection.total_froms
        connection.pin_types = ""
        # connection.reuse = 1
        connection.reuse = 1 if segment.length <= 6 else 0
        # connection.reuse = 1 if varConnReuseIMUX[(segment.length - 1)] > 0.2 else 0
        connection.switchpoint = 0
        if connection.num_foreach > 0: 
            relationsIMUX.append(connection)
    # -> -> From opins, plb
    connection = From_inf()
    connection.type = "pb"
    connection.name = "plb"
    connection.total_froms = PbTotalNum
    connection.num_foreach = 8
    # connection.num_foreach = int(round(0.125 * connection.total_froms))
    # connection.num_foreach = int(round(scaleOtherTypeRelations[0] * connection.total_froms * varConnNumsIMUX[(maxSegLen - 1) + 1]))
    connection.pin_types = " ".join(randomPick(OpinTypes, OpinTypeProbs, random.randint(0, len(OpinTypes))))
    connection.reuse = 1
    # connection.reuse = 1 if varConnReuseIMUX[(maxSegLen - 1) + 1] > 0.2 else 0
    connection.switchpoint = 0
    if connection.num_foreach > 0 and len(connection.pin_types) > 0: 
        relationsIMUX.append(connection)
    # -> -> From opins, oxbar
    connection = From_inf()
    connection.type = "omux"
    connection.name = "oxbar"
    connection.total_froms = OxbarTotalNum
    connection.num_foreach = int(round(0.125 * connection.total_froms))
    # connection.num_foreach = int(round(scaleOtherTypeRelations[1] * connection.total_froms * varConnNumsIMUX[(maxSegLen - 1) + 2]))
    connection.pin_types = ""
    connection.reuse = 1
    # connection.reuse = 1 if varConnReuseIMUX[(maxSegLen - 1) + 2] > 0.2 else 0
    connection.switchpoint = 0
    if connection.num_foreach > 0: 
        relationsIMUX.append(connection)

    
    
    relationsIMUX = {"Ia Ic Ie Ig": relationsIMUX, }

    # -> ToMUXNum
    numSegs = {}
    for segment in segments: 
        numSegs[segment.name] = int(segment.freq / segment.length / 2)

    # -> GSB driving relations
    relationsGSB = {}
    for seg1 in segments: 
        # -> -> From segments
        relation = []
        for seg2 in segments: 
            connection = From_inf()
            connection.type = "seg"
            connection.name = seg2.name
            connection.total_froms = int(segNums[seg2.length - 1] / seg2.length / 2)
            connection.num_foreach = connection.total_froms
            connection.pin_types = ""
            # connection.reuse = 1
            connection.reuse = 1 if seg1.length <= 6 and seg2.length <= 6 else 0
            # connection.reuse = 1 if seg1.length <= 6 else 0
            # connection.reuse = 1 if varConnReuseGSB[(seg1.length - 1) * (maxSegLen + numAddition) + (seg2.length - 1)] > (0.2 + seg1.length / float(maxSegLen)) else 0
            connection.switchpoint = 0
            if connection.num_foreach > 0: 
                relation.append(connection)
        # -> -> From opins, plb
        connection = From_inf()
        connection.type = "pb"
        connection.name = "plb"
        connection.total_froms = PbTotalNum
        connection.num_foreach = int(round(0.25 * connection.total_froms))
        # connection.num_foreach = int(round(scaleOtherTypeRelations[0] * connection.total_froms * varConnNumsGSB[(seg1.length - 1) * (maxSegLen + numAddition) + (maxSegLen - 1) + 1]))
        connection.pin_types = " ".join(randomPick(OpinTypes, OpinTypeProbs, random.randint(0, len(OpinTypes))))
        # connection.reuse = 1
        connection.reuse = 1 if seg1.length <= 6 else 0
        # connection.reuse = 1 if varConnReuseGSB[(seg1.length - 1) * (maxSegLen + numAddition) + (maxSegLen - 1) + 1] > (0.4 + seg1.length / float(maxSegLen)) else 0
        connection.switchpoint = 0
        if connection.num_foreach > 0 and len(connection.pin_types) > 0: 
            relation.append(connection)
        # -> -> From opins, oxbar
        connection = From_inf()
        connection.type = "cas"
        connection.name = "cas"
        connection.total_froms = OxbarTotalNum
        connection.num_foreach = int(round(0.125 * connection.total_froms))
        # connection.num_foreach = int(round(scaleOtherTypeRelations[1] * connection.total_froms * varConnNumsGSB[(seg1.length - 1) * (maxSegLen + numAddition) + (maxSegLen - 1) + 2]))
        connection.pin_types = ""
        # connection.reuse = 1
        connection.reuse = 1 if seg1.length <= 6 else 0
        # connection.reuse = 1 if varConnReuseGSB[(seg1.length - 1) * (maxSegLen + numAddition) + (maxSegLen - 1) + 2] > (0.4 + seg1.length / float(maxSegLen)) else 0
        connection.switchpoint = 0
        if connection.num_foreach > 0: 
            relation.append(connection)
        relationsGSB[seg1.name] = relation
            
    others = {'num_foreach': 12, 'mux_nums': 16}

    relations = [relationsGSB, numSegs, relationsIMUX, others]

    # print(segments)
    # print()
    # for elem in relations: 
    #     print(elem)
    # print()
    # print("Channel Width:", chanWidth)

    return segments, relations, chanWidth, type_to_num


def generateDetailSPListV2(size, dirOffset, detailOffset, spOffset, segNum, type, currentSegdirInd):

    detailSPList = []
    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}
    sp = spOffset
    detailInd = detailOffset
    dirInd = dirOffset
    if type == "IMUX":
        for i in range(size):
            detailInd = detailInd + segNum // 2 - ((segNum + 1) % 2) * ((i + 1) % 2)
            detail = ind2dir[dirInd % 4] + str(detailInd % segNum)
            detailSPList.append((detail, str(sp)))
            sp = (sp + 1) % 4
            dirInd = (dirInd + 1) % 4
                
    elif type == "GSB":
        for i in range(size):
            detail = ind2dir[dirInd % 4] + str((detailInd + i) % segNum)
            detailSPList.append((detail, str(sp)))
            sp = (sp + 1) % 4
        dirInd = (dirInd + 1) % 4
        if dirInd == 0:
            detailInd += size
            # if dirInd == currentSegdirInd // 2 * 2 + 1 - (currentSegdirInd % 2):
            #     dirInd = (dirInd + 1) % 4


    return detailSPList, dirInd, detailInd % segNum, sp

def generateDetailSPList(size, dirOffset, detailOffset, spOffset, segNum, type, currentSegdirInd):

    detailSPList = []
    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}
    sp = spOffset
    detailInd = detailOffset
    dirInd = dirOffset
    if type == "IMUX":
        for i in range(size):
            detail = ind2dir[dirInd % 4] + str(detailInd)
            detailInd = (detailInd + 1) % segNum
            detailSPList.append((detail, str(sp)))
            # if (i % 16 == 15):
            #     detailInd = (detailInd + 1) % segNum
                
    elif type == "GSB":
        # if dirInd == currentSegdirInd // 2 * 2 + 1 - (currentSegdirInd % 2):
        #     dirInd = (dirInd + 1) % 4
        # for i in range(size):
        #     detail = ind2dir[dirInd % 4] + str(detailInd)
        #     detailSPList.append((detail, str(sp)))
        #     if (i % 4 == 3):
        #         dirInd = (dirInd + 1) % 4
        #         if dirInd == currentSegdirInd // 2 * 2 + 1 - (currentSegdirInd % 2):
        #             dirInd = (dirInd + 1) % 4
        #     if (i % 12 == 11):
        #         detailInd = (detailInd + 1) % segNum
        for i in range(size):
            detail = ind2dir[dirInd % 4] + str(detailInd)
            detailInd = (detailInd + 1) % segNum
            detailSPList.append((detail, str(sp)))

    dirInd += 1
    return detailSPList, dirInd, detailInd, (sp + 1) % 4

def generateIMUXFirstStage(archTree, imux_1st_size, imux_1st_num, segNum):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    gsbElem = gsb_arch.find("gsb")
    imuxElem = gsb_arch.find("imux")
    if imuxElem.find("multistage_muxs") != None:
        imuxElem.remove(imuxElem.find("multistage_muxs"))
    imux_two_stage = ET.SubElement(imuxElem, "multistage_muxs")
    first_stage = ET.SubElement(imux_two_stage, "first_stage")
    first_stage.set("switch_name", "imux_medium_mux")
    
    dirOffset = 0
    
    fromDetailOffsetPrev = 0
    spOffset = 0

    plbPins = ['o', 'q', 'mux_o']

    # assign seg drives
    for i in range(imux_1st_num):
        mux = ET.SubElement(first_stage, "mux")
        mux.set("name", "IG_1ST_" + str(i))
        (detailSPList, dirOffset, fromDetailOffsetCur, spOffset) = generateDetailSPList(imux_1st_size, dirOffset, fromDetailOffsetPrev, spOffset, segNum, "IMUX", 0)
        for j in range(imux_1st_size):
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'seg')
            fromNode.set('name', 'l4')
            fromNode.set('from_detail', detailSPList[j][0])
            fromNode.set('switchpoint', detailSPList[j][1])
        if i % 4 == 3:
            spOffset = (spOffset + 1) % 4
            fromDetailOffsetPrev = fromDetailOffsetCur

        # assign plb feedback from plb: o q mux_o omux(16)
        if i % 4 == 0:
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'omux')
            fromNode.set('name', 'oxbar')
            fromNode.set('from_detail', str(i // 4 % 16))
            fromNode.set('switchpoint', "0")
        else:
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'pb')
            fromNode.set('name', 'plb')
            plbFromDetail = plbPins[i % 4 - 1] + ":" + str(i // 4 % 8)
            fromNode.set('from_detail', plbFromDetail)
            fromNode.set('switchpoint', "0")

            

    

def generateIMUXSecondStage(archTree, imux_2nd_size, imux_1st_num, K, N):

    # always followd by generateIMUXFirstStage

    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    imuxElem = gsb_arch.find("imux")
    imux_two_stage = imuxElem.find("multistage_muxs")
    second_stage = ET.SubElement(imux_two_stage, "second_stage")

    ind2pin = {0:"Ia", 1:"Ib", 2:"Ic", 3:"Id", 4:"Ie", 5:"If", 6:"Ig", 7:"Ih", }
    indMux = 0
    ind1STMux = 0
    for indLut in range(N):
        for indpin in range(K):

            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", "IG_2ND_" + str(indMux))
            mux.set("to_pin", ind2pin[indLut] + ":" + str(indpin))

            muxFrom = ""

            for indFrom in range(imux_2nd_size):
                muxFrom = muxFrom + " IG_1ST_" + str(ind1STMux % imux_1st_num)
                ind1STMux += 1
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('mux_name', muxFrom[1:])
            indMux += 1
                
def generateGSBFirstStage(archTree, gsb_1st_size, gsb_1st_num, segNum):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    plbPins = ['o', 'q', 'o']
    gsbElem = gsb_arch.find("gsb")
    if gsbElem.find("multistage_muxs") != None:
        gsbElem.remove(gsbElem.find("multistage_muxs"))
    gsb_seg_group = gsbElem.find("seg_group")
    gsb_seg_group.set("track_nums", str(segNum))
    gsb_two_stage = ET.SubElement(gsbElem, "multistage_muxs")
    first_stage = ET.SubElement(gsb_two_stage, "first_stage")
    first_stage.set("switch_name", "gsb_medium_mux")
    
    dirOffset = 0
    fromDetailOffset = 0
    fromDetailOffsetPrev = 0
    spOffset = 0
    for i in range(gsb_1st_num):
        mux = ET.SubElement(first_stage, "mux")
        mux.set("name", "mux-" + str(i))
        (detailSPList, dirOffset, fromDetailOffsetCur, spOffset) = generateDetailSPList(gsb_1st_size, dirOffset, fromDetailOffsetPrev, spOffset, segNum, "GSB", 0)
        if i % 4 == 3:
            spOffset = (spOffset + 1) % 4
            fromDetailOffsetPrev = fromDetailOffsetCur
        for j in range(gsb_1st_size):
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'seg')
            fromNode.set('name', 'l4')
            fromNode.set('from_detail', detailSPList[j][0])
            fromNode.set('switchpoint', detailSPList[j][1])

        # assign the additional drive which could be seg or plb
        if i % 4 == 0:
            dirFromDetail = detailSPList[0][0][0]
            indFromDetail = str((int(detailSPList[0][0][1:]) + segNum // 4) % segNum)
            segFromDetail = dirFromDetail + indFromDetail 
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'seg')
            fromNode.set('name', 'l4')
            fromNode.set('from_detail', segFromDetail)
            fromNode.set('switchpoint', "0")
        else:
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'pb')
            fromNode.set('name', 'plb')
            plbFromDetail = plbPins[i % 4 - 1] + ":" + str(i // 4 % 8)
            fromNode.set('from_detail', plbFromDetail)
            fromNode.set('switchpoint', "0")

def generateGSBSecondStage(archTree, gsb_2nd_size, gsb_1st_num, segNum):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    gsbElem = gsb_arch.find("gsb")
    gsb_two_stage = gsbElem.find("multistage_muxs")
    second_stage = ET.SubElement(gsb_two_stage, "second_stage")
    second_stage.set("switch_name", "only_mux")

    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}
    ind1STMux = 0
    ind2NDMux = 0

    for i in range(segNum):

        for indDir in range(4):
            ind2NDMux += 1
            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", ind2dir[indDir]+"-b"+str(i))
            mux.set("to_segName", "l4")
            mux.set("to_track", ind2dir[indDir]+str(i))

            muxFrom = ""

            for indFrom in range(gsb_2nd_size):
                muxFrom = muxFrom + " mux-" + str((ind1STMux + indFrom) % gsb_1st_num)
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('mux_name', muxFrom[1:])

            # assign the additional drive -- omux
            
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'omux')
            fromNode.set('name', 'oxbar')
            fromNode.set('from_detail', str(ind2NDMux % 16))
            fromNode.set('switchpoint', "0")
        
        ind1STMux += gsb_2nd_size

def assignFirstStageMuxFromSeg(StageMuxFroms, seg, indList, segNum, segTimes,stageGroupNum, stageGroupSize, muxOffset, segIdOffset, dirIdOffset, muxName):
    
    ind2dir = ["W", "N", "E", "S"]
    type_str = "seg"
    fromName = seg.name  

        
    segId = segIdOffset
    dirId = dirIdOffset

    for i in range(stageGroupNum):
        muxId = muxOffset

        # assign the drives from seg in one glb group
        for j in range(segTimes):

            
            mux_name = muxName + str(muxId + i * stageGroupSize)
            dir_str = ind2dir[dirId]

            # one group contains four muxes, assign by segs_times
            from_details = ""
            from_details =dir_str + str(indList[segId])  
            # print("assign " + str(fromName) + " " + from_details + " to " + mux_name)
            dirId = (dirId + 1) % 4
            if dirId % 4 == 0:
                segId = (segId + 1) % segNum
            muxId = (muxId + 1) % stageGroupSize
        
            # if first_mux_assign:
            #     to_track_to_first_mux[i].append(mux_name)

            stagemuxfrom = TwoStageMuxFrom_inf(
                type_str, fromName, from_details, 0)
            if mux_name in StageMuxFroms:
                StageMuxFroms[mux_name].append(stagemuxfrom)
            else:
                StageMuxFroms[mux_name] = [stagemuxfrom]  

    return (muxId, segId)

def assignGLBStageMuxFromSeg(StageMuxFroms, seg, indList, segNum, segTimes,glbGroupNum, glbGroupSize, glbStageSize, muxOffset, dirIdOffset, segIdOffset):
    ind2dir = ["W", "N", "E", "S"]
    type_str = "seg"
    fromName = seg.name  

        
    segId = segIdOffset
    dirId = dirIdOffset

    for i in range(glbGroupNum):
        muxId = muxOffset

        # assign the drives from seg in one glb group
        for j in range(segTimes):

            
            mux_name = "mux_" + str(muxId + i * glbGroupSize)
            dir_str = ind2dir[muxId % 4]

            # one group contains four muxes, assign by segs_times
            from_details = ""
            from_details =dir_str + str(indList[segId] % segNum)  
            # print("assign " + str(fromName) + " " + from_details + " to " + mux_name)
            dirId = (dirId + 1) % 4
            if (dirId % 4 == 0):
                segId = (segId + 1) % segNum
            muxId = (muxId + 1) % glbGroupSize
        
            # if first_mux_assign:
            #     to_track_to_first_mux[i].append(mux_name)

            stagemuxfrom = TwoStageMuxFrom_inf(
                type_str, fromName, from_details, 0)
            if mux_name in StageMuxFroms:
                StageMuxFroms[mux_name].append(stagemuxfrom)
            else:
                StageMuxFroms[mux_name] = [stagemuxfrom]  

    return (muxId, segId)

def assignFirstStageFromGLB(firstStageMuxFroms, glbGroupNum, glbGroupSize, firstStageNum):

    glbMuxNum = glbGroupSize * glbGroupNum
    muxId = 0
    for i in range(firstStageNum):
        muxName = "mux2nd_" + str(i)
        # assign the glb drives in one first stage mux
        for j in range(glbGroupSize):
            fromMuxName = 'mux_' + str(muxId)
            muxId = (muxId + 1) % glbMuxNum
            typeGlb = "glb"
            fromName = "glb"
            glbFrom = TwoStageMuxFrom_inf(
                typeGlb, fromName, fromMuxName, 0)
            if muxName in firstStageMuxFroms:
                firstStageMuxFroms[muxName].append(glbFrom)
            else:
                firstStageMuxFroms[muxName] = [glbFrom]  
            

def assignSecondStageFromFirst(secondStageMuxFroms, secondStageSize, firstStageNum, K, N):
    muxId = 0
    i_ports = ("Ia", "Ib", "Ic", "Id", "Ie", "If", "Ig", "Ih")
    for i_p in range(len(i_ports)):
        for i_b in range(K):
            mux_name = "b" + str(i_b) + "-" + i_ports[i_p]
            to_pin = i_ports[i_p] + ":" + str(i_b)
            second_mux = (mux_name, to_pin)
            first_mux = []
            for i_m in range(secondStageSize):
                mux_name = "mux2nd_" + str(muxId)
                muxId = (muxId + 1) % firstStageNum
                first_mux.append(mux_name)
                
            secondStageMuxFroms[second_mux] = first_mux

def assignSecondStageMuxFromSeg(StageMuxFroms, seg, indList, segNum, segTimes, K, N, pinOffset, segIdOffset):

    ind2dir = ["W", "N", "E", "S"]
    type_str = "seg"
    fromName = seg.name  

    i_ports = ("Ia", "Ib", "Ic", "Id", "Ie", "If", "Ig", "Ih")
        
    segId = segIdOffset

    muxId = 0
    dirId = 0
    

    for indLut in range(N):
        indPin = pinOffset

        # assign the drives from seg in one glb group
        for j in range(segTimes):

            muxId = indLut * K + indPin
            dir_str = ind2dir[dirId % 4]

            # one group contains K lut inputs, assign by segs_times
            from_details = ""
            from_details =dir_str + str(indList[segId])  
            dirId = (dirId + 1) % 4
            if dirId % 4 == 0:
                segId = (segId + 1) % segNum
            mux_name = "b" + str(indPin) + "-" + i_ports[indLut]
            to_pin = i_ports[indLut] + ":" + str(indPin)
        
            # if first_mux_assign:
            #     to_track_to_first_mux[i].append(mux_name)
            second_mux = (mux_name, to_pin)
            # print("assign " + str(fromName) + " " + from_details + " to " + mux_name)

            stagemuxfrom = TwoStageMuxFrom_inf(
                type_str, fromName, from_details, 0)
            if second_mux in StageMuxFroms:
                StageMuxFroms[second_mux].append(stagemuxfrom)
            else:
                StageMuxFroms[second_mux] = [stagemuxfrom]  
            indPin = (indPin + 1) % K

    return (indPin, segId)

def assignFbToFirstStage(StageMuxFroms, num):
    
    i_ports = ("Ia", "Ib", "Ic", "Id", "Ie", "If", "Ig", "Ih")
    pins = ["o", "q"]
        
    indOmux = 0
    
    # assign the drives from pb following the lut order

    for indMux in range(num):

            
        mux_name = "mux2nd_" + str(indMux)

        if (indMux % 3 == 2):
            type_str = "omux"
            fromName = "oxbar"
            from_details = "OG_" + str(indOmux)
            indOmux = (indOmux + 1) % 8
        else:
            type_str = "pb"
            fromName = "plb"
            from_details = pins[indMux % 3] + ":" + str(indMux // 3 % 8)


        stagemuxfrom = TwoStageMuxFrom_inf(
            type_str, fromName, from_details, 0)
        if mux_name in StageMuxFroms:
            StageMuxFroms[mux_name].append(stagemuxfrom)
        else:
            StageMuxFroms[mux_name] = [stagemuxfrom]  
        indMux += 1

def assignSegThroughThreeStage(segments, GLBStageMuxFroms, firstStageMuxFroms, secondStageMuxFroms, glbGroupNum, glbGroupSize, glbStageSize, firstStageNum, secondStageSize, K, N, mux_fanin, segIdSofar):

    # assign the seg that drives CLB through three stages
    segThreeStageNum = {}
    segThreeStageRatio = {}
    totalThreeStageNum = 0
    for seg in segments:
        segThreeStageNum[seg.name] = seg.num_three_stage_driven
        totalThreeStageNum += seg.num_three_stage_driven
        if segThreeStageNum[seg.name] == 0:
            segThreeStageNum.pop(seg.name)
    for segName in segThreeStageNum:
        segThreeStageRatio[segName] = segThreeStageNum[segName] / totalThreeStageNum
    segIdSofar = segThreeStageNum

    print("seg to the num that it drives CLB through three stages:"+str(segThreeStageNum))
    
    # assign the times that each seg appears 
    segThreeStageTimes = {}
    minTimes = glbStageSize * glbGroupSize
    glbGroupConnections = glbGroupSize * glbStageSize
    segCheck = 0
    minSeg = []
    for segName in segThreeStageRatio.keys():
        segTimes = int(glbGroupConnections * segThreeStageRatio[segName])
        segThreeStageTimes[segName] = segTimes
        segCheck = segCheck + segThreeStageTimes[segName]
        if (minTimes == segTimes):
            minSeg.append(segName)
        if (minTimes > segTimes):
            minTimes = segTimes
            minSeg = [segName]

    ind = 0
    while(segCheck != glbGroupConnections):
        segName = minSeg[ind]
        segThreeStageTimes[segName] = segThreeStageTimes[segName] + 1
        segCheck = segCheck + 1
        ind = (ind + 1) % len(minSeg)
    print("three stages seg's times appearing in one group:"+ str(segThreeStageTimes))

    # according to segThreeStageTimes assign the seg to glb stage, the from detail info is affected by segThreeStageNum

    muxOffset = 0
    dirIdOffset = 0
    for seg in segments:
        if seg.name in segThreeStageNum:
            segIdOffset = 0
            segNum = segThreeStageNum[seg.name]
            segTimes = segThreeStageTimes[seg.name]
            indList = [i for i in range(segNum)]
            print(seg.name + ':' + str(indList))
            (muxOffset, segIdOffset) = assignGLBStageMuxFromSeg(GLBStageMuxFroms, seg, indList, segNum, segTimes, glbGroupNum, glbGroupSize, glbStageSize, muxOffset, dirIdOffset, segIdOffset)

    assignFirstStageFromGLB(firstStageMuxFroms, glbGroupNum, glbGroupSize, firstStageNum)

    assignSecondStageFromFirst(secondStageMuxFroms, secondStageSize, firstStageNum, K, N)

    return segIdSofar

def assignSegThroughTwoStage(segments, firstStageMuxFroms, secondStageMuxFroms, firstStageSize, firstStageNum, secondStageSize, K, N, mux_fanin, segIdSofar):


    # assign the seg that drives CLB through two stages
    segTwoStageNum = {}
    segTwoStageRatio = {}
    totalTwoStageNum = 0
    for seg in segments:
        segTwoStageNum[seg.name] = seg.num_two_stage_driven
        totalTwoStageNum += seg.num_two_stage_driven
        if segTwoStageNum[seg.name] == 0:
            segTwoStageNum.pop(seg.name)
    for segName in segTwoStageNum:
        segTwoStageRatio[segName] = segTwoStageNum[segName] / totalTwoStageNum
    
    print("seg to the num that it drives CLB through two stages:"+str(segTwoStageNum))
    # assign the times that each seg appears 
    firstGroupSize = 4
    segTwoStageTimes = {}
    minTimes = firstStageSize * firstGroupSize
    glbGroupConnections = firstGroupSize * firstStageSize
    segCheck = 0
    minSeg = []

    for segName in segTwoStageRatio.keys():
        segTimes = int(glbGroupConnections * segTwoStageRatio[segName])
        segTwoStageTimes[segName] = segTimes
        segCheck = segCheck + segTwoStageTimes[segName]
        if (minTimes == segTimes):
            minSeg.append(segName)
        if (minTimes > segTimes):
            minTimes = segTimes
            minSeg = [segName]
    
    ind = 0
    while(segCheck != glbGroupConnections):
        segName = minSeg[ind]
        segTwoStageTimes[segName] = segTwoStageTimes[segName] + 1
        segCheck = segCheck + 1
        ind = (ind + 1) % len(minSeg)
    print("three stages seg's times appearing in one group:" + str(segTwoStageTimes))

    
    # according to segTwoStageTimes assign the seg to first stage, the from detail info is affected by segThreeStageNum
    firstGroupNum = 15
    firstGroupSize = 4

    muxOffset = 0
    dirIdOffset = 0
    
    for seg in segments:
        segIdOffset = 0
        if seg.name in segTwoStageNum:
            segNum = segTwoStageNum[seg.name]
            segTimes = segTwoStageTimes[seg.name]
            if seg.name in segIdSofar:
                indList = [i + segIdSofar[seg.name] for i in range(segNum)]
                segIdSofar[seg.name] += segNum
            else:
                indList = [i for i in range(segNum)]
                segIdSofar[seg.name] = segNum

            print(seg.name + ':' + str(indList))
            (muxOffset, segIdOffset) = assignFirstStageMuxFromSeg(firstStageMuxFroms, seg, indList, segNum, segTimes, firstGroupNum, firstGroupSize, muxOffset, segIdOffset, dirIdOffset, 'mux2nd_')
    
    assignSecondStageFromFirst(secondStageMuxFroms, secondStageSize, firstStageNum, K, N)
    return segIdSofar


def assignSegThroughOneStage(segments, secondStageMuxFroms, secondStageSize, K, N, mux_fanin, segIdSofar):

    # assign the seg that drives CLB through two stages
    segOneStageNum = {}
    segOneStageRatio = {}
    totalOneStageNum = 0
    for seg in segments:
        segOneStageNum[seg.name] = seg.num_one_stage_driven
        totalOneStageNum += seg.num_one_stage_driven
        if segOneStageNum[seg.name] == 0:
            segOneStageNum.pop(seg.name)
    for segName in segOneStageNum:
        segOneStageRatio[segName] = segOneStageNum[segName] / totalOneStageNum
    print("seg to the num that it drives CLB through one stages:" + str(segOneStageNum))
    # assign the times that each seg appears 
    firstGroupSize = 4
    segOneStageTimes = {}
    minTimes = secondStageSize * K
    groupConnections = secondStageSize * K
    segCheck = 0
    minSeg = []
    for segName in segOneStageRatio.keys():
        segTimes = int(groupConnections * segOneStageRatio[segName])
        segOneStageTimes[segName] = segTimes
        segCheck = segCheck + segOneStageTimes[segName]
        if (minTimes == segTimes):
            minSeg.append(segName)
        if (minTimes > segTimes):
            minTimes = segTimes
            minSeg = [segName]
    
    ind = 0
    while(segCheck != groupConnections):
        segName = minSeg[ind]
        segOneStageTimes[segName] = segOneStageTimes[segName] + 1
        segCheck = segCheck + 1
        ind = (ind + 1) % len(minSeg)
    print("three stages seg's times appearing in one group:" + str(segOneStageTimes))

    pinOffset = 0
    for seg in segments:
        segIdOffset = 0
        if seg.name in segOneStageNum:
            segNum = segOneStageNum[seg.name]
            segTimes = segOneStageTimes[seg.name]
            if seg.name in segIdSofar:
                indList = [i + segIdSofar[seg.name] for i in range(segNum)]
                segIdSofar[seg.name] += segNum
            else:
                indList = [i for i in range(segNum)]
                segIdSofar[seg.name] = segNum
            print(seg.name + ':' + str(indList))
            (pinOffset, segIdOffset) = assignSecondStageMuxFromSeg(secondStageMuxFroms, seg, indList, segNum, segTimes, K, N, pinOffset, segIdOffset)


def assignMultiStageMuxForImux(segments, imux_froms, imux_mux_fanin, imuxElem):

    
    imux_two_stage = ET.SubElement(imuxElem, "multistage_muxs")
    first_stage = ET.SubElement(imux_two_stage, "first_stage")
    first_stage.set("switch_name", "imux_medium_mux")
    second_stage = ET.SubElement(imux_two_stage, "second_stage")
    glb_stage = ET.SubElement(imux_two_stage, "glb_stage")
    glb_stage.set("switch_name", "imux_medium_mux")

    glbStageSize = 6
    glbGroupSize = 4
    glbGroupNum = 4
    glbStageNum = glbGroupNum * glbGroupSize
    glbConnections = glbStageSize * glbStageNum

    secondStageSize = 6

    K = 6
    N = 8

    firstStageNum = 40

    GLBStageMuxFroms = {}
    firstStageMuxFroms = {}
    secondStageMuxFroms ={}
    segIdSofar = {}

    segIdSofar = assignSegThroughThreeStage(segments, GLBStageMuxFroms, firstStageMuxFroms, secondStageMuxFroms, glbGroupNum, glbGroupSize, glbStageSize, firstStageNum, secondStageSize, K, N, imux_mux_fanin, segIdSofar)
    print("segIdSofar " + str(segIdSofar))

    firstStageSize = 4
    segIdSofar = assignSegThroughTwoStage(segments, firstStageMuxFroms, secondStageMuxFroms, firstStageSize, firstStageNum, secondStageSize, K, N, imux_mux_fanin, segIdSofar)
    print("segIdSofar " + str(segIdSofar))

    assignSegThroughOneStage(segments, secondStageMuxFroms, secondStageSize, K, N, imux_mux_fanin, segIdSofar)

    assignFbToFirstStage(firstStageMuxFroms, firstStageNum)

    

    for k, v in GLBStageMuxFroms.items():
        mux_from = ET.SubElement(glb_stage, "mux")
        mux_from.set("name", k)
        fanin = 0
        #print("\tmux_name" + k)
        for vv in v:
            #vv.show()
            vv.to_arch(mux_from)
            fanin += vv.count_detail_nums()
        imux_mux_fanin["glb"][k] = fanin

    for k, v in firstStageMuxFroms.items():
        mux_from = ET.SubElement(first_stage, "mux")
        mux_from.set("name", k)
        fanin = 0

        for vv in v:
            if type(vv) is str:
                a_from = ET.SubElement(mux_from, "from")
                a_from.set("mux_name", vv)
                fanin += len(v)
            else:
                vv.to_arch(mux_from)
                fanin += vv.count_detail_nums()
        
        imux_mux_fanin["first"][k[0]] = fanin

    
    for k, v in secondStageMuxFroms.items():
        mux_from = ET.SubElement(second_stage, "mux")
        mux_from.set("name", k[0])
        mux_from.set("to_pin", k[1])
        fanin = 0

        for vv in v:
            if type(vv) is str:
                a_from = ET.SubElement(mux_from, "from")
                # a_from.set("mux_name", " ".join(vv))
                a_from.set("mux_name", vv)
                fanin += len(vv)
            else:
                vv.to_arch(mux_from)
                fanin += vv.count_detail_nums()
        
        imux_mux_fanin["second"][k[0]] = fanin

    


def generateMultiStageMux(archTree, segments):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    gsbElem = gsb_arch.find("gsb")
    imuxElem = gsb_arch.find("imux")
    segsElem = archTree["root"].getroot().find("segmentlist")
    
    if imuxElem.find("multistage_muxs") != None:
        imuxElem.remove(imuxElem.find("multistage_muxs"))
    if gsbElem.find("multistage_muxs") != None:
        gsbElem.remove(gsbElem.find("multistage_muxs"))

    imux = {}
    imux_mux_fanin ={}
    imux_mux_fanin["first"] = {}
    imux_mux_fanin["second"] = {}
    imux_mux_fanin["glb"] = {}
    
    gsb_mux_fanin = {}
    gsb_mux_fanin["first"] = {}
    gsb_mux_fanin["second"] = {}

    for lut_group in imuxElem:
        lut_name = lut_group.get("name")
        imux_froms = []
        for fromElem in lut_group:
            imux_froms.append(From_inf(fromElem))
        imux[lut_name] = imux_froms
    if len(imux) > 1:
        raise ArchError("too many lut_group in imux, only one lut_group is ok")
    assignMultiStageMuxForImux(segments, imux_froms, imux_mux_fanin, imuxElem)
    
    gsb = {}
    to_mux_nums = {}
    gsb_mux_fanin = {}
    gsb_mux_fanin["first"] = {}
    gsb_mux_fanin["second"] = {}

    segs = {}
    segs_numfreq = {}
    segElems = []
    seg_num = 0

    for seg in segsElem:
        seg_info = Seg_inf(seg)
        if (seg.get('name')[0] == 'l'):
            seg_name = seg.get("name")
            seg_length = int(seg.get("length"))
            segs[seg_name] = seg_length
            segs_numfreq[seg_name] = int(float(seg.get("freq")) / 2 / seg_length)
            seg_info.total_froms = int(float(seg.get("freq")) / 2 / seg_length)
            # print(str(seg_name) + ' ' + str(seg_info.total_froms))
            seg_num = seg_num + segs_numfreq[seg_name]
            segElems.append(seg_info) 
        # print(seg_info.total_from)
    for seg_name in segs_numfreq.keys():
        segs_numfreq[seg_name] = segs_numfreq[seg_name] / seg_num
    pin_froms = []
    for seg_group in gsbElem.findall('seg_group'):
        to_seg_name = seg_group.get("name")
        if (to_seg_name == "l1"):
            print('enter gsb l1 group')
            for fromElem in seg_group.findall('from'):
                if fromElem.get("type") != "seg":
                    if fromElem.get("type") == "pb":
                        # divide the pb from description into seperate From_inf acccording to its pin_types
                        # from_details = fromElem.get("pin_types").split()
                        from_details = ['o', 'q']
                        for pin_type in from_details:
                            pin_from = From_inf(fromElem)
                            pin_from.pin_types = pin_type
                            pin_froms.append(pin_from)
                    else:
                        pin_froms.append(From_inf(fromElem))
        seg_froms = []
        for fromElem in seg_group:
            seg_froms.append(From_inf(fromElem))

        gsb[to_seg_name] = seg_froms
        to_mux_nums[to_seg_name] = int(seg_group.get("track_nums"))
    assignTwoStageMux_gsb_v200(segs, gsb, to_mux_nums, gsb_mux_fanin, gsbElem, segs_numfreq, segElems, pin_froms)
    
    return (gsb_mux_fanin, imux_mux_fanin)


def objectiveTest(variables, space, archTree):
    segments, relations, chanWidth, typeToNum = genArch(variables)
    if chanWidth < 160:
        segments, relations, chanWidth, typeToNum = genArch(variables)
    # segments, relations, chanWidth = genArch3(variables)
    # segments, relations, chanWidth = genArch2(variables)
    modifyArch_V3_bent(segments, relations, archTree)
    writeArch2(archTree["root"].getroot(), "./testGenerateMultiInter.xml")
    modifyArch_addMedium(archTree)
    for seg in segments:
        seg.show()
    (gsbMUXFanin, imuxMUXFanin) = generateMultiStageMux(archTree, segments)
    writeArch2(archTree["root"].getroot(), "./testGenerateMulti.xml")
    return 0

if __name__ == '__main__':

    archTree = readArch2("../arch/multiTemplate.xml")

    trials = Trials()
    maxSegLen = 16
    space = [hp.uniform("var" + str(idx), 0.0, 1.0) for idx in range(maxSegLen * 7)]

    fmin(
        # partial(objective, space=space, trials=trials, base_arch_tree=base_arch_tree, new_arch_name=new_arch_name),
        partial(objectiveTest, space=space, archTree = archTree),
        space=space,
        # algo=tpe.suggest,
        algo=partial(mix.suggest, p_suggest=[(0.2, rand.suggest), (0.8, tpe.suggest)]),
        # algo=partial(tpe.suggest, n_startup_jobs=1, n_EI_candidates=4),
        max_evals=1,
        trials=trials,
        # connect_string = connect_string,
        # return_argmin=True,
    )