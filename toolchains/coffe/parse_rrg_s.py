##########the rrg file is so big, need to speed up
import time
import xml.etree.cElementTree as ET
from collections import Counter

RECUR_DEPTH = 5


class RoutingPathFragment:
    """profile of a specificed routing path about the driver mux and load mux information"""

    def __init__(self):
        pass

    def __int__(self, path_type, segment_length, first_level_mux_size, first_level_mux_fanout, driver_mux_size,
                load_info):
        """path_type(string): omux, imux, routing_segments
           segment_length(int): required if path_type is routing_segments, indicating the length of the wire
           first_level_mux_size(int): required if path type is imux or routing_segments
           first_level_mux_fanout(int): required if path type is imux or routing_segments
           driver_mux_size(int): required among all path_types
           load_info([[(switch_id, mux_size)]]: the first indexing is about the load position along the wire for path_type routing_segments, 0 means no load at this position,
                                                switch_id indicates which path_type the load mux belongs
        """
        self.path = path_type
        self.segment_length = segment_length
        self.first_level_mux_size = first_level_mux_size
        self.first_level_mux_fanout = first_level_mux_fanout
        self.driver_mux_size = driver_mux_size
        self.load_info = load_info

class RoutingPathProfile:
    """describe the routing paths between muxes within one tile"""

    def __init__(self, muxes_of_tile):
        """list of mux, mux in the form of MuxProfile"""
        self.muxes = muxes_of_tile
        self.muxes_id = [mux.nodeid for mux in self.muxes]
        self.mux_types = []
        for mux in self.muxes:
            if mux.mux_info() not in self.mux_types:
                self.mux_types.append(mux.mux_info())
        self.mux_type_by_id = {}
        for mux in self.muxes:
            self.mux_type_by_id[mux.nodeid] = (mux.mux_info()[0], mux.mux_info()[1], len(mux.fanout) - 1)

    def _mux_id_to_profile(self, mux_id):
        """get mux type according to mux_id"""
        for mux in self.muxes:
            if mux_id == mux.nodeid:
                return mux

    def distinct_muxes(self):
        """abstract all muxes to a list of distinct muxes"""
        distinct_muxes = []
        for mux in self.muxes:
            if mux.mux_info() not in distinct_muxes:
                distinct_muxes.append(mux.mux_info())
        distinct_muxes_ = {mux[0]: [] for mux in distinct_muxes}
        for mux in distinct_muxes:
            distinct_muxes_[mux[0]].append(mux)
        print 'distinct_muxes: ', distinct_muxes_
        return distinct_muxes_

    def _mux_graph(self):
        """get mux graph in the form of {mux:[load_mux]}"""
        ids_of_muxes = [mux.nodeid for mux in self.muxes]
        graph = {muxid: [] for muxid in self.muxes_id}
        for mux in self.muxes:
            id = mux.nodeid
            for fanout_mux_id, _ in mux.fanout:
                '''if fanout_mux_id not in ids_of_muxes:
                    graph[id].append(-1)# -1 means the fanin comes from mux that is not within the current tile
                else:'''
                graph[id].append(fanout_mux_id)
        print 'mux graph: ', graph
        return graph

    def _mux_type_graph(self, distinct_muxes):
        """get mux graph in the form of {mux_type:[driver_mux_type]}"""
        graph = {mux_type: [] for mux_type, _ in distinct_muxes.iteritems()}
        for mux_type, mux_info in distinct_muxes.iteritems():
            for _, fanin_dist in mux_info:
                for key in fanin_dist.keys():
                    if key not in graph[mux_type]:
                        graph[mux_type].append(key)
        del graph['OPIN']
        print graph
        return graph

    def _all_routing_paths(self, graph, source, sink, path=[]):
        """find all paths between source and sink in the form of [(distint_mux, num of load)]"""
        paths = []

        # find the muxes belonging the sink type
        sink_muxes = []
        for mux_id in [mux.nodeid for mux in self.muxes]:
            if sink == self._mux_id_to_profile(mux_id).type:
                sink_muxes.append(mux_id)

        # figure out the different mux types included in the sink type and load of each mux
        sink_muxes_type = []
        mux_type_load_average = {}
        mux_type_cnt = {}
        for mux_id in sink_muxes:
            mux_type = self._mux_id_to_profile(mux_id).mux_info()
            if mux_type not in sink_muxes_type:
                sink_muxes_type.append(mux_type)
                mux_type_load_average[sink_muxes_type.index(mux_type)] = 0
                mux_type_cnt[sink_muxes_type.index(mux_type)] = 0
            mux_type_load_average[sink_muxes_type.index(mux_type)] = mux_type_load_average[
                                                                         sink_muxes_type.index(mux_type)] + len(
                self._mux_id_to_profile(mux_id).fanout) - 1
            mux_type_cnt[sink_muxes_type.index(mux_type)] = mux_type_cnt[sink_muxes_type.index(mux_type)] + 1
        for i in mux_type_load_average.keys():
            mux_type_load_average[i] = mux_type_load_average[i] / mux_type_cnt[i]

        temp_sink_muxes_type = list(sink_muxes_type)
        for sink_mux in sink_muxes:
            sink_mux_type = self._mux_id_to_profile((sink_mux)).mux_info()
            if sink_mux_type in temp_sink_muxes_type:
                temp_sink_muxes_type.remove(sink_mux_type)
                for src_mux in graph[sink_mux]:
                    src_mux_type = self

    def all_routing_paths(self):
        """get all paths within one tile, path in the form of list of (MuxProfile, num of load)"""
        distinct_muxes = self.distinct_muxes()

        # get OPIN and IPIN nodes
        starts = []
        ends = []
        for mux in self.muxes:
            if mux.type == 'OPIN':
                starts.append(mux)
            elif mux.type == 'IPIN':
                ends.append(mux)

        # DFS find all paths
        def find_all_paths(graph, start, ends, path=[], recur_depth=0, max_recur_depth=RECUR_DEPTH):
            recur_depth = recur_depth + 1
            if recur_depth > max_recur_depth:
                return []
            else:
                path = path + [start]
                if start in ends:
                    return [path]

                paths = []
                load_muxes = graph.get(start, [])
                if load_muxes != []:
                    for muxid in load_muxes:
                        if not muxid in self.muxes_id:  # if driving node at other coordinates, store and end finding
                            return [path]
                        else:
                            if muxid not in path:
                                new_paths = find_all_paths(graph, muxid, ends, path, recur_depth, max_recur_depth)
                                for new_path in new_paths:
                                    paths.append(new_path)
                    return paths
                else:
                    return [path]

        # get mux graph, call find_all_paths
        all_paths = []
        mux_graph = self._mux_graph()
        start_t = time.time()
        for start in starts:
            all_paths = all_paths + find_all_paths(mux_graph, start.nodeid, [mux.nodeid for mux in ends])
        # for those not occuring on the above paths, independent mux should be traversed
        independent_muxes = []
        path_muxes = list(set([muxid for path in all_paths for muxid in path]))
        for muxid in self.muxes_id:
            if not muxid in path_muxes:
                independent_muxes.append(muxid)
        for muxid in independent_muxes:
            all_paths = all_paths + find_all_paths(mux_graph, muxid, [mux.nodeid for mux in ends], [], 0, 3)
        print 'independent muxes', independent_muxes
        end_t = time.time()
        print 'finding all paths costs time: %s seconds' % (end_t - start_t)

        transformed_paths = []
        for path in all_paths:
            print path
            transformed_path = []
            for muxid in path:
                if muxid in self.muxes_id:
                    transformed_path.append(self.mux_type_by_id[muxid])
                else:
                    transformed_path.append(muxid)
            transformed_paths.append(transformed_path)
            print transformed_path
        rep_paths = []
        rep_tans_paths = []
        temp_rep_paths = {}
        distinct_paths = []
        for i in range(len(transformed_paths)):
            if transformed_paths[i] not in rep_tans_paths:
                rep_tans_paths.append(transformed_paths[i])
                print transformed_paths[i]
            # print all_paths[i], transformed_paths[i]
        for i in range(len(all_paths)):
            index = rep_tans_paths.index(transformed_paths[i])

        # transform all_paths from nodeid into mux_type and extract representative infomation

class MuxProfile:
    """describe the mux, including mux_size, mux fanin distribution and load"""

    def __init__(self, node, type, fanin, fanout):
        self.nodeid = node
        self.type = type
        self.fanin = fanin  # [(nodeid, type)]
        self.mux_size = len(fanin)
        self.fanout = fanout  # [(nodeid, type)]
        self.fanin_organized = {type: 0 for _, type in self.fanin}
        self.fanout_organized = {type: 0 for _, type in self.fanout}
        for _, type in self.fanin:
            self.fanin_organized[type] = self.fanin_organized[type] + 1
        for _, type in self.fanout:
            self.fanout_organized[type] = self.fanout_organized[type] + 1

    def mux_info(self):
        """return (mux_type, mux_size, mux_fanin_organized), mux_fanin_organized in form of {type:num}"""
        fanin_organized = {type: 0 for _, type in self.fanin}
        fanout_organized = {type: 0 for _, type in self.fanout}
        for _, type in self.fanin:
            fanin_organized[type] = fanin_organized[type] + 1
        for _, type in self.fanout:
            fanout_organized[type] = fanout_organized[type] + 1
        return (self.type, self.mux_size, fanin_organized)

# todo: the input is a list of nodeid
def node_to_mux_profile(nodeid_list, rrg_file_path):
    """given a node, reture the mux profile including mux size, mux type, and mux fanin"""
    segment_id = None
    fanin_nodeid = {}
    fanin_nodetype = []
    fanout_nodeid = {}

    temp_nodeid = list(nodeid_list)
    temp_segment_id = {}
    for event, elem in ET.iterparse(rrg_file_path):
        if elem.tag in ['node', 'segment', 'edge']:
            if elem.tag == 'node':
                nodeid = int(elem.get('id'))
                if nodeid in temp_nodeid:
                    temp_nodeid.remove(nodeid)
                    if elem.find('segment') != None:
                        temp_segment_id[nodeid] = int(elem.find("./segment[@segment_id]").get('segment_id'))
                    else:
                        print 'only nodes with segment_id can be represented with mux!'
                        exit(-1)
                else:
                    elem.clear()
            elif elem.tag == 'edge':
                sink_nodeid = int(elem.get('sink_node'))
                src_nodeid = int(elem.get('src_node'))
                if sink_nodeid in nodeid_list:
                    fanin_nodeid[sink_nodeid].append(src_nodeid)
                    elem.clear()
                elif src_nodeid in nodeid_list:
                    fanout_nodeid[src_nodeid].append(sink_nodeid)
                    elem.clear()
                else:
                    elem.clear()
        else:
            elem.clear()

    for event, elem in ET.iterparse(rrg_file_path):
        if elem.tag in ['node', 'segment']:
            if elem.tag == 'node' and int(elem.get('id')) in fanin_nodeid.keys():
                if elem.find('segment') != None:
                    fanin_nodetype[int(elem.get('id'))].append(
                        int(elem.find("./segment[@segment_id]").get('segment_id')))
                else:
                    assert 'OPIN' == elem.get('type')
                    fanin_nodetype.append('OPIN')
                elem.clear()
        else:
            elem.clear()

    print {'mux_size': len(fanin_nodeid), 'type': segment_id, 'mux_fanin': zip(fanin_nodeid, fanin_nodetype)}
    return {'mux_size': len(fanin_nodeid), 'type': segment_id, 'mux_fanin': zip(fanin_nodeid, fanin_nodetype)}


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
        return hash((self.mux_size, self.mux_type, tuple(sorted(self.mux_fanin_type))))

    def print_mux_info(self):
        print 'mux_type: ', self.mux_type, '; mux_size: ', self.mux_size, '; mux_fanin_type: ', self.mux_fanin_type

class SegmentProfile:
    """this class contain a wire info, with load and driving mux info"""
    seg_len_dict = {}
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
        load_mux_loc = []
        driver_mux_loc = self.driver_mux.coordinate
        for load_mux in self.fanout_mux:
            if self.wire_length == 0:
                dis = 0
            else:
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
            load_mux_loc.append(dis)
        return load_mux_loc

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
            fanout_mux_key.append((mux.mux_type, mux.mux_size, tuple(sorted(mux.mux_fanin_type))))
        fanout_mux_key.sort()
        return hash((self.segment_id, self.driver_mux.__hash__(), tuple(fanout_mux_key)))

    def print_seg_info(self):
        print '****************************************************************'
        print 'segment length: ', self.wire_length
        print 'driver mux: ',
        self.driver_mux.print_mux_info()
        print 'load muxes: ', len(self.fanout_mux)
        for load_mux in self.fanout_mux:
            load_mux.print_mux_info()

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

def _get_certain_tile_node(node_ctx, center_coordinate):
    """judge the node_ctx whether belongs to a center tile"""
    # get node_ctx coordinate info
    xlow = int(node_ctx.find('loc').get('xlow'))
    ylow = int(node_ctx.find('loc').get('ylow'))
    xhigh = int(node_ctx.find('loc').get('xhigh'))
    yhigh = int(node_ctx.find('loc').get('yhigh'))

    # get all nodes with its driver mux implemented at center_coordinate tile
    if node_ctx.get('type') != 'SOURCE' and node_ctx.get('type') != 'SINK':
        id = int(node_ctx.get('id'))
        type = node_ctx.get('type')
        if center_coordinate[0] == xhigh and center_coordinate[
            1] == yhigh:  # handle nodes with up-right end at center_coordinate
            if node_ctx.find('segment') != None:  # handle segments
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                # todo: nodes with segment_id 789 have mux implemented at center_coordinate, nodes with no segment_id 789 have mux implemented\
                #         at center_coordinate only when the direction is DEC. This is particular in Qian's rrg assignation, need to be generalized among all rrg
                if segment_id in [7, 8, 9] or node_ctx.get('direction') == 'DEC_DIR':
                    return NodeProfile(id, type, segment_id)
            else:  # handle OPIN and IPIN
                return NodeProfile(id, type, None)
        elif center_coordinate[0] == xlow and center_coordinate[1] + 1 == ylow:
            if node_ctx.find('segment') != None:
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                if segment_id not in [7, 8, 9] and node_ctx.get('direction') == 'INC_DIR' and node_ctx.get(
                        'type') == 'CHANY':
                    return NodeProfile(id, type, segment_id)
        elif center_coordinate[0] + 1 == xlow and center_coordinate[1] == ylow:
            if node_ctx.find('segment') != None:
                segment_id = int(node_ctx.find('segment').get('segment_id'))
                if segment_id not in [7, 8, 9] and node_ctx.get('direction') == 'INC_DIR' and node_ctx.get(
                        'type') == 'CHANX':
                    return NodeProfile(id, type, segment_id)
        return -1
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

def parse_rrg(rrg_file_path, segment_length):
    """path rrg_file and get routing path fragments"""

    start_t = time.time()

    tree = ET.parse(rrg_file_path)
    root = tree.getroot()


    # get coordinates
    index_x = 0
    index_y = 0
    for x in root.iter('x_list'):
        index_x = max(index_x, int(x.attrib['index']))
    for y in root.iter('y_list'):
        index_y = max(index_y, int(y.attrib['index']))
    coordinate = (index_x, index_y)
    center_coordiante = (coordinate[0] / 2, coordinate[1] / 2)

    # get segments
    segments = {}
    seg_name_by_id = {}
    for segment in root.find('segments'):
        seg_name_by_id[int(segment.attrib['id'])] = segment.attrib['name']
    for key in seg_name_by_id.iterkeys():
        segment_name = seg_name_by_id[key]
        segments[key] = segment_length[segment_name]
    SegmentProfile.seg_len_dict = segments

    # get swtiches
    switches = {}
    for switch in root.find('switches'):
        switches[int(switch.attrib['id'])] = switch.attrib['name']

    #traverse the rr_nodes tag and get representing nodes for one tile and CHANX\CHANY
    tile_nodes = set()
    seg_nodes = set()
    for node in root.find('rr_nodes'):
        # get all nodes with its driver mux implemented at center_coordinate tile
        tile_node = _get_certain_tile_node(node, center_coordiante)
        if tile_node != -1:
            tile_nodes.add(tile_node)

        # get connection strategy of each wire segment
        node_profile = _get_certain_node_with_segment(node, center_coordiante, segments)
        if node_profile != -1:
            seg_nodes.add(node_profile)

    # re-organize nodes by segment id or type
    nodes_by_type = {node.segment_id if node.segment_id != None else node.type: [] for node in tile_nodes}
    for node in tile_nodes:
        if node.segment_id != None:
            nodes_by_type[node.segment_id].append(node)
        else:
            nodes_by_type[node.type].append(node)

    mux_fanin_by_node = {node.id: [] for node in tile_nodes}
    mux_fanout_by_node = {node.id: [] for node in tile_nodes}
    type_by_nodeid = {node.id: type for type, nodes in nodes_by_type.iteritems() for node in nodes}

    #dict to store fanin and fanout
    seg_fanin_id_dict = {node.id:set() for node in seg_nodes}
    seg_fanout_id_dict = {node.id:set() for node in seg_nodes}

    #traverse rr_edges tag and get fanin and fanout info of each node
    for edge in root.find('rr_edges'):
        src_node = int(edge.get('src_node'))
        sink_node = int(edge.get('sink_node'))

        #get fanin nodes for each segment node
        if sink_node in seg_fanin_id_dict.keys():
            seg_fanin_id_dict[sink_node].add(src_node)

        # get fanout nodes for each segment node
        if src_node in seg_fanout_id_dict.keys():
            seg_fanout_id_dict[src_node].add(sink_node)

        '''# get fanin nodes for each node
        if sink_node in mux_fanin_by_node.keys():
            type = None
            if src_node in type_by_nodeid.keys():
                type = type_by_nodeid[src_node]
            else:
                src_node_elem = root.find("./rr_nodes/node[@id='%d']" % src_node)
                if src_node_elem == None:
                    exit(-1)
                elif src_node_elem.find("./segment[@segment_id]") == None:
                    type = src_node_elem.get('type')
                else:
                    type = int(src_node_elem.find("./segment[@segment_id]").get('segment_id'))
            mux_fanin_by_node[sink_node].append((src_node, type))
        # get fanout nodes for each node
        if src_node in mux_fanout_by_node.keys():
            type = None
            if sink_node in type_by_nodeid.keys():
                type = type_by_nodeid[sink_node]
            else:
                sink_node_elem = root.find("./rr_nodes/node[@id='%d']" % sink_node)
                if sink_node_elem == None:
                    exit(-1)
                elif sink_node_elem.find("./segment[@segment_id]") == None:
                    type = sink_node_elem.get('type')
                else:
                    type = int(sink_node_elem.find("./segment[@segment_id]").get('segment_id'))
            mux_fanout_by_node[src_node].append((sink_node, type))
        '''

    #according fanin and fanout node id, get its associated segment id, if the fanin node doesnt have a segment id, it must be OPIN
    seg_fanin_id_set = set([fanin for fanins in seg_fanin_id_dict.values() for fanin in fanins])
    seg_fanin_nodes_dict = {node_id:None for node_id in seg_fanin_id_set}
    seg_fanout_id_set = set([fanout for fanouts in seg_fanout_id_dict.values() for fanout in fanouts])
    seg_fanout_nodes_dict = {node_id:None for node_id in seg_fanout_id_set}
    for node in root.find('rr_nodes'):
        node_id = int(node.get('id'))
        if node_id in seg_fanin_id_set:
            coordinate = _get_node_coordinate(node)
            node_type = node.get('type')
            node_seg_id = -1 # OPIN etc type node doesnt have segment_id tag
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'OPIN'
            seg_fanin_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id, coordinate)
        if node_id in seg_fanout_id_set:
            coordinate = _get_node_coordinate(node)
            node_type = node.get('type')
            node_seg_id = -1
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'IPIN'
            seg_fanout_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id, coordinate)

    #after knowing fanout, need to figure out the mux info between current wire segment and its load wire segment
    load_seg_fanin_id_dict = {node_id:set() for node_id in seg_fanout_id_set}
    for edge in root.find('rr_edges'):
        src_node = int(edge.get('src_node'))
        sink_node = int(edge.get('sink_node'))
        if sink_node in seg_fanout_id_set:
            load_seg_fanin_id_dict[sink_node].add(src_node)
    load_seg_fanin_id_set = set([fanin for fanins in load_seg_fanin_id_dict.values() for fanin in fanins])
    load_seg_fanin_nodes_dict = {node_id:None for node_id in load_seg_fanin_id_set}
    for node in root.find('rr_nodes'):
        node_id = int(node.get('id'))
        if node_id in load_seg_fanin_id_set:
            node_type = node.get('type')
            node_seg_id = -1
            if node_type == 'CHANX' or node_type == 'CHANY':
                node_seg_id = int(node.find("./segment[@segment_id]").get('segment_id'))
            else:
                assert node_type == 'OPIN'
            load_seg_fanin_nodes_dict[node_id] = NodeProfile(node_id, node_type, node_seg_id)

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
            load_muxes.append(MuxInfo(load_mux_size, load_mux_fanin_seg_ids, load_mux_type, load_mux_coord))

        #fill a segmentprofile
        seg_profile = SegmentProfile(seg_node.segment_id, segments[seg_node.segment_id], seg_name_by_id[seg_node.segment_id])
        seg_profile.add_driver_mux(driver_mux)
        for load_mux in load_muxes:
            seg_profile.add_load_mux(load_mux)
        if seg_profile.driver_mux.mux_size != 0:
            seg_profiles.add(seg_profile)

    #organize segmentprofile by segment_id
    print len(seg_profiles)
    organized_seg_profiles = {segment_id: [] for segment_id in segments.keys()}
    for seg_profile in seg_profiles:
        organized_seg_profiles[seg_profile.segment_id].append(seg_profile)
    for key, value in organized_seg_profiles.iteritems():
        for seg in organized_seg_profiles[key]:
            print seg.get_seg_distinct_profile()

    #exlude redundent segment
    distinct_seg_profiles = []
    temp_distinct_tag = []
    for seg in seg_profiles:
        seg_distinct_info = seg.get_seg_distinct_profile()
        if not seg_distinct_info in temp_distinct_tag:
            temp_distinct_tag.append(seg_distinct_info)
            distinct_seg_profiles.append(seg)

    print len(seg_profiles), len(distinct_seg_profiles)
    end_t = time.time()
    print 'reading rrg file costs time: %s seconds' % (end_t - start_t)
    '''
    # generate a list of MuxProfile
    muxes_profile = []
    assert len(mux_fanin_by_node) == len(mux_fanout_by_node)
    for nodeid in mux_fanin_by_node.keys():
        # if type_by_nodeid[nodeid] not in ['OPIN', 'IPIN']:
        muxes_profile.append(
            MuxProfile(nodeid, type_by_nodeid[nodeid], mux_fanin_by_node[nodeid], mux_fanout_by_node[nodeid]))
    # muxes_profile = [mux for mux in muxes_profile if mux.mux_size != 0]

    routing_path_profile = RoutingPathProfile(muxes_profile)
    routing_path_profile.all_routing_paths()
    '''
    # print 'mux_fanin_by_node', mux_fanin_by_node
    # print 'mux_fanout_by_node', mux_fanout_by_node
    # print len(mux_fanout_by_node), len(muxes_profile)
    # print 'num of distinct muxes: %d'%len(distinct_mux), 'details: ', distinct_mux

    return 0


if __name__ == '__main__':
    segment_info = {'l1':1, 'l2':2, 'l3':3, 'l4':4, 'l5':5, 'l8':8, 'l12':12, 'imux_medium':0, 'omux_medium':0, 'gsb_medium':0}
    parse_rrg('/home/syh/projects/openfpga_gsb/rr.graph', segment_info)
    # parse_rrg('/home/syh/projects/openfpga_gsb/25*25')
    # node_to_mux_profile(183362, '/home/syh/projects/openfpga_gsb/29*29')
