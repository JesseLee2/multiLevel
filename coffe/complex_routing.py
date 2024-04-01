import math
import os
import sys
import shutil
from collections import Counter

import parse_rrg
import basic_subcircuits
import mux_subcircuits
import top_spice_writer as tsw
import utils


class _Specs:
    """process parameters and routing resources parameters"""
    def __init__(self, arch_params_dict):
        #process parameters
        self.transistor_type = arch_params_dict['transistor_type']
        self.vdd = arch_params_dict['vdd']
        self.vsram = arch_params_dict['vsram']
        self.vsram_n = arch_params_dict['vsram_n']
        self.gate_length = arch_params_dict['gate_length']
        self.min_tran_width = arch_params_dict['min_tran_width']
        self.min_width_tran_area = arch_params_dict['min_width_tran_area']
        self.sram_cell_area = arch_params_dict['sram_cell_area']
        self.trans_diffusion_length = arch_params_dict['trans_diffusion_length']
        self.metal_stack = arch_params_dict['metal']
        self.model_path = arch_params_dict['model_path']
        self.model_library = arch_params_dict['model_library']
        self.rest_length_factor = arch_params_dict['rest_length_factor']
        self.use_tgate = arch_params_dict['use_tgate']
        #routing resources parameters
        self.segment_length_by_name = arch_params_dict['segment_length_by_name']

class MuxInfo:
    def __init__(self, mux_type, mux_size, mux_coordinate, num_per_tile):
        self.mux_type = mux_type
        self.mux_size = mux_size
        self.mux_coordinate = mux_coordinate
        self.num_per_tile = num_per_tile

class _RoutingMux:
    def __init__(self, mux_info):
        self.required_size = mux_info.mux_size
        self.name = mux_info.name
        self.coordinate = mux_info.coordinate
        self.level1_size = -1
        self.level2_size = -1
        self.implemented_size = -1
        self.sram_per_mux = -1
        self.num_per_tile = mux_info.num_per_tile
        self.initial_transistor_sizes = {}
        self.weight = mux_info.weight
        #this is the seg_profile(s) that has(have) the this mux as the driver mux
        self.associated_segs = []

    def generate(self, file_name, log):
        """generate mux spice circuit"""
        log.info("Adding " + str(self.name) + " in " + str(file_name))
        self.level2_size = int(math.sqrt(self.required_size))
        self.level1_size = int(math.ceil(float(self.required_size) / self.level2_size))
        self.implemented_size = self.level1_size * self.level2_size
        self.sram_per_mux = self.level1_size + self.level2_size
        if self.implemented_size == 2:
            self.transistor_names, self.wire_names = mux_subcircuits.generate_ptran_2_to_1_mux(file_name, self.name)
            self.initial_transistor_sizes["ptran_" + self.name + "_nmos"] = 3
            self.initial_transistor_sizes["rest_" + self.name + "_pmos"] = 1
            self.initial_transistor_sizes["inv_" + self.name + "_1_nmos"] = 3
            self.initial_transistor_sizes["inv_" + self.name + "_1_pmos"] = 6
            self.initial_transistor_sizes["inv_" + self.name + "_2_nmos"] = 6
            self.initial_transistor_sizes["inv_" + self.name + "_2_pmos"] = 12
        else:
            self.transistor_names, self.wire_names = mux_subcircuits.generate_ptran_2lvl_mux(file_name, self.name, self.implemented_size, self.level1_size, self.level2_size)
            self.initial_transistor_sizes["ptran_" + self.name + "_L1_nmos"] = 3
            self.initial_transistor_sizes["ptran_" + self.name + "_L2_nmos"] = 3
            self.initial_transistor_sizes["rest_" + self.name + "_pmos"] = 1
            self.initial_transistor_sizes["inv_" + self.name + "_1_nmos"] = 3
            self.initial_transistor_sizes["inv_" + self.name + "_1_pmos"] = 6
            self.initial_transistor_sizes["inv_" + self.name + "_2_nmos"] = 6
            self.initial_transistor_sizes["inv_" + self.name + "_2_pmos"] = 12

        return self.initial_transistor_sizes

    def update_area(self, area_dict, width_dict):
        """after changing sizes of transistors, more corse block mux area need to be re-calculated, width is related to area"""
        if self.implemented_size != 2:
            area = ((self.level1_size * self.level2_size) * area_dict["ptran_" + self.name + "_L1"] +
                    self.level2_size * area_dict["ptran_" + self.name + "_L2"] +
                    area_dict["rest_" + self.name + ""] +
                    area_dict["inv_" + self.name + "_1"] +
                    area_dict["inv_" + self.name + "_2"])
            area_with_sram = area + (self.level1_size + self.level2_size)*area_dict["sram"]
            # vpr arch file 'tag switchlist' related parameters
            area_dict[self.name + "_trans_size"] = area_dict["ptran_" + self.name + "_L1"]
            area_dict[self.name + "_buf_size"] = area_dict["rest_" + self.name + ""] + area_dict["inv_" + self.name + "_1"] + area_dict["inv_" + self.name + "_2"]
        else:
            area = (2 * area_dict["ptran_" + self.name]) + area_dict["rest_" + self.name] + area_dict["inv_" + self.name + "_1"] + area_dict["inv_" + self.name + "_2"]
            area_with_sram = area + area_dict["sram"]
            # vpr arch file 'tag switchlist' related parameters
            area_dict[self.name + "_trans_size"] = area_dict["ptran_" + self.name]
            area_dict[self.name + "_buf_size"] = area_dict["rest_" + self.name + ""] + area_dict["inv_" + self.name + "_1"] + area_dict["inv_" + self.name + "_2"]

        width = math.sqrt(area)
        width_with_sram = math.sqrt(area_with_sram)
        area_dict[self.name] = area
        width_dict[self.name] = width
        area_dict[self.name + "_sram"] = area_with_sram
        width_dict[self.name + "_sram"] = width_with_sram



    def update_wires(self, width_dict, wire_lengths_dict, ratio):
        """width --> length --> length RC pi model"""
        if self.implemented_size != 2:
            wire_lengths_dict["wire_" + self.name + "_driver"] = (width_dict["inv_" + self.name + "_1"] + width_dict["inv_" + self.name + "_2"])/4
            wire_lengths_dict["wire_" + self.name + "_L1"] = width_dict[self.name] * ratio
            wire_lengths_dict["wire_" + self.name + "_L2"] = width_dict[self.name] * ratio
        else:
            wire_lengths_dict["wire_" + self.name + "_driver"] = (width_dict["inv_" + self.name + "_1"] + width_dict["inv_" + self.name + "_2"])/4
            wire_lengths_dict["wire_" + self.name] = width_dict[self.name] * ratio

    def print_implemention_details(self, log):
        log.info(self.name +  " DETAILS:")
        log.info("Style: two-level MUX")
        log.info("Required MUX size: " + str(self.required_size) + ":1")
        log.info("Implemented MUX size: " + str(self.implemented_size) + ":1")
        log.info("Level 1 size = " + str(self.level1_size))
        log.info("Level 2 size = " + str(self.level2_size))
        log.info("Number of unused inputs = " + str(self.num_unused_inputs))
        log.info("Number of MUXes per tile: " + str(self.num_per_tile))
        log.info("Number of SRAM cells per MUX: " + str(self.sram_per_mux))

class ComplexRouting():

    def __init__(self, seg_profiles, tile_muxes, arch_parameters, log):

        self.log = log
        self.specs = _Specs(arch_parameters)

        self.wire_RC_filename = "wire_RC.l"
        self.process_data_filename = "process_data.l"
        self.includes_filename = "includes.l"
        self.basic_subcircuits_filename = "basic_subcircuits.l"
        self.subcircuits_filename = "subcircuits.l"
        self.sweep_data_filename = "sweep_data.l"

        self.seg_profiles = seg_profiles
        self.tile_muxes = tile_muxes

        #get all distinct muxes that together form all the segment profiles, which have different (type, size)
        distinct_muxes = self._get_distinct_muxes(seg_profiles)

        #look up tile_muxes to add up all the muxes of a typical tile
        num_tile_muxes = sum(tile_muxes.values())
        #instantiate class object _RoutingMux, and store them to namespace of current class in order to use mux with it naming convention
        self.muxes = {}
        for mux in distinct_muxes:
            #assign some attribute that _RoutingMux requires mux to have
            num_per_tile = tile_muxes.get((mux.mux_type, mux.mux_size), -1)
            if num_per_tile == -1:
                self.log.warning("num_per_tile attribute not found on segment mux {}! assigned to -1".format(
                    (mux.mux_type, mux.mux_size)))
                mux.num_per_tile = -1
                mux.weight = 0
            else:
                mux.num_per_tile = num_per_tile
                mux.weight = float(num_per_tile) / num_tile_muxes
            
            #from mux to instinctiate the _RoutingMux object
            mux.name = utils.segid_to_name(mux.mux_type, parse_rrg.SegmentProfile.seg_name_dict) + '_size_' + str(mux.mux_size) + '_mux'
            self.muxes[mux.name] = _RoutingMux(mux)
        #add a special mux to drive 'OPIN'
        self._manually_add_mux("opin_size_2_mux", 2, -1, 0)
        

        self.transistor_sizes = {}
        self.transistor_area_list = {}
        self.area_dict = {}
        self.width_dict = {}
        self.wire_lengths_dict = {}
        self.wire_rc_dict = {}
        self.wire_delay_dict = {}
        self.delay_dict = {}

    def _manually_add_mux(self, name, size, num_per_tile, weight):
        """manually add some mux such as 2:1 mux to driver 'OPIN'"""
        manual_mux = parse_rrg.MuxInfo(size, [], name, -1)
        manual_mux.num_per_tile = num_per_tile
        manual_mux.weight = weight
        manual_mux.name = name
        # watch out: str 'opin_size_2_mux' cant be reused!!!
        self.muxes[name] = _RoutingMux(manual_mux)
    
    def generate(self, arch_folder):

        os.chdir(arch_folder)

        self.log.info("\n##############################################")
        self.log.info("Generating files which are needed to perform Hspice simulation")

        #generate basic circuits, such as pass-transistor, inverter, level-restorer, wire, elc
        self._generate_basic_subcircuits(self.log)

        #generate mux subcuits according to self.muxes, it generates all the muxes of different (type, size), later used to generate top spice file
        self._create_lib_files(self.log)
        for mux in self.muxes.values():
            self.transistor_sizes.update(mux.generate(self.subcircuits_filename, self.log))
        self._end_lib_files()

        #process data defines .PARAM variable to be used in spice file, the device spice model path, and voltage source.
        self._generate_process_data(self.log)

        #wrap process data, subcircuits, basic subcircuits together to form a all-in-one library, only called by top spice file
        self._generate_includes(self.log)

        #generate segment top spice file
        ######################################
        #create sub directory sp_file

        if not os.path.exists(os.path.join(arch_folder, "top_sp_files")):
            top_spice_dir = os.path.join(arch_folder, "top_sp_files")
            os.makedirs(top_spice_dir)

        #re-organize seg_profiles into dict form, to facilitate look up all segment belonging to one type
        seg_profile_by_type = {}
        for seg in self.seg_profiles:
            if not seg.segment_id in seg_profile_by_type.keys():
                seg_profile_by_type[seg.segment_id] = []
                seg_profile_by_type[seg.segment_id].append(seg)
            else:
                seg_profile_by_type[seg.segment_id].append(seg)

        #for every segment, generate a top spice file
        sp_file_naming = []
        distinct_seg_tag = []
        for seg in self.seg_profiles:
            #exclude seg that is redundent in terms of driver mux size, load mux size and loc
            seg_tag = seg.get_seg_distinct_profile()
            if seg_tag in distinct_seg_tag:
                continue
            else:
                distinct_seg_tag.append(seg_tag)

                #give unique top spice name for seg
                top_name = seg.seg_name + '_size_' + str(seg.get_seg_driver_mux_size()) + '_mux'
                spice_name = top_name + "_top_" + str(sp_file_naming.count(top_name)) + '.sp'
                sp_file_naming.append(top_name)

                # add the seg to associated _RoutingMux object
                self.muxes[top_name].associated_segs.append(seg)

                #create dir for each top spice file
                sp_dir = os.path.join(top_spice_dir, spice_name.rstrip(".sp"))
                if not os.path.exists(sp_dir):
                    os.makedirs(sp_dir)
                os.chdir(sp_dir)

                #spice file title, include library INCLUDE
                tsw.write_spice_file_header(spice_name, top_name)

                #input signal, simulate option
                tsw.write_spice_setup_and_input(spice_name)

                #choose a fanin segment of the current segment
                fanin_seg_ids = seg.driver_mux.mux_fanin_type
                sel_fanin_seg = None
                fanin_seg_ids = sorted(Counter(fanin_seg_ids).items(), key= lambda kv : kv[1])
                for i in range(2):
                    for seg_id, _ in fanin_seg_ids:
                        if sel_fanin_seg is None:
                            for default_fanin_seg in seg_profile_by_type.get(seg_id, []):
                                if sel_fanin_seg is None:
                                    for fanin_seg_fanout_mux in default_fanin_seg.fanout_mux:
                                        if i == 0:
                                            if fanin_seg_fanout_mux.mux_type == seg.segment_id and fanin_seg_fanout_mux.mux_size == seg.get_seg_driver_mux_size() and default_fanin_seg.get_seg_driver_mux_size() > 1:
                                                sel_fanin_seg = default_fanin_seg
                                                break
                                        else:
                                            if fanin_seg_fanout_mux.mux_size == seg.get_seg_driver_mux_size() and default_fanin_seg.get_seg_driver_mux_size() > 1:
                                                sel_fanin_seg = default_fanin_seg
                                                break
                                else:
                                    break
                        else:
                            break
                    if sel_fanin_seg:
                        break

                #generate the circuits in the form:
                #       |~~  |\    |   |  |\    |    |   |\    |~~
                #     __|    | |----------| |------------| | __|
                #            |/    |   |  |/    |    |   |/
                #               default_fanin_seg,   current_seg
                if sel_fanin_seg is None:
                    #there are segments whose fanin is all 'OPIN', i assume a 2:1 MUX driving 'OPIN
                    self.log.info("there is segment whose fanin is all 'OPIN', i assume a 2:1 MUX driving 'OPIN'!")
                    seg.print_seg_info(self.log)
                    mux_delay_meas_points, inv_delay_meas_points, segment_delay_meas_points, mux_instances_within_seg_profile = tsw.write_spice_circuit(spice_name, parse_rrg.SegmentProfile.seg_name_dict, seg, None)
                else:
                    mux_delay_meas_points, inv_delay_meas_points, segment_delay_meas_points, mux_instances_within_seg_profile = tsw.write_spice_circuit(spice_name, parse_rrg.SegmentProfile.seg_name_dict, seg, sel_fanin_seg)

                #generate measurement
                tsw.write_spice_measurement(spice_name, seg, parse_rrg.SegmentProfile.seg_name_dict, mux_delay_meas_points, inv_delay_meas_points, segment_delay_meas_points)

                #add attribute 'mux_instances' to seg, which contains all routing muxes exemplified as driver mux or load muxes of the seg
                seg.mux_instances = mux_instances_within_seg_profile

                #add attribute top_spice_path to seg, by checking the existence of this attribute i can know whether this segment profile has been generated
                seg.top_spice_path = os.path.join(sp_dir, spice_name)
                print(seg.top_spice_path)
                print(seg.seg_name)
                
            os.chdir('../../../')

        self.log.info("Generating top spice file completed!")
        os.chdir(arch_folder)

        #sum up all area of routing muxes for the first time
        self.update_area()
        #according to area, calculate wire length, espically for intra_tile_wire
        self.update_wires()
        #according to wire length, assign RC value for each wire
        self.update_wire_rc()

    def get_mux(self, mux_name):
        """get _RoutingMux object named mux_name"""
        if self.muxes.get(mux_name, None) is None:
            self.log.error("get mux \"%s\" failed!" % mux_name)
        else:
            return self.muxes[mux_name]

    def get_top_spice_file_path_for_all_seg(self):
        """return a list containing all top spice file path for simulating all segment profiles"""
        top_spice_path_list = []
        for seg in self.seg_profiles:
            if not hasattr(seg, "top_spice_path"):
                continue
            else:
                top_spice_path_list.append(seg.top_spice_path)
        return top_spice_path_list

    def _get_distinct_muxes(self, seg_profiles):
        distinct_muxes = []
        distinct_muxes_tag = []
        for seg in seg_profiles:
            seg_muxes = []
            seg_muxes.append(seg.driver_mux)
            seg_muxes.extend(seg.fanout_mux)
            for mux in seg_muxes:
                if not (mux.mux_type, mux.mux_size) in distinct_muxes_tag:
                    distinct_muxes_tag.append((mux.mux_type, mux.mux_size))
                    distinct_muxes.append(mux)
        return distinct_muxes

    def update_area(self):
        """send self.area_dict to each routing mux, then routing mux itself will update its own area.
        after knowing areas of all the routing mux, total tile routing mux area is clear by doing summation"""
        #get area values for each transistors
        self._update_area_for_transistor()

        #get area values for each basic subcircuits
        self._update_area_for_components_in_mux()

        #Calculate area for sram area
        self.area_dict['sram'] = self.specs.sram_cell_area * self.specs.min_width_tran_area

        #Calculate area for each routing mux
        for mux in self.muxes.values():
            #calculate area only for tile muxes, the num_pre_tile attribute of segment related mux is already assigned to none -1
            mux.update_area(self.area_dict, self.width_dict)

        #calculate total area for routing area of a tile, suming up all routing mux area
        total_routing_area = 0
        for mux in self.muxes.values():
            #total area only including tile muxes
            if mux.num_per_tile != -1:
                mux_name = mux.name
                mux_name_sram = mux_name + "_sram"
                mux_name_total = mux_name + "_total"
                self.area_dict[mux_name_total] = mux.num_per_tile * self.area_dict[mux_name_sram]
                total_routing_area = total_routing_area + self.area_dict[mux_name_total]
        self.area_dict["total_routing_area"] = total_routing_area
        
    def _update_area_for_transistor(self):
        """ We use self.transistor_sizes to calculate area
            Using the area model, we calculate the transistor area in minimum width transistor areas.
            We also calculate area in nm and transistor width in nm. Nanometer values are needed for wire length calculations.
            For each transistor, this data forms a tuple (tran_name, tran_channel_width_nm, tran_drive_strength, tran_area_min_areas, tran_area_nm, tran_width_nm)
            The FPGAs transistor_area_list is updated once these values are computed."""

        # Initialize transistor area list
        tran_area_list = []

        # For each transistor, calculate area
        for tran_name, tran_size in self.transistor_sizes.items():
            # Get tran channel width area in nm
            tran_channel_width_nm = tran_size * self.specs.min_tran_width
            # Get tran area in min transistor widths
            tran_area = self._area_model(tran_size)
            # Get area in nm square
            tran_area_nm = tran_area * self.specs.min_width_tran_area
            # Get width of transistor in nm
            tran_width = math.sqrt(tran_area_nm)
            # Add this as a tuple to the tran_area_list
            tran_area_list.append((tran_name, tran_channel_width_nm, tran_size, tran_area, tran_area_nm, tran_width))

        self.transistor_area_list = tran_area_list

    def _update_area_for_components_in_mux(self):
        """update area for components in mux circuits such as pass-transistor in level1|level2, invertor, and rest."""
        # Initialize component area list of tuples (component name, component are, component width)
        comp_area_list = []

        # Create a dictionary to store component sizes for multi-transistor components
        comp_dict = {}

        # For each transistor in the transistor_area_list
        # tran is a tuple having the following formate (tran_name, tran_channel_width_nm,
        # tran_drive_strength, tran_area_min_areas, tran_area_nm, tran_width_nm)
        for tran in self.transistor_area_list:
            # those components should have an nmos and a pmos transistors in them
            if "inv_" in tran[0] or "tgate_" in tran[0]:
                # Get the component name; transistors full name example: inv_lut_out_buffer_2_nmos.
                # so the component name after the next two lines will be inv_lut_out_buffe_2.
                comp_name = tran[0].replace("_nmos", "")
                comp_name = comp_name.replace("_pmos", "")

                # If the component is already in the dictionary
                if comp_name in comp_dict:
                    if "_nmos" in tran[0]:
                        # tran[4] is tran_area_nm
                        comp_dict[comp_name]["nmos"] = tran[4]
                    else:
                        comp_dict[comp_name]["pmos"] = tran[4]

                    # At this point we should have both NMOS and PMOS sizes in the dictionary
                    # We can calculate the area of the inverter or tgate by doing the sum
                    comp_area = comp_dict[comp_name]["nmos"] + comp_dict[comp_name]["pmos"]
                    comp_width = math.sqrt(comp_area)
                    comp_area_list.append((comp_name, comp_area, comp_width))
                else:
                    # Create a dict for this component to store nmos and pmos sizes
                    comp_area_dict = {}
                    # Add either the nmos or pmos item
                    if "_nmos" in tran[0]:
                        comp_area_dict["nmos"] = tran[4]
                    else:
                        comp_area_dict["pmos"] = tran[4]

                    # Add this inverter to the inverter dictionary
                    comp_dict[comp_name] = comp_area_dict
            # those components only have one transistor in them
            elif "ptran_" in tran[0] or "rest_" in tran[0] or "tran_" in tran[0]:
                # Get the comp name
                comp_name = tran[0].replace("_nmos", "")
                comp_name = comp_name.replace("_pmos", "")
                # Add this to comp_area_list directly
                comp_area_list.append((comp_name, tran[4], tran[5]))

        # Convert comp_area_list to area_dict and width_dict
        area_dict = {}
        width_dict = {}
        for component in comp_area_list:
            area_dict[component[0]] = component[1]
            width_dict[component[0]] = component[2]

        # Set the FPGA object area and width dict
        self.area_dict = area_dict
        self.width_dict = width_dict

    def update_wires(self):
        """update self.wire_lengths and self.wire_leyers, including wire inside routing mux and wire length of segment """
        #update wires inside routing mux
        #####################################
        for mux in self.muxes.values():
            mux.update_wires(self.width_dict, self.wire_lengths_dict, 1)

        #update wires for wire segments
        ##########################################
        #todo: get value for self.area_dict["tile"], temporarily assign a resonable value in number of min transistor from vpr arch
        self.area_dict["tile"] = 24439.95 * self.specs.min_width_tran_area
        self.width_dict["tile"] = math.sqrt(self.area_dict["tile"])
        self.wire_lengths_dict["tile"] = self.width_dict["tile"]

        #get all distinct wire segments with different name
        wire_seg_names = []
        wire_seg_lengths = []
        for seg_profile in self.seg_profiles:
            if seg_profile.seg_name not in wire_seg_names:
                wire_seg_names.append(seg_profile.seg_name)
                wire_seg_lengths.append(seg_profile.wire_length)
        for i in range(len(wire_seg_names)):
            if wire_seg_lengths[i] == 0:
                #todo: is it reasonable to assign intra wire length with tile length?
                self.wire_lengths_dict[wire_seg_names[i]] = self.width_dict["tile"]
            else:
                self.wire_lengths_dict[wire_seg_names[i]] = self.width_dict["tile"] * wire_seg_lengths[i]

    def update_wire_rc(self):
        """ This function updates self.wire_rc_dict based on the FPGA's self.wire_lengths and self.wire_layers."""
        for wire, length in self.wire_lengths_dict.items():
            #todo: only one metal layer, dont provide option
            rc = self.specs.metal_stack[1]
            res = rc[0] * length
            cap = rc[1] * length / 2
            self.wire_rc_dict[wire] = (res, cap)

    def update_delays(self, hspice_api):
        """Get Hspice delays for each segment profile, returns False if Hspice simulation failed"""
        self.log.info("#####################################################")
        self.log.info("######UPDATING DELAYS################################\n##################################################")

        weighted_routing_path_delay = 0.0
        valid_delay = True
        #prepare parameters expected by hspice simulation, including transistor sizes and wire RC
        ######################################################################
        parameter_dict = {}
        for tran_name, tran_size in self.transistor_sizes.items():
            parameter_dict[tran_name] = [tran_size * 1e-9 * self.specs.min_tran_width]
        for wire_name, rc_data in self.wire_rc_dict.items():
            parameter_dict[wire_name + "_res"] = [rc_data[0]]
            parameter_dict[wire_name + "_cap"] = [rc_data[1] * 1e-15]

        #run hspice for each wire segment profile
        #################################################
        sims_seg_profiles = []
        for seg in self.seg_profiles:
            if hasattr(seg, "top_spice_path"):
                sims_seg_profiles.append(seg)
        spice_meas_list = []
        pool = utils.get_parallel_num(len(sims_seg_profiles))
        for seg in sims_seg_profiles:
            spice_path = seg.top_spice_path
            spice_meas_list.append((pool.apply_async(utils.hspice_task, args=(hspice_api, spice_path, parameter_dict,)), seg))
        pool.close()
        pool.join()
        spice_meas_list = [(i.get(), j) for i, j in spice_meas_list]
        for spice_meas, seg in spice_meas_list:
            tfall_str = spice_meas["meas_total_tfall"][0]
            trise_str = spice_meas["meas_total_trise"][0]
            tfall, trise = utils.valid_delay_results(tfall_str, trise_str, self.log)
            seg.delay = max(tfall, trise)
            seg.tfall = tfall
            seg.trise = trise

        for mux in self.muxes.values():
            #get seg_profiles that have this mux as the driver mux, so these seg_profiles have the same driver mux but different load muxes
            segs_with_the_same_driver_mux = mux.associated_segs
            tfall_avg, trise_avg = 0.0, 0.0
            if segs_with_the_same_driver_mux:
                for seg in segs_with_the_same_driver_mux:
                    tfall_avg = tfall_avg + seg.tfall
                    trise_avg = trise_avg + seg.trise
                avg_delay = (tfall_avg + trise_avg) / (2 * len(segs_with_the_same_driver_mux))
                weighted_routing_path_delay = weighted_routing_path_delay +  avg_delay * mux.weight

        self.delay_dict["weighted_routing_delay"] = weighted_routing_path_delay


        """
        for seg in self.seg_profiles:
            if not hasattr(seg, "top_spice_path"):
                continue
            else:
                self.log.info("Doing Hsice simulation for " + seg.seg_name)
                valid_delay = True

                #run hspice
                spice_meas = hspice_api.run(seg.top_spice_path, parameter_dict)

                #get hpsice measurement results
                if spice_meas["meas_total_tfall"][0] == "failed" or spice_meas["meas_total_trise"][0] == "failed":
                    valid_delay = False
                    tfall = 1
                    trise = 1
                else:
                    tfall = float(spice_meas["meas_total_tfall"][0])
                    trise = float(spice_meas["meas_total_trise"][0])
                if tfall < 0 or trise < 0:
                    valid_delay = False

                #assign delay to newly-added attribute delay of segment profile object
                seg.delay = max(tfall, trise)
        """
        #average delays of each segment
        for seg in self.seg_profiles:
            if not hasattr(seg, "delay"):
                continue
            else:
                if not seg.seg_name in self.delay_dict.keys():
                    self.delay_dict[seg.seg_name] = []
                    self.delay_dict[seg.seg_name].append((seg.tfall, seg.trise))
                else:
                    self.delay_dict[seg.seg_name].append((seg.tfall, seg.trise))

        return valid_delay

    def update_itself(self):
        """this function is a wrap of other member functions, in order to update area, wire length, and wire rc as transistor sizes changes"""
        self.update_area()
        self.update_wires()
        self.update_wire_rc()

    def update_transistor_sizes(self, trans_names, sizing_combinations, inv_ratios = None):
        """ This function is used to update self.transistor_sizes for a particular transistor sizing combination.
            'element_names' is a list of elements (ptran, inv, etc.) that need their sizes updated.
            'combo' is a particular transistor sizing combination for the transistors in 'element_names'
            'inv_ratios' are the inverter P/N ratios for this transistor sizing combination.
            'combo' will typically describe only the transistors belong to a type of mux. Other transistors retain their current size."""
        new_sizes = {}
        assert len(trans_names) == len(sizing_combinations)
        for i in range(len(trans_names)):
            trans_name = trans_names[i]
            trans_size = sizing_combinations[i]
            if "ptran_" in trans_name:
                new_sizes[trans_name + "_nmos"] = trans_size
            elif "rest_" in trans_name:
                new_sizes[trans_name + "_pmos"] = trans_size
            elif "inv_" in trans_name:
                if inv_ratios is None:
                    # todo: why not make pmos_size double nmos_size to speed up searching, as we all know, pmos size generally need to be larger than nmos size
                    new_sizes[trans_name + "_nmos"] = trans_size
                    new_sizes[trans_name + "_pmos"] = trans_size
                else:
                    if inv_ratios[trans_name] < 1:
                        new_sizes[trans_name + "_pmos"] = trans_size
                        new_sizes[trans_name + "_nmos"] = trans_size / inv_ratios[trans_name]
                    else:
                        new_sizes[trans_name + "_nmos"] = trans_size
                        new_sizes[trans_name + "_pmos"] = trans_size * inv_ratios[trans_name]
        self.transistor_sizes.update(new_sizes)

    def _area_model(self, tran_size):
        """ Transistor area model. 'tran_size' is the transistor drive strength in min. width transistor drive strengths. """
        area = 0.447 + 0.128 * tran_size + 0.391 * math.sqrt(tran_size)
        return area

    def _generate_includes(self, log):
            """ Generate the includes file. Top-level SPICE decks should only include this file. """
            log.info("Generating includes.l")

            includes_file = open(self.includes_filename, 'w')
            includes_file.write("*** INCLUDE ALL LIBRARIES\n\n")
            includes_file.write(".LIB INCLUDES\n\n")
            includes_file.write("* Include process data (voltage levels, gate length and device models library)\n")
            includes_file.write(".LIB \"process_data.l\" PROCESS_DATA\n\n")
            includes_file.write("* Include transistor parameters\n")
            includes_file.write("* Include wire resistance and capacitance\n")
            # includes_file.write(".LIB \"wire_RC.l\" WIRE_RC\n\n")
            includes_file.write("* Include basic subcircuits\n")
            includes_file.write(".LIB \"basic_subcircuits.l\" BASIC_SUBCIRCUITS\n\n")
            includes_file.write("* Include subcircuits\n")
            includes_file.write(".LIB \"subcircuits.l\" SUBCIRCUITS\n\n")
            includes_file.write("* Include sweep data file for .DATA sweep analysis\n")
            includes_file.write(".INCLUDE \"sweep_data.l\"\n\n")
            includes_file.write(".ENDL INCLUDES")
            includes_file.close()

    def _generate_process_data(self, log):
        """ Write the process data library file. It contains voltage levels, gate length and device models. """

        log.info("Generating process_data.l")

        process_data_file = open(self.process_data_filename, 'w')
        process_data_file.write("*** PROCESS DATA AND VOLTAGE LEVELS\n\n")
        process_data_file.write(".LIB PROCESS_DATA\n\n")
        process_data_file.write("* Voltage levels\n")
        process_data_file.write(".PARAM supply_v = " + str(self.specs.vdd) + "\n")
        process_data_file.write(".PARAM sram_v = " + str(self.specs.vsram) + "\n")
        process_data_file.write(".PARAM sram_n_v = " + str(self.specs.vsram_n) + "\n")

        process_data_file.write("* Geometry\n")
        process_data_file.write(".PARAM gate_length = " + str(self.specs.gate_length) + "n\n")
        process_data_file.write(".PARAM trans_diffusion_length = " + str(self.specs.trans_diffusion_length) + "n\n")
        process_data_file.write(".PARAM min_tran_width = " + str(self.specs.min_tran_width) + "n\n")
        process_data_file.write(".param rest_length_factor=" + str(self.specs.rest_length_factor) + "\n")
        process_data_file.write("\n")

        process_data_file.write("* Supply voltage.\n")
        process_data_file.write("VSUPPLY vdd gnd supply_v\n")
        process_data_file.write("* SRAM voltages connecting to gates\n")
        process_data_file.write("VSRAM vsram gnd sram_v\n")
        process_data_file.write("VSRAM_N vsram_n gnd sram_n_v\n\n")
        process_data_file.write("* Device models\n")
        process_data_file.write(".LIB \"" + "../../" + self.specs.model_path + "\" " + self.specs.model_library + "\n\n")
        process_data_file.write(".ENDL PROCESS_DATA")
        process_data_file.close()

    def _generate_basic_subcircuits(self, log):
        """ Generates the basic subcircuits SPICE file (pass-transistor, inverter, etc.) """
        log.info("Generating basic_subcircuits.l")

        # Open basic subcircuits file and write heading
        basic_sc_file = open(self.basic_subcircuits_filename, 'w')
        basic_sc_file.write("*** BASIC SUBCIRCUITS\n\n")
        basic_sc_file.write(".LIB BASIC_SUBCIRCUITS\n\n")
        basic_sc_file.close()

        basic_subcircuits.wire_generate(self.basic_subcircuits_filename)
        basic_subcircuits.ptran_generate(self.basic_subcircuits_filename, False)
        basic_subcircuits.ptran_pmos_generate(self.basic_subcircuits_filename, False)
        basic_subcircuits.rest_generate(self.basic_subcircuits_filename, False)
        basic_subcircuits.inverter_generate(self.basic_subcircuits_filename, False, None)

        # Write footer
        basic_sc_file = open(self.basic_subcircuits_filename, 'a')
        basic_sc_file.write(".ENDL BASIC_SUBCIRCUITS")
        basic_sc_file.close()

    def _create_lib_files(self, log):
        """ Create SPICE library files and add headers. """
        log.info("Generating subcircuits.l")

        # Create Subcircuits file
        sc_file = open(self.subcircuits_filename, 'w')
        sc_file.write("*** SUBCIRCUITS\n\n")
        sc_file.write(".LIB SUBCIRCUITS\n\n")
        sc_file.close()

    def _end_lib_files(self):
        """ End the SPICE library files. """

        # Subcircuits file
        sc_file = open(self.subcircuits_filename, 'a')
        sc_file.write(".ENDL SUBCIRCUITS")
        sc_file.close()

    def get_routing_area(self):
        """return total area of routing mux"""
        if self.area_dict.get("total_routing_area", -1) == -1:
            self.log.error("total_routing_area not found!")
        else:
            return self.area_dict["total_routing_area"]

    def get_routing_delay(self):
        """return the sum of all weighted segment profile delay"""
        if self.delay_dict.get("weighted_routing_delay", -1) == -1:
            self.log.error("weighted_routing_delay not found!")
        else:
            return self.delay_dict["weighted_routing_delay"]

    def get_segs_by_routing_mux(self, mux):
        """Given a mux, check which segment profile has it as the driver mux or load muxes with enough proportion, return those segs
           This helps exclude unnecessary segment profiles during hspice sims"""
        segs_list = []

        for seg_profile in self.seg_profiles:
            if hasattr(seg_profile, "mux_instances"):
                mux_name = mux.name
                if mux_name in os.path.basename(seg_profile.top_spice_path):
                    #mux as the driver mux
                    segs_list.append(seg_profile)
                else:
                    if len(seg_profile.mux_instances) == 1:
                        continue
                    #mux as load muxes with enough proportion
                    routing_mux_instance_tag = [mux_name + "_on", mux_name + "_off", mux_name + "_partial"]
                    load_cnt = 0
                    load_ratio = 0.0
                    for tag in routing_mux_instance_tag:
                        if tag in seg_profile.mux_instances:
                            # to speed up simulation, filter those seg_profiles in which the mux only accounts for a small proprotion of the load mux.
                            load_cnt = load_cnt + seg_profile.mux_instances.count(tag)
                    #i assume load_ratio bigger than 0.3 matters, the larger, the faster of the simulation
                    load_ratio = float(load_cnt) / (len(seg_profile.mux_instances) - 1)
                    if load_ratio > 0.3:
                        segs_list.append(seg_profile)

        if not segs_list:
            self.log.warning("No segment profiles contain the mux!")
        return segs_list

if __name__ == "__main__":
    try:
        src_dir = sys.path[0]
        work_dir = os.path.dirname(src_dir)
        os.chdir(work_dir)
        if not os.path.exists("tmp"):
            os.mkdir("tmp")
        os.chdir("tmp")
        print(src_dir + work_dir + os.getcwd())
        seg_length_dic = {'l1':1, 'l2':2, 'l3':3, 'l4':4, 'l5':5, 'l8':8, 'l12':12, 'imux_medium':0, 'omux_medium':0, 'gsb_medium':0}
        seg_profiles, tile_muxes = parse_rrg.parse_rrg('/home/syh/projects/openfpga_gsb/rr.graph', seg_length_dic)
        inst_complex_routing = ComplexRouting(seg_profiles, tile_muxes, None, None)
        inst_complex_routing.generate()
        #delete all files generate last time
        tmp_files = os.listdir(os.path.join(work_dir, "tmp"))
        for contect in tmp_files:
            if os.path.isdir(os.path.join(work_dir, "tmp") + "/" + contect):
                shutil.rmtree(os.path.join(work_dir, "tmp") + "/" + contect)
            else:
                os.remove(os.path.join(work_dir, "tmp") + "/" + contect)

    except Exception as e:
        print(e.__class__ + e)