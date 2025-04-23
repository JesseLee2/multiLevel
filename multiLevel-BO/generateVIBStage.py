
import os
import xml.etree.cElementTree as ET
import re
from xml.dom import minidom

from functools import partial
# from hyperopt import hp, fmin, mix, tpe, rand, space_eval, STATUS_OK, STATUS_FAIL
# from hyperopt.mongoexp import MongoTrials, Trials

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


def addGLBFrom(archTree):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    imuxElem = gsb_arch.find("imux")
    imux_two_stage = imuxElem.find("multistage_muxs")
    first_stage = imux_two_stage.find("first_stage")
    i = 0

    for mux in first_stage.findall('mux'):
        
        fromNode = ET.SubElement(mux, "from")
        fromNode.set('type', 'glb')
        fromNode.set('name', 'glb')
        fromNode.set('from_detail', 'GLB' + str(i % 16))
        fromNode.set('switchpoint', "0")
        i += 1



def generateIMUXGLBStage(archTree, glb_num, glb_size, cas_size):

    # always followd by generateIMUXFirstStage

    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    imuxElem = gsb_arch.find("imux")
    imux_two_stage = imuxElem.find("multistage_muxs")
    glb_stage = ET.SubElement(imux_two_stage, "glb_stage")
    glb_stage.set("switch_name", "imux_medium_mux")

    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}

    for i in range(glb_num):
        muxName = "GLB" + str(i)
        segFromNum = int(glb_size * 0.5)
        casFromNum = glb_size - segFromNum
        mux = ET.SubElement(glb_stage, "mux")
        mux.set("name", muxName)

        for j in range(segFromNum):
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'seg')
            fromNode.set('name', 'l4')
            fromDetail = ind2dir[(i * segFromNum + j) % 4] + str((i * segFromNum + j) // 4)
            fromNode.set('from_detail', fromDetail)
            fromNode.set('switchpoint', str((i * segFromNum + j) % 4))
        
        for k in range(casFromNum):
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'cas')
            fromNode.set('name', 'cas')
            fromNode.set('from_detail', "SW_CAS" + str((i * casFromNum + k)% cas_size))
            fromNode.set('switchpoint', "0")

        fromNode = ET.SubElement(mux, "from")
        fromNode.set('type', 'glb')
        fromNode.set('name', 'glb')
        fromNode.set('from_detail', "GLB" + str((i + 1)% glb_num))
        fromNode.set('switchpoint', "0")
        

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
    print(segNum)
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
    # first_stage.set("switch_name", "imux_medium_mux")
    first_stage.set("switch_name", "imux_medium_mux")
    
    dirOffset = 0
    
    fromDetailOffsetPrev = 0
    spOffset = 0

    plbPins = ['o', 'q']

    indPin = 0

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

        # assign plb feedback from plb: o q omux(16)
        if i % 4 == 0:
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'omux')
            fromNode.set('name', 'oxbar')
            fromNode.set('from_detail', str(i // 4 % 8))
            fromNode.set('switchpoint', "0")
        else:
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('type', 'pb')
            fromNode.set('name', 'plb')
            plbFromDetail = plbPins[indPin % 2] + ":" + str(indPin // 2 % 8)
            indPin += 1
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
    # first_stage.set("switch_name", "gsb_medium_mux")
    first_stage.set("switch_name", "imux_medium_mux")
    
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
    # second_stage.set("switch_name", "only_mux")

    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}
    ind1STMux = 0
    ind2NDMux = 0

    for i in range(segNum):

        for indDir in range(4):
            ind2NDMux += 1
            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", ind2dir[indDir]+"-b"+str(i))
            mux.set("to_seg_name", "l4")
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

def generateGSBOneStage(archTree, size, segNum):
    
    ind2dir = {0:'W', 1:'E', 2:'S', 3:'N'}
    plbPins = ['o', 'q', 'o']

    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    gsbElem = gsb_arch.find("gsb")
    gsb_two_stage = gsbElem.find("multistage_muxs")
    if gsb_two_stage.find("second_stage") != None:
        gsb_two_stage.remove(gsb_two_stage.find("second_stage"))
    second_stage = ET.SubElement(gsb_two_stage, "second_stage")
    dirOffset = 0
    fromDetailOffsetPrev = 0
    spOffset = 0


    for i in range(segNum):
        spOffset = (spOffset + 1) % 4
        for indDir in range(4):
            segDir = ind2dir[indDir]
            
            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", ind2dir[indDir]+"-b"+str(i))
            mux.set("to_seg_name", "l4")
            mux.set("to_track", ind2dir[indDir]+str(i))
            (detailSPList, dirOffset, fromDetailOffsetCur, spOffset) = generateDetailSPList(size, dirOffset, fromDetailOffsetPrev, spOffset, segNum, "GSB", 0)
            for j in range(size):
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

        fromDetailOffsetPrev = fromDetailOffsetCur

def generateCBSBInGSB(archTree):
    
    # size: * Fcin
    generateIMUXFirstStage(archTree, 4, 80, 20)

    # the imux second stage acts as crossbar to LUT. Full Connect
    generateIMUXSecondStage(archTree, 10, 80, 6, 8)
    generateGSBOneStage(archTree, 12, 20)

def generateOMUX(archTree):
    gsb_arch = archTree["root"].getroot().find("gsb_arch")
    gsbElem = gsb_arch.find("gsb")
    multiSstage = gsbElem.find("multistage_muxs")
    firstStage = multiSstage.find("first_stage")

    N = 16
    S = 8

    oOffset = 0
    qOffset = 0

    for i in range(N):
        muxName = 'omux-' + str(i)
        mux = ET.SubElement(firstStage, "mux")
        mux.set('name', muxName)

        for j in range(S):
            omuxFrom = ET.SubElement(mux, "from")
            if (j < S // 2):
                omuxFrom.set("type", "pb")
                omuxFrom.set("name", "plb")
                fromDetail = "o:" + str(oOffset % 8)
                omuxFrom.set("from_detail", fromDetail)
                omuxFrom.set("switchpoint", "0")
                oOffset += 1
            else:
                omuxFrom.set("type", "pb")
                omuxFrom.set("name", "plb")
                fromDetail = "q:" + str(qOffset % 8)
                omuxFrom.set("from_detail", fromDetail)
                omuxFrom.set("switchpoint", "0")
                qOffset += 1


        



def generateMultiInVIB(archTree, L, listN, listSw, listSf, listSm, segNum, isDcm):
    
    gsb_arch = archTree["root"].getroot().find("gsb_arch")

    plbPins = ['o', 'q']
    ind2dir = {0: 'W', 1:'E', 2:'N', 3:'S'}
    gsbElem = gsb_arch.find("gsb")
    if gsbElem.find("multistage_muxs") != None:
        gsbElem.remove(gsbElem.find("multistage_muxs"))
    gsb_seg_group = gsbElem.find("seg_group")
    gsb_seg_group.set("track_nums", str(segNum))
    gsb_two_stage = ET.SubElement(gsbElem, "multistage_muxs")
    first_stage = ET.SubElement(gsb_two_stage, "first_stage")
    # first_stage.set("switch_name", "gsb_medium_mux")
    first_stage.set("switch_name", "gsb_medium_mux")
    fromDetailOffsetPrev = 0
    indMux = 0
    dirOffset = 0
    spOffset = 0
    
    # generateOMUX(archTree)

    for i in range(L-1):
        indPlbO = 0
        indOMUX = 0
        indFrom = 0

        for j in range(listN[i]):
            muxName = 'mux-' + str(i) + "-" + str(j)
            mux = ET.SubElement(first_stage, "mux")
            mux.set('name', muxName)
            

            if (i == 0):
                size = listSw[0]
                (detailSPList, dirOffset, fromDetailOffsetCur, spOffset) = generateDetailSPList(size, dirOffset, fromDetailOffsetPrev, spOffset, segNum, "IMUX", 0)
                for k in range(size):
                    fromNode = ET.SubElement(mux, "from")
                    fromNode.set('type', 'seg')
                    fromNode.set('name', 'l4')
                    fromNode.set('from_detail', detailSPList[k][0])
                    fromNode.set('switchpoint', detailSPList[k][1])
                for k in range(listSf[0]):
                    if (isDcm):
                        pin = 'o' if (k % 2 == 0) else 'q'
                        fromNode = ET.SubElement(mux, "from")
                        fromNode.set('type', 'pb')
                        fromNode.set('name', 'plb')
                        fromNode.set('from_detail', pin + ':' + str(indPlbO))
                        indPlbO = (indPlbO + 1) % 8


                    pin = 'o' if (k % 2 == 0) else 'q'
                    fromNode = ET.SubElement(mux, "from")
                    fromNode.set('type', 'pb')
                    fromNode.set('name', 'plb')
                    fromNode.set('from_detail', pin + ':' + str(indPlbO))
                    if k % 2:
                        indPlbO = (indPlbO + 1) % 8

            else:
                (detailSPList, dirOffset, fromDetailOffsetCur, spOffset) = generateDetailSPList(listSw[i], dirOffset, fromDetailOffsetPrev, spOffset, segNum, "IMUX", 0)
                for k in range(listSw[i]):
                    fromNode = ET.SubElement(mux, "from")
                    fromNode.set('type', 'seg')
                    fromNode.set('name', 'l4')
                    fromNode.set('from_detail', detailSPList[k][0])
                    fromNode.set('switchpoint', detailSPList[k][1])
                for k in range(listSf[i]):
                    pin = 'o' if (k % 2 == 0) else 'q'
                    fromNode = ET.SubElement(mux, "from")
                    fromNode.set('type', 'pb')
                    fromNode.set('name', 'plb')
                    fromNode.set('from_detail', pin + ':' + str(indPlbO))
                    indPlbO = (indPlbO + 1) % 8
                for k in range(listSm[i]):
                    if (k == 0):
                        fromName = 'mux-' + str(i-1) + "-" + str(indFrom % listN[i-1])
                    else:
                        fromName = ' mux-' + str(i-1) + "-" + str(indFrom % listN[i-1])
                    indFrom += 1
                if (len(listSm) > 0):
                    fromNode = ET.SubElement(mux, "from")
                    
                    fromNode.set('mux_name', fromName)

            # if (j % 8 < 3):
            #     a = 0
            #     # fromNode.set('type', 'pb')
            #     # fromNode.set('name', 'plb')
            #     # fromNode.set('from_detail', 'o:' + str(indPlbO))
            #     # indPlbO = (indPlbO + 1) % 8
            # else:
            #     fromNode = ET.SubElement(mux, "from")
            #     fromNode.set('mux_name', 'omux-' + str(indOMUX))
            #     indOMUX = (indOMUX + 1) % 16
                


            if indMux % 4 == 3:
                dirOffset = (dirOffset + 1) % 4
                fromDetailOffsetPrev = fromDetailOffsetCur
            indMux += 1

    
    second_stage = ET.SubElement(gsb_two_stage, "second_stage")

    ind2pin = {0:"Ia", 1:"Ib", 2:"Ic", 3:"Id", 4:"Ie", 5:"If", 6:"Ig", 7:"Ih", }
    indMux = 0
    indFrom = 0
    indPlb = 0
    K = 6
    N = 8
    for indLut in range(N):
        for indpin in range(K):

            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", "mux-" + str(L-1)+ "-" + str(indMux))
            mux.set("to_pin", ind2pin[indLut] + ":" + str(indpin))

            muxFrom = ""

            for k in range(listSm[-1]):
                muxFrom = muxFrom + " mux-" + str(L-2) + "-" + str(indFrom % listN[-2])
                indFrom += 1
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('mux_name', muxFrom[1:])
            indMux += 1

            # for k in range(listSw[-1]):
            #     fromNode = ET.SubElement(mux, "from")
            #     fromNode.set('type', 'seg')
            #     fromNode.set('name', 'l4')
            #     fromNode.set('from_detail', detailSPList[k][0])
            #     fromNode.set('switchpoint', detailSPList[k][1])
            for k in range(listSf[-1]):
                pin = 'o' if (indPlb % 2 == 0) else 'q'
                fromNode = ET.SubElement(mux, "from")
                fromNode.set('type', 'pb')
                fromNode.set('name', 'plb')
                fromNode.set('from_detail', pin + ':' + str(indPlb // 2))
                indPlb = (indPlb + 1) % 16
    
    ind2NDMux = 0
    ind1STMux = 0
    indPlb = 0
    for i in range(segNum):
        for indDir in range(4):
            ind2NDMux += 1
            mux = ET.SubElement(second_stage, "mux")
            mux.set("name", ind2dir[indDir]+"-b"+str(i))
            mux.set("to_seg_name", "l4")
            mux.set("to_track", ind2dir[indDir]+str(i))

            muxFrom = ""

            for indFrom in range(listSm[-1]):
                muxFrom = muxFrom + " mux-" + str(L-2) + "-" + str((ind1STMux + indFrom) % listN[-2])
            fromNode = ET.SubElement(mux, "from")
            fromNode.set('mux_name', muxFrom[1:])
            
            # for k in range(listSw[-1]):
            #     fromNode = ET.SubElement(mux, "from")
            #     fromNode.set('type', 'seg')
            #     fromNode.set('name', 'l4')
            #     fromNode.set('from_detail', detailSPList[k][0])
            #     fromNode.set('switchpoint', detailSPList[k][1])
            for k in range(listSf[-1]):
                pin = 'o' if (indPlb % 2 == 0) else 'q'
                fromNode = ET.SubElement(mux, "from")
                fromNode.set('type', 'pb')
                fromNode.set('name', 'plb')
                fromNode.set('from_detail', pin + ':' + str(indPlb // 2))
                indPlb = (indPlb + 1) % 16

            # assign the additional drive -- omux
            
        
        ind1STMux += listSm[-1]

def genLists(variables):
    lowerBound = [2,     0, 0, 0, 0, 0,    0, 0, 0, 0, 0,     0, 0, 0, 0, 0,     4, 0, 0, 0, 0]
    upperBound = [5,     0, 80, 25, 20, 20,    8, 8, 12, 12, 12,     4, 6, 8, 8, 8,    12, 6, 6, 6, 0]
    L = round(lowerBound[0] + (upperBound[0] - lowerBound[0]) * variables[0])
    listN = list(variables[1: L+1])
    listSw = list(variables[6: L+6])
    listSf = list(variables[11: L+11])
    listSm = list(variables[16: L+16])
    for i in range(L):
        indN = i + 1
        indSw = i + 6
        indSf = i + 11
        indSm = i + 16
        listN[i] = round(lowerBound[indN] + (upperBound[indN] - lowerBound[indN]) * listN[i])
        listSw[i] = round(lowerBound[indSw] + (upperBound[indSw] - lowerBound[indSw]) * listSw[i])
        listSf[i] = round(lowerBound[indSf] + (upperBound[indSf] - lowerBound[indSf]) * listSf[i])
        listSm[i] = round(lowerBound[indSm] + (upperBound[indSm] - lowerBound[indSm]) * listSm[i])
    
    listN.reverse()
    listSw.reverse()
    listSf.reverse()
    listSm.reverse()
    print([listN, listSw, listSf, listSm])
    return [listN, listSw, listSf, listSm]

def checkSm(N, S):
    for i in range(1, len(S)):
        if S[i] > N[i-1]:
            return False
    return True

def checkArea(Sw, Sf, Sm):
    for i in range(len(Sw)):
        if Sw[i] + Sf[i] + Sm[i] > 8: 
            return False
    return True

def objectiveTest(variables, space, archTree):
    lists = genLists(variables)
    listN = lists[0]
    listSw = lists[1]
    listSf = lists[2]
    listSm = lists[3]
    if not checkSm(listN, listSm):
        return {
            'why': 'exceed trial limit',
            'status': STATUS_FAIL
        }
    generateMultiInVIB(archTree, len(listN), listN, listSw, listSf, listSm, 20)
    
    writeArch2(archTree["root"].getroot(), "./testGenerateMulti.xml")
    print("write done")
    return 0

if __name__ == '__main__':

    archTree = readArch2("./vibBaseline.xml")

    
    # baseline 80 80, base2 works the best
    comb_base = [[[60, 60, 60], [4, 4, 0], [4, 4, 1], [0, 1, 8]],
                [[60, 60, 60], [3, 3, 0], [4, 4, 1], [0, 1, 8]],
                [[60, 60, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
                [[60, 60, 60], [3, 3, 0], [3, 3, 1], [0, 1, 8]],
                [[60, 60, 60], [3, 3, 0], [2, 2, 1], [0, 1, 8]],
                [[60, 60, 60], [2, 2, 0], [3, 3, 1], [0, 1, 8]],
                [[60, 60, 60], [2, 2, 0], [2, 2, 1], [0, 1, 8]]]
    
    # exploration para set
    
    # combSw = [[[60, 60, 60], [3, 5, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [5, 3, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [4, 3, 1], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [3, 4, 1], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [3, 5, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [5, 3, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [4, 3, 1], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [3, 4, 1], [3, 3, 1], [0, 1, 8]],
    #           [[80, 40, 60], [3, 5, 0], [3, 3, 1], [0, 1, 8]],
    #           [[80, 40, 60], [5, 3, 0], [3, 3, 1], [0, 1, 8]],
    #           [[80, 40, 60], [4, 3, 1], [3, 3, 1], [0, 1, 8]],
    #           [[80, 40, 60], [3, 4, 1], [3, 3, 1], [0, 1, 8]]
    #           ]
    
    
    # combSw2 = [[[60, 60, 60], [2, 6, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [6, 2, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [1, 7, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [7, 1, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [0, 8, 0], [3, 3, 1], [0, 1, 8]],
    #           [[60, 60, 60], [8, 0, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [2, 6, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [6, 2, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [1, 7, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [7, 1, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [0, 8, 0], [3, 3, 1], [0, 1, 8]],
    #           [[40, 80, 60], [8, 0, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [6, 2, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [2, 6, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [1, 7, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [7, 1, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [0, 8, 0], [3, 3, 1], [0, 1, 8]],
    #           [[20, 100, 60], [8, 0, 0], [3, 3, 1], [0, 1, 8]]
    #           ]
    
    
    # combSf = [[[60, 60, 60], [4, 4, 0], [4, 2, 1], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [3, 2, 2], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [2, 4, 1], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [2, 3, 2], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [3, 4, 0], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [4, 3, 0], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [4, 2, 1], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [3, 2, 2], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [2, 4, 1], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [2, 3, 2], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [3, 4, 0], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [4, 3, 0], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [4, 2, 1], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [3, 2, 2], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [2, 4, 1], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [2, 3, 2], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [3, 4, 0], [0, 1, 8]],
    #           [[80, 40, 60], [4, 4, 0], [4, 3, 0], [0, 1, 8]],
    #           ]
    # combSf2 = [[[60, 60, 60], [4, 4, 0], [7, 0, 0], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [0, 7, 0], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [0, 0, 7], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [4, 0, 3], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [3, 0, 4], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [0, 3, 4], [0, 1, 8]],
    #           [[60, 60, 60], [4, 4, 0], [0, 4, 3], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [7, 0, 0], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [0, 7, 0], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [0, 0, 7], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [4, 0, 3], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [3, 0, 4], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [0, 3, 4], [0, 1, 8]],
    #           [[40, 80, 60], [4, 4, 0], [0, 4, 3], [0, 1, 8]],
    #           ]
    
    # combSm = [[[60, 60, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #          [[60, 60, 60], [4, 4, 0], [3, 3, 1], [0, 2, 7]],
    #          [[60, 60, 60], [4, 4, 0], [3, 3, 2], [0, 3, 6]],
    #          [[40, 80, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #          [[40, 80, 60], [4, 4, 0], [3, 3, 1], [0, 2, 7]],
    #          [[40, 80, 60], [4, 4, 0], [3, 3, 2], [0, 3, 6]],
    #          [[20, 100, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #          [[20, 100, 60], [4, 4, 0], [3, 3, 1], [0, 2, 7]],
    #          [[20, 100, 60], [4, 4, 0], [3, 3, 2], [0, 3, 6]],
    #          [[80, 40, 60], [4, 4, 0], [3, 3, 1], [0, 1, 9]],
    #          [[80, 40, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #          [[80, 40, 60], [4, 4, 0], [3, 3, 1], [0, 2, 7]],
    #          [[80, 40, 60], [4, 4, 0], [3, 3, 2], [0, 3, 6]],
    #          [[100, 20, 60], [4, 4, 0], [3, 3, 1], [0, 1, 9]],
    #          [[100, 20, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #          [[100, 20, 60], [4, 4, 0], [3, 3, 1], [0, 2, 7]],
    #          [[100, 20, 60], [4, 4, 0], [3, 3, 2], [0, 3, 6]],
    #          ]

    # combPattern = [[[60, 60, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    #                [[60, 60, 60], [7, 4, 0], [0, 3, 1], [0, 1, 8]],
    #                [[60, 60, 60], [0, 4, 0], [7, 3, 1], [0, 1, 8]],
    #                [[60, 60, 60], [4, 4, 0], [3, 3, 1], [0, 1, 8]],
    # ]


    # for comb in combSf[1:]:
    #     generateMultiInVIB(archTree, 3, comb[0], comb[1], comb[2], comb[3], 20, False)
    #     # swName = str(comb[1][1]) + "_" + str(comb[2][1]) + "_" + str(comb[3][1])
    #     sfName = str(comb[2][0]) + "_" + str(comb[2][1]) + "_" + str(comb[2][2])
    #     writeArch2(archTree["root"].getroot(), "./exp/sw2_" + sfName + ".xml")

    # for i in range(len(comb_base)):
    #     baseName = "base" + str(i)
    #     comb = comb_base[i]
    #     generateMultiInVIB(archTree, 3, comb[0], comb[1], comb[2], comb[3], 20, False)
    #     writeArch2(archTree["root"].getroot(), "./exp/base/" + baseName + ".xml")

    for i in range(len(combSf2)):
        baseName = "Sf" + str(i+20)
        comb = combSf2[i]
        generateMultiInVIB(archTree, 3, comb[0], comb[1], comb[2], comb[3], 20, False)
        writeArch2(archTree["root"].getroot(), "./exp/Sf/" + baseName + ".xml")
    
    
    # for i in range(len(combSf)):
    #     baseName = "Sf" + str(i)
    #     comb = combSf[i]
    #     generateMultiInVIB(archTree, 3, comb[0], comb[1], comb[2], comb[3], 20, False)
    #     writeArch2(archTree["root"].getroot(), "./exp/Sf/" + baseName + ".xml")
    
    
    # for i in range(len(combSm)):
    #     baseName = "Sm" + str(i)
    #     comb = combSm[i]
    #     generateMultiInVIB(archTree, 3, comb[0], comb[1], comb[2], comb[3], 20, False)
    #     writeArch2(archTree["root"].getroot(), "./exp/Sm/" + baseName + ".xml")


    # add some examples
    # generateMultiInVIB(archTree, 3, [16, 100, 60], [0, 4, 0], [4, 1, 0], [0, 1, 8], 20, True)
    # writeArch2(archTree["root"].getroot(), "./exp/sw_4_1.5_0.xml")
    


    # trials = Trials()
    # paramNum = 20
    # space = [hp.uniform("var" + str(idx), 0.0, 1.0) for idx in range(paramNum + 1)]

    # fmin(
    #     # partial(objective, space=space, trials=trials, base_arch_tree=base_arch_tree, new_arch_name=new_arch_name),
    #     partial(objectiveTest, space=space, archTree = archTree),
    #     space=space,
    #     # algo=tpe.suggest,
    #     algo=partial(mix.suggest, p_suggest=[(0.2, rand.suggest), (0.8, tpe.suggest)]),
    #     # algo=partial(tpe.suggest, n_startup_jobs=1, n_EI_candidates=4),
    #     max_evals=1,
    #     trials=trials,
    #     # connect_string = connect_string,
    #     # return_argmin=True,
    # )

    # L2 set
    # listN = [100, 60]
    # listSw = [4, 0]
    # listSf = [2, 1]
    # listSm = [0, 8]
    # generateMultiInVIB(archTree, len(listN), listN, listSw, listSf, listSm, 20)
    # writeArch2(archTree["root"].getroot(), "./multi/testL2.xml")
