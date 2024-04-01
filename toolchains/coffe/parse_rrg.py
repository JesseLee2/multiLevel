##########the rrg file is so big, need to speed up
import time
import xml.etree.cElementTree as ET
from collections import Counter
import multiprocessing
from multiprocessing import Process, Manager, Lock
import sys

import math
import os
import utils

CPU_CNT = multiprocessing.cpu_count()
NPROCESSES = 4

class ProcessGroup:
    def __init__(self):
        self.processes = []

    def start_process(self, task, param_list):
        for i in range(NPROCESSES):
            self.processes.append(Process(target=task, args=param_list[i]))
        for i in range(NPROCESSES):
            self.processes[i].start()
    def join_process(self):
        for i in range(NPROCESSES):
            self.processes[i].join()


class NodeProfile:
    """"describe the node tag in rrg"""
    def __init__(self, id, mux_type, segment_id, coordinate = ()):
        self.id = id
        self.type = mux_type
        self.segment_id = segment_id
        self.coordinate = coordinate

class MuxInfo:
    """describe a mux info, including mux size, mux fanin type, mux type(driving which segment), and mux fanout type"""
    def __init__(self, mux_size, mux_fanin_type, mux_type, coordinate):
        self.mux_size = mux_size
        self.mux_fanin_type = mux_fanin_type
        self.mux_type = mux_type
        self.coordinate = coordinate

    def __eq__(self, other):
        #only care about the mux size and which segment it drives
        return self.mux_size == other.mux_size and self.mux_type == other.mux_type and Counter(self.mux_fanin_type) == Counter(other.mux_fanin_type)

    def __hash__(self):
        return hash((self.mux_size, self.mux_type, tuple(self.mux_fanin_type)))

    def print_mux_info(self):
        print('mux type: ' + str(self.mux_type) + '; mux size: ' + str(self.mux_size) + '; mux_fanin_type: ' + str(self.mux_fanin_type))

class SegmentProfile:
    """this class contain a wire info, with load and driving mux info"""
    seg_len_dict = {}
    seg_name_dict = {}
    def __init__(self, segment_id, wire_length, seg_name):
        self.segment_id = segment_id
        self.wire_length = wire_length
        self.fanout_mux = []
        self.driver_mux = None
        self.seg_name = seg_name

    def add_load_mux(self, load_mux):
        self.fanout_mux.append(load_mux)

    def add_driver_mux(self, driver_mux):
        self.driver_mux = driver_mux

    def get_load_distances(self):
        """get distance between each load mux and the driver mux, if distance is 0, ratio*tile_lengh determines distance between 2 muxes within one tile"""
        #(type, direction):(CHANX, INC_DIR)->(0,0), (CHANX, DEC_DIR)->(0,1), (CHANY, INC_DIR)->(1,0), (CHANY, DEC_DIR)->(1,1),
        #type xor direction is the length offset introduced by coordinate system
        self.load_mux_loc = []
        driver_mux_loc = self.driver_mux.coordinate
        for load_mux in self.fanout_mux:
            load_mux.print_mux_info()
            if self.wire_length == 0:
                dis = 0
            elif load_mux.mux_type in self.seg_len_dict:
                load_len = self.seg_len_dict[load_mux.mux_type]
                if load_len != 0:
                    #load mux drives a wire segment with lengh not equal to 0
                    if load_mux.coordinate[3] == driver_mux_loc[3]:
                        if load_mux.coordinate[2] == driver_mux_loc[2]:
                            #same type, same direction
                            dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1])
                        else:
                            #diff type, same direction
                            dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1])
                    else:
                        if load_mux.coordinate[2] == driver_mux_loc[2]:
                            #same type, diff direction
                            dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1]) + 1
                        else:
                            #diff type, diff direction
                            dis = abs(abs(driver_mux_loc[0]-load_mux.coordinate[0]) - abs(driver_mux_loc[1]-load_mux.coordinate[1])) + 1
                else:
                    if driver_mux_loc[-1] == 0:
                        dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1]) + 1
                    else:
                        dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1])
            else:
                if driver_mux_loc[-1] == 0:
                    dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1]) + 1
                else:
                    dis = abs(driver_mux_loc[0]-load_mux.coordinate[0]) + abs(driver_mux_loc[1]-load_mux.coordinate[1])
            self.load_mux_loc.append(dis)
        return self.load_mux_loc

    def get_seg_driver_mux_size(self):
        return self.driver_mux.mux_size

    def get_seg_distinct_profile(self):
        """this routine gets what matters when building spice netlist of a segment"""
        load_mux_distinct_profile = []
        load_mux_loc = self.get_load_distances()
        for i in range(len(self.fanout_mux)):
            load_mux_distinct_profile.append((self.fanout_mux[i].mux_size, load_mux_loc[i]))
        return (self.segment_id, self.get_seg_driver_mux_size(), tuple(sorted(load_mux_distinct_profile)))

    def __eq__(self, other):
        return self.segment_id == other.segment_id and self.driver_mux == other.driver_mux and Counter(self.fanout_mux) == Counter(other.fanout_mux)

    def __hash__(self):
        fanout_mux_key = []
        for mux in self.fanout_mux:
            fanout_mux_key.append((mux.mux_type, mux.mux_size, tuple(mux.mux_fanin_type)))
            # print((mux.mux_type, mux.mux_size, tuple(sorted(mux.mux_fanin_type))))
        # print(fanout_mux_key)
        # fanout_mux_key.sort()
        return hash((self.segment_id, self.driver_mux.__hash__(), tuple(fanout_mux_key)))

    def __nonzero__(self):
        return not self is None

    def print_seg_info(self, log):
        log.info('****************************************************************')
        log.info('segment name: ' + self.seg_name)
        log.info('segment length: ' + str(self.wire_length))
        log.info('driver mux size: ' + str(self.get_seg_driver_mux_size()))
        log.info(str(len(self.fanout_mux)) + ' load muxes:')
        for i in range(len(self.fanout_mux)):
            log.info("load mux size: " + str(self.fanout_mux[i].mux_size) + "; mux distance: " + str(self.load_mux_loc[i]))


def _get_certain_node_with_segment(node_ctx, center_coordinate, seg_len_dict):
    """get node_ctx info that has sub tag 'segment/segment_id' """
    # get node coordinate info
    xlow = int(node_ctx.find('loc').get('xlow'))
    ylow = int(node_ctx.find('loc').get('ylow'))
    xhigh = int(node_ctx.find('loc').get('xhigh'))
    yhigh = int(node_ctx.find('loc').get('yhigh'))

    if (node_ctx.get('type') == 'CHANX' or node_ctx.get('type') == 'CHANY'):
        #exclude SOURCE, SINK, OPIN, IPIN node
        seg_id = int(node_ctx.find('segment').get('segment_id'))
        seg_len = seg_len_dict[seg_id]
        if seg_len == 0 and (xlow == center_coordinate[0] and xhigh == center_coordinate[0]) and (
                ylow == center_coordinate[1] and yhigh == center_coordinate[1]):
            # handle segments that intra-connect within a tile
            node_id = int(node_ctx.get('id'))
            node_type = node_ctx.get('type')
            node_coordinate = _get_node_coordinate(node_ctx)
            return NodeProfile(node_id, node_type, seg_id, node_coordinate)
        elif (ylow == center_coordinate[1] and yhigh == center_coordinate[1]) and (
                center_coordinate[0] - seg_len + 1 <= xlow <= center_coordinate[0]) and (xhigh - xlow + 1 == seg_len) or \
                (xlow == center_coordinate[0] and xhigh == center_coordinate[0]) and (
                center_coordinate[1] - seg_len + 1 <= ylow <= center_coordinate[1]) and (yhigh - ylow + 1 == seg_len):
            # handle segments that inter-connect between different tiles
            node_id = int(node_ctx.get('id'))
            node_type = node_ctx.get('type')
            node_coordinate = _get_node_coordinate(node_ctx)
            return NodeProfile(node_id, node_type, seg_id, node_coordinate)
        return -1
    return  -1

def _get_certain_tile_node(node_ctx, center_coordinate, segments_ids_with_len_0):
    """judge the node_ctx whether belongs to a center tile, exclude SINK, SOURCE, OPIN, IPIN"""
    # get node_ctx coordinate info
    ##################################################
    xlow = int(node_ctx.find('loc').get('xlow'))
    ylow = int(node_ctx.find('loc').get('ylow'))
    xhigh = int(node_ctx.find('loc').get('xhigh'))
    yhigh = int(node_ctx.find('loc').get('yhigh'))

    # get all nodes with its driver mux implemented at center_coordinate tile
    if node_ctx.get('type') != 'SOURCE' and node_ctx.get('type') != 'SINK':
        #get node id
        id = int(node_ctx.get('id'))

        #get node type, if node is a pin, type is 'OPIN' or 'IPIN'; id node is a routing resource, type is 'CHANX' or 'CHANY'
        type = node_ctx.get('type')

        if center_coordinate[0] == xhigh and center_coordinate[1] == yhigh:
            # handle nodes at left and bottom side of gsb
            if node_ctx.find('segment') != None:
                # handle segments, exclude IPIN, OPIN
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                #for segments with length equal to 0, its driver mux must reside on the tile
                #for segments with length not equal to 0, only those with direction 'DEC_DIR' have the driver mux at the tile
                if segment_id in segments_ids_with_len_0 or node_ctx.get('direction') == 'DEC_DIR':
                    return NodeProfile(id, type, segment_id)
            #else:  # handle OPIN and IPIN
            #   return NodeProfile(id, type, None)
        elif center_coordinate[0] == xlow and center_coordinate[1] + 1 == ylow:
            #handle nodes at top side of gsb
            if node_ctx.find('segment') != None:
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                if segment_id not in segments_ids_with_len_0 and node_ctx.get('direction') == 'INC_DIR' and node_ctx.get('type') == 'CHANY':
                    return NodeProfile(id, type, segment_id)
        elif center_coordinate[0] + 1 == xlow and center_coordinate[1] == ylow:
            #handle nodes at right side of gsb
            if node_ctx.find('segment') != None:
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                if segment_id not in segments_ids_with_len_0 and node_ctx.get('direction') == 'INC_DIR' and node_ctx.get('type') == 'CHANX':
                    return NodeProfile(id, type, segment_id)
    return -1

def _get_node_coordinate(node):
    """get node coordinate in the form of (x, y, type, direction)"""
    xlow = int(node.find('loc').get('xlow'))
    xhigh = int(node.find('loc').get('xhigh'))
    ylow = int(node.find('loc').get('ylow'))
    yhigh = int(node.find('loc').get('yhigh'))
    coordinate = None
    if node.get('direction') != None:
        if node.get('direction') == 'INC_DIR':
            # load node may not be segment, so it can be 'OPIN' or 'IPIN', force type and direction to 0
            if node.get('type') == 'CHANX':
                coordinate = (xlow, ylow, 0, 0)
            else:
                coordinate = (xlow, ylow, 1, 0)
        else:
            if node.get('type') == 'CHANX':
                coordinate = (xhigh, yhigh, 0, 1)
            else:
                coordinate = (xhigh, yhigh, 1, 1)
    else:
        #if the node is not a wire segment, force type and direction to -1
        coordinate = (xlow, ylow, -1, -1)
    return coordinate

#define task function
def _parallel_task1(lock, rr_nodes, tile_nodes, seg_nodes, center_coordinate, seg_ids_with_length_0, segments):
    temp_seg_nodes = []
    temp_tile_nodes = []
    for node in rr_nodes:
        # get all nodes with its driver mux implemented at center_coordinate tile
        tile_node = _get_certain_tile_node(node, center_coordinate, seg_ids_with_length_0)
        if tile_node != -1:
            temp_tile_nodes.append(tile_node)

        # get connection strategy of each wire segment
        node_profile = _get_certain_node_with_segment(node, center_coordinate, segments)
        if node_profile != -1:
            temp_seg_nodes.append(node_profile)
    lock.acquire()
    tile_nodes.extend(temp_tile_nodes)
    seg_nodes.extend(temp_seg_nodes)
    lock.release()

def _parallel_task2(lock, rr_edges, tile_nodes_ids, seg_fanin_ids, seg_fanout_ids, tile_nodes_muxes_sizes, seg_fanin_id_dict, seg_fanout_id_dict):
    temp_seg_fanin_id_dict = {}
    temp_seg_fanout_id_dict = {}
    temp_tile_nodes_mux_sizes = {}

    for edge in rr_edges:
        src_node = int(edge.get('src_node'))
        sink_node = int(edge.get('sink_node'))

        # get fanin nodes for each segment node
        if sink_node in seg_fanin_ids:
            if temp_seg_fanin_id_dict.get(sink_node, -1) == -1:
                temp_seg_fanin_id_dict[sink_node] = set()
            temp_seg_fanin_id_dict[sink_node].add(src_node)

        # get fanout nodes for each segment node
        if src_node in seg_fanout_ids:
            if temp_seg_fanout_id_dict.get(src_node, -1) == -1:
                temp_seg_fanout_id_dict[src_node] = set()
            temp_seg_fanout_id_dict[src_node].add(sink_node)

        # get the number of fanin nodes for each tile node, irrespective of fanin type
        if sink_node in tile_nodes_ids:
            if temp_tile_nodes_mux_sizes.get(sink_node, -1) == -1:
                temp_tile_nodes_mux_sizes[sink_node] = 0
            temp_tile_nodes_mux_sizes[sink_node] = temp_tile_nodes_mux_sizes[sink_node] + 1

    lock.acquire()
    for k, v in temp_tile_nodes_mux_sizes.items():
        if tile_nodes_muxes_sizes.get(k, -1) == -1:
            tile_nodes_muxes_sizes[k] = 0
        tile_nodes_muxes_sizes[k] = tile_nodes_muxes_sizes[k] + v
    for k, v in temp_seg_fanin_id_dict.items():
        if seg_fanin_id_dict.get(k, -1) == -1:
            seg_fanin_id_dict[k] = set()
        seg_fanin_id_dict[k] = seg_fanin_id_dict[k] | v
    for k, v in temp_seg_fanout_id_dict.items():
        if seg_fanout_id_dict.get(k, -1) == -1:
            seg_fanout_id_dict[k] = set()
        seg_fanout_id_dict[k] = seg_fanout_id_dict[k] | v
    lock.release()
    #return (tile_nodes_mux_sizes, seg_fanin_id_dict, seg_fanout_id_dict)

def _parallel_task3(lock, rr_nodes, seg_fanin_id_set, seg_fanin_nodes_dict, seg_fanout_id_set, seg_fanout_nodes_dict):
    tmp_seg_fanin_nodes_dict = {}
    tmp_seg_fanout_nodes_dict = {}

    for node in rr_nodes:
        node_id = int(node.get('id'))
        if node_id in seg_fanin_id_set:
            coordinate = _get_node_coordinate(node)
            node_type = node.get('type')
            node_seg_id = -1 # OPIN etc type node doesnt have segment_id tag
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'OPIN'
            tmp_seg_fanin_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id, coordinate)
        if node_id in seg_fanout_id_set:
            coordinate = _get_node_coordinate(node)
            node_type = node.get('type')
            node_seg_id = -1
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'IPIN'
            tmp_seg_fanout_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id, coordinate)
    lock.acquire()
    seg_fanin_nodes_dict.update(tmp_seg_fanin_nodes_dict)
    seg_fanout_nodes_dict.update(tmp_seg_fanout_nodes_dict)
    lock.release()

def _parallel_task4(lock, rr_edges, seg_fanout_id_set, load_seg_fanin_id_dict):
    tmp_load_seg_fanin_id_dict = {}
    for edge in rr_edges:
        src_node = int(edge.get('src_node'))
        sink_node = int(edge.get('sink_node'))
        if sink_node in seg_fanout_id_set:
            if tmp_load_seg_fanin_id_dict.get(sink_node, -1) == -1:
                tmp_load_seg_fanin_id_dict[sink_node] = set()
            tmp_load_seg_fanin_id_dict[sink_node].add(src_node)
    lock.acquire()
    for k, v in tmp_load_seg_fanin_id_dict.items():
        if load_seg_fanin_id_dict.get(k, -1) == -1:
            load_seg_fanin_id_dict[k] = set()
        load_seg_fanin_id_dict[k] = load_seg_fanin_id_dict[k] | v
    lock.release()

def _parallel_task5(lock, rr_nodes, load_seg_fanin_id_set, load_seg_fanin_nodes_dict):
    tmp_load_seg_fanin_nodes_dict = {}
    for node in rr_nodes:
        node_id = int(node.get('id'))
        if node_id in load_seg_fanin_id_set:
            node_type = node.get('type')
            node_seg_id = -1
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'OPIN'
            tmp_load_seg_fanin_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id)
    lock.acquire()
    load_seg_fanin_nodes_dict.update(tmp_load_seg_fanin_nodes_dict)
    lock.release()

def parse_rrg(rrg_file_path, segment_length, log):
    """parse rrg_file and get routing path fragments, return all muxes of a tile, all segments with different loading,
    segment_length is a dict bundling segment_id and its actual length"""

    log.info("\n####################################################")
    log.info("start reading and parsing rrg file")

    #get rrg root node
    ####################################
    start_t = time.time()
    tree = ET.parse(rrg_file_path)
    end_t = time.time()
    log.info("reading rrg file costs %f seconds!" % (end_t - start_t))

    start_t = time.time()

    root = tree.getroot()

    # get center coordinate of the FPGA
    #######################################
    index_x = 0
    index_y = 0
    for x in root.iter('x_list'):
        index_x = max(index_x, int(x.attrib['index']))
    for y in root.iter('y_list'):
        index_y = max(index_y, int(y.attrib['index']))
    coordinate = (index_x, index_y)
    center_coordiante = (coordinate[0] // 2, coordinate[1] // 2)

    #todo:make sure that the block type is 'clb' at center_coordinate

    # get segments info including segment_id and its name
    ##########################################
    segments = {}
    seg_name_by_id = {}
    for segment in root.find('segments'):
        seg_name_by_id[int(segment.attrib['id'])] = segment.attrib['name']
    for key in seg_name_by_id.keys():
        segment_name = seg_name_by_id[key]
        if not segment_name in segment_length:
            print(segment_name)
            print(segment_length)
            print("segment_name not found!")
            log.error("segment (" + segment_name + ") in rrg file not found in segment_length_by_name dict! please check arch input file segment specification!")
            sys.exit(1)
        else:
            segments[key] = segment_length[segment_name]
    SegmentProfile.seg_len_dict = segments
    SegmentProfile.seg_name_dict = seg_name_by_id

    #get segments with length equal to 0
    seg_ids_with_length_0 = {k:v for k, v in segments.items() if v == 0}

    #traverse the rr_nodes tag and get representing nodes for one tile and CHANX\CHANY
    ################################################################
    #all routing nodes belonging to a tile, used to count the total num of mux belonging to a tile
    tile_nodes = set()

    #all routing nodes crossing through, souring, sinking at center coordinate, used to find the loading ways of each segment
    seg_nodes = set()

    #intermediate results
    manager = Manager()
    lock = Lock()
    #temp_tile_nodes = [manager.list() for i in range(NPROCESSES)]
    #temp_seg_nodes = [manager.list() for i in range(NPROCESSES)]
    temp_tile_nodes = manager.list()
    temp_seg_nodes = manager.list()

    #prepare parameter for each process
    rr_nodes = root.find('rr_nodes')
    rr_nodes_size = int(math.ceil(len(rr_nodes) / float(NPROCESSES)))
    param_list_1 = [(lock, rr_nodes[i * rr_nodes_size : (i + 1) * rr_nodes_size], temp_tile_nodes, temp_seg_nodes, center_coordiante, seg_ids_with_length_0, segments) for i in range(NPROCESSES)]

    # start process
    process_group1 = ProcessGroup()
    process_group1.start_process(_parallel_task1, param_list_1)
    process_group1.join_process()

    # get final results
    tile_nodes = set(temp_tile_nodes)
    seg_nodes = set(temp_seg_nodes)

    # print("after task1")
    # for nodes in tile_nodes:
    #     print(nodes.id)
    # for nodes in seg_nodes:
    #     print(nodes.id)


    #parse rr_edges to analyze fanin and fanout info of the node
    ########################################################
    #dict to store each tile node id and its driver mux size
    tile_nodes_mux_sizes = {node.id:0 for node in tile_nodes}

    #dict to store fanin and fanout of seg_nodes
    seg_fanin_id_dict = {node.id:set() for node in seg_nodes}
    # print(seg_fanin_id_dict)
    seg_fanout_id_dict = {node.id:set() for node in seg_nodes}

    #traverse rr_edges tag and get fanin and fanout info of each node
    #make it parallel
    rr_edges = root.find('rr_edges')
    rr_edges_size = int(math.ceil(len(rr_edges) / float(NPROCESSES)))
    tmp_tile_nodes_mux_sizes = Manager().dict()
    tmp_seg_fanin_id_dict = Manager().dict()
    tmp_seg_fanout_id_dict = Manager().dict()

    #prepare parameters for parallel processes
    param_list2 = [(lock, rr_edges[i * rr_edges_size : (i + 1) * rr_edges_size], tile_nodes_mux_sizes.keys(), seg_fanin_id_dict.keys(), seg_fanout_id_dict.keys(), tmp_tile_nodes_mux_sizes, tmp_seg_fanin_id_dict, tmp_seg_fanout_id_dict) for i in range(NPROCESSES)]

    #start_process
    process_group2 = ProcessGroup()
    process_group2.start_process(_parallel_task2, param_list2)
    process_group2.join_process()

    #get result
    tile_nodes_mux_sizes.update(tmp_tile_nodes_mux_sizes)
    seg_fanin_id_dict.update(tmp_seg_fanin_id_dict)
    seg_fanout_id_dict.update(tmp_seg_fanout_id_dict)

    # print('after parse task2')
    # print(tile_nodes_mux_sizes)
    # print(seg_fanin_id_dict)
    # print(seg_fanout_id_dict)

    #organize tile_nodes and counting the number of types of mux belonging to a tile, and the num of each type of mux
    ############################################
    tile_nodes_seg_id_by_node_id_dict = {node.id: node.segment_id for node in tile_nodes}
    # is_first = True
    for node in tile_nodes:
    #     if is_first:
    #         print(node.segment_id)
    #         is_first = False
        if node.segment_id == 5:
            print(node.id)
    # print(tile_nodes_seg_id_by_node_id_dict)
    tile_muxes =Counter([(tile_nodes_seg_id_by_node_id_dict[node_id], mux_size) for node_id, mux_size in tile_nodes_mux_sizes.items() if mux_size != 0])

    #organize seg_nodes to analyze fanin and fanout info of each segment node
    #####################################################
    #according fanin and fanout node id, get its associated segment id, if the fanin node doesnt have a segment id, it must be OPIN
    seg_fanin_id_set = set([fanin for fanins in seg_fanin_id_dict.values() for fanin in fanins])
    seg_fanin_nodes_dict = {node_id:None for node_id in seg_fanin_id_set}
    seg_fanout_id_set = set([fanout for fanouts in seg_fanout_id_dict.values() for fanout in fanouts])
    seg_fanout_nodes_dict = {node_id:None for node_id in seg_fanout_id_set}

    #intermediate results
    tmp_seg_fanin_nodes_dict = Manager().dict()
    tmp_seg_fanout_nodes_dict = Manager().dict()

    #prepare parameters
    param_list3 = [(lock, rr_nodes[i * rr_nodes_size : (i + 1) * rr_nodes_size], seg_fanin_id_set, tmp_seg_fanin_nodes_dict, seg_fanout_id_set, tmp_seg_fanout_nodes_dict) for i in range(NPROCESSES)]

    #start process
    process_group3 = ProcessGroup()
    process_group3.start_process(_parallel_task3, param_list3)
    process_group3.join_process()

    #get results
    seg_fanin_nodes_dict.update(tmp_seg_fanin_nodes_dict)
    seg_fanout_nodes_dict.update(tmp_seg_fanout_nodes_dict)
    # print('after parse task3')
    # print(seg_fanin_nodes_dict)
    # print(seg_fanout_nodes_dict)

    #after knowing fanout, need to figure out the mux info between current wire segment and its load wire segment
    load_seg_fanin_id_dict = {node_id:set() for node_id in seg_fanout_id_set}

    #intermediate results
    tmp_load_seg_fanin_id_dict = Manager().dict()

    #prepare parameters
    param_list4 = [(lock, rr_edges[i * rr_edges_size : (i + 1) * rr_edges_size], seg_fanout_id_set, tmp_load_seg_fanin_id_dict) for i in range(NPROCESSES)]

    #start process
    process_group4 = ProcessGroup()
    process_group4.start_process(_parallel_task4, param_list4)
    process_group4.join_process()

    #get results
    load_seg_fanin_id_dict.update(tmp_load_seg_fanin_id_dict)
    # print('after parse task4')
    # print(load_seg_fanin_id_dict)

    load_seg_fanin_id_set = set([fanin for fanins in load_seg_fanin_id_dict.values() for fanin in fanins])
    load_seg_fanin_nodes_dict = {node_id:None for node_id in load_seg_fanin_id_set}

    #intermediate results
    tmp_load_seg_fanin_nodes_dict = Manager().dict()

    #prepare parrameters
    param_list5 = [(lock, rr_nodes[i * rr_nodes_size : (i + 1) * rr_nodes_size], load_seg_fanin_id_set, tmp_load_seg_fanin_nodes_dict) for i in range(NPROCESSES)]

    #start process
    process_group5 = ProcessGroup()
    process_group5.start_process(_parallel_task5, param_list5)
    process_group5.join_process()

    #get results
    load_seg_fanin_nodes_dict.update(tmp_load_seg_fanin_nodes_dict)
    # print('after parse task5')
    # print(load_seg_fanin_nodes_dict)

    #merge data to produce wire segment info
    seg_profiles = set()
    for seg_node in seg_nodes:
        #driver mux info
        driver_mux_size = len(seg_fanin_id_dict[seg_node.id])
        driver_mux_type = seg_node.segment_id
        driver_mux_coord = seg_node.coordinate
        driver_mux_fanin_seg_ids = []
        for fanin_id in seg_fanin_id_dict[seg_node.id]:
            fanin_node = seg_fanin_nodes_dict[fanin_id]
            if fanin_node.segment_id == -1:
                driver_mux_fanin_seg_ids.append(fanin_node.type)
            else:
                driver_mux_fanin_seg_ids.append(fanin_node.segment_id)
        driver_mux = MuxInfo(driver_mux_size, driver_mux_fanin_seg_ids, driver_mux_type, driver_mux_coord)
        if seg_node.segment_id == 5:
            print(driver_mux.print_mux_info())
        
        #load mux info
        load_muxes = []
        for load_seg_node_id in seg_fanout_id_dict[seg_node.id]:
            load_mux_size = len(load_seg_fanin_id_dict[load_seg_node_id])
            load_seg_node = seg_fanout_nodes_dict[load_seg_node_id]
            load_mux_coord = load_seg_node.coordinate
            load_mux_type = None
            if load_seg_node.segment_id == -1:
                load_mux_type = load_seg_node.type
            else:
                load_mux_type = load_seg_node.segment_id
            load_mux_fanin_seg_ids = []
            for fanin_id in load_seg_fanin_id_dict[load_seg_node_id]:
                fanin_node = load_seg_fanin_nodes_dict[fanin_id]
                if fanin_node.segment_id == -1:
                    load_mux_fanin_seg_ids.append(fanin_node.type)
                else:
                    load_mux_fanin_seg_ids.append(fanin_node.segment_id)
            if not load_mux_size in [0, 1]:
                #exclude mux with mux size equal to 0 and 1
                #todo:if load mux size is 1, it is likely to be IPIN. it is appropriate to delete them?
                load_muxes.append(MuxInfo(load_mux_size, load_mux_fanin_seg_ids, load_mux_type, load_mux_coord))

        #fill a segmentprofile
        seg_profile = SegmentProfile(seg_node.segment_id, segments[seg_node.segment_id], seg_name_by_id[seg_node.segment_id])
        seg_profile.add_driver_mux(driver_mux)
        for load_mux in load_muxes:
            seg_profile.add_load_mux(load_mux)
        if not seg_profile.driver_mux.mux_size in [0,1]:
            #exclude muxes with mux size equal to 0 and 1
            seg_profiles.add(seg_profile)

    #exlude redundent segment
    #todo: this may cause some trouble for generating spice file, why not excluding when generating spice file?
    distinct_seg_profiles = []
    distinct_seg_tag = []
    for seg in seg_profiles:
        seg_distinct_info = seg.get_seg_distinct_profile()
        if not seg_distinct_info in distinct_seg_tag:
            distinct_seg_tag.append(seg_distinct_info)
            distinct_seg_profiles.append(seg)

    end_t = time.time()

    #tile_muxes should be found in seg_profiles, check if
    #########################################################
    seg_muxes = set([(tag[0], tag[1]) for tag in distinct_seg_tag])
    print(seg_muxes)
    print(tile_muxes)
    # for tile_mux in tile_muxes.keys():
    #     if not tile_mux in seg_muxes:
    #         print(tile_mux)
    #         log.error("mux from tile is not found in all muxes of all segment driver and load context!\nTile muxes should be included in seg_muxes")

    #log info
    #########################################################
    log.info('parsing rrg file costs time: %f seconds' % (end_t - start_t))
    log.info('there are %d distinct segments(driver mux size, load mux size and loc are two indicators to determine whether 2 segment is the same!)' % len(seg_profiles))
    for seg in seg_profiles:
        seg.print_seg_info(log)
    log.info("tile at coordinate (" + str(center_coordiante[0]) + "," + str(center_coordiante[1]) + ") has " + str(len(tile_nodes_mux_sizes)) + " muxes!")

    return seg_profiles, tile_muxes

if __name__ == '__main__':
    log_file = os.path.join('./', "logfile.log")
    log = utils.Logger(log_file)
    segment_info = {'l1':1, 'l2':2, 'l3':3, 'l4':4, 'l5':5, 'l8':8, 'l12':12, 'imux_medium':0, 'omux_medium':0, 'gsb_medium':0}
    parse_rrg('./rrg.xml', segment_info, log)
    # parse_rrg('/home/syh/projects/openfpga_gsb/rr.graph', segment_info)
    # parse_rrg('/home/syh/projects/openfpga_gsb/25*25')
    # _node_to_mux_profile(183362, '/home/syh/projects/openfpga_gsb/29*29')
