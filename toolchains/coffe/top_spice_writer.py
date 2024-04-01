import utils
import sys

def write_spice_file_header(spice_file, title):
    with open(spice_file, 'a') as fp:
        fp.write(".TITLE " + title + "\n\n")
        fp.write("********************************************************************************\n")
        fp.write("** Include libraries, parameters and other\n")
        fp.write("********************************************************************************\n\n")
        fp.write(".LIB \"../../includes.l\" INCLUDES\n\n")
    fp.close()

def write_spice_setup_and_input(spice_file):
    with open(spice_file, 'a') as fp:
        fp.write("********************************************************************************\n")
        fp.write("** Setup and input\n")
        fp.write("********************************************************************************\n\n")
        fp.write(".TRAN 1p 24n SWEEP DATA=sweep_data\n")
        fp.write(".OPTIONS BRIEF=1 captab\n\n")
        fp.write("* Input signal\n")
        fp.write("VIN n_in gnd PULSE (0 supply_v 1n 0 0 2n 4n)\n\n")
    fp.close()

def write_spice_measurement(spice_file, seg, seg_name_dict, buf_delay_meas_points, inv_delay_meas_points, seg_delay_meas_points):
    """measure the delay between two points, and attach a tag to the measurement in order to parse the delay of interest later on"""

    with open(spice_file, 'a') as fp:
        fp.write("\n\n********************************************************************************\n")
        fp.write("** Measurement\n")
        fp.write("********************************************************************************\n\n")

        #get measurement tag for measuring the mux delay
        #mux_delay_tag = "meas_" + str(seg.driver_mux.mux_type) + '_size_' + str(seg.driver_mux.mux_size) + '_mux'

        #get measurement tag for measuring the segment delay
        segment_delay_tag = "meas_" + seg.seg_name

        # get measurement tag for measuring the inverter delay
        inverter1_delay_tag = "meas_inv_" + utils.segid_to_name(seg.driver_mux.mux_type, seg_name_dict) + '_size_' + str(seg.driver_mux.mux_size) + '_mux_1'
        inverter2_delay_tag = "meas_inv_" + utils.segid_to_name(seg.driver_mux.mux_type, seg_name_dict) + '_size_' + str(seg.driver_mux.mux_size) + '_mux_2'

        '''fp.write("* the delay of the driver mux of the segment\n")
        #fall delay of the mux driver(buffer)
        fp.write(".MEASURE TRAN " + mux_delay_tag + "_tfall TRIG V(" + str(buf_delay_meas_points[0]) + ") VAL='supply_v/2' RISE=1\n")
        fp.write("+    TARG V(" + str(buf_delay_meas_points[1]) + ") VAL='supply_v/2' RISE=1\n")
        #rise delay of the mux driver(buffer)
        fp.write(".MEASURE TRAN " + mux_delay_tag + "_trise TRIG V(" + str(buf_delay_meas_points[0]) + ") VAL='supply_v/2' FALL=1\n")
        fp.write("+    TARG V(" + str(buf_delay_meas_points[1]) + ") VAL='supply_v/2' FALL=1\n")'''

        fp.write("* the delay of the 1st inverter of the driver mux of the segment\n")
        # fall delay of the mux driver(buffer)
        fp.write(".MEASURE TRAN " + inverter1_delay_tag + "_tfall TRIG V(" + str(inv_delay_meas_points[0]) + ") VAL='supply_v/2' RISE=1\n")
        fp.write("+    TARG V(" + str(inv_delay_meas_points[1]) + ") VAL='supply_v/2' FALL=1\n")
        # rise delay of the mux driver(buffer)
        fp.write(".MEASURE TRAN " + inverter1_delay_tag + "_trise TRIG V(" + str(inv_delay_meas_points[0]) + ") VAL='supply_v/2' FALL=1\n")
        fp.write("+    TARG V(" + str(inv_delay_meas_points[1]) + ") VAL='supply_v/2' RISE=1\n")

        fp.write("\n* the delay of the 2nd inverter of the driver mux of the segment\n")
        # fall delay of the segment
        fp.write(".MEASURE TRAN " + inverter2_delay_tag + "_tfall TRIG V(" + str(seg_delay_meas_points[0]) + ") VAL='supply_v/2' FALL=1\n")
        fp.write("+    TARG V(" + str(seg_delay_meas_points[1]) + ") VAL='supply_v/2' FALL=1\n")
        # rise delay of the segment
        fp.write(".MEASURE TRAN " + inverter2_delay_tag + "_trise TRIG V(" + str(seg_delay_meas_points[0]) + ") VAL='supply_v/2' RISE=1\n")
        fp.write("+    TARG V(" + str(seg_delay_meas_points[1]) + ") VAL='supply_v/2' RISE=1\n\n")

        fp.write("\n* the delay of segment path\n")
        #fall delay of the segment
        fp.write(".MEASURE TRAN " + "meas_total_tfall TRIG V(" + str(seg_delay_meas_points[0]) + ") VAL='supply_v/2' FALL=1\n")
        fp.write("+    TARG V(" + str(seg_delay_meas_points[1]) + ") VAL='supply_v/2' FALL=1\n")
        #rise delay of the segment
        fp.write(".MEASURE TRAN " + "meas_total_trise TRIG V(" + str(seg_delay_meas_points[0]) + ") VAL='supply_v/2' RISE=1\n")
        fp.write("+    TARG V(" + str(seg_delay_meas_points[1]) + ") VAL='supply_v/2' RISE=1\n\n")

        #end identifier
        fp.write(".END")
    fp.close()

def write_spice_circuit(spice_file, seg_name_dict, seg, default_fanin_seg = None):
    """generate wire segment circuits, including driving context and load context,
    return pairs of ports between which TRIG and TARG points of transisent measurement are added"""

    # list to record every routing mux exemplified as the driver mux or load muxes of the segment profile
    mux_instances = []
    try:

        #intricnsic delay of buffer used by VPR
        buf_delay_meas_points = None

        #inverter delay of the buffer
        inv_delay_meas_points = None

        #segment routing path delay, which is used to guide the process of sizing transistors
        seg_delay_meas_points = None

        with open(spice_file, 'a') as fp:
            fp.write("********************************************************************************\n")
            fp.write("** Circuits\n")
            fp.write("********************************************************************************\n\n")

            driver_mux_name = utils.segid_to_name(seg.driver_mux.mux_type, seg_name_dict) + '_size_' + str(seg.driver_mux.mux_size) + '_mux'
            if default_fanin_seg is not None:
                #parameterize mux name
                ######################
                fanin_seg_driver_mux_name = utils.segid_to_name(default_fanin_seg.driver_mux.mux_type, seg_name_dict) + '_size_' + str(default_fanin_seg.driver_mux.mux_size) + '_mux'

                #instance the fanin wire segment
                ###############################
                fanin_seg_name = 'fanin_segment' + str(default_fanin_seg.segment_id)
                fanin_seg_load_muxes_distince = default_fanin_seg.get_load_distances()
                fanin_seg_load_muxes = default_fanin_seg.fanout_mux
                fanin_seg_len = default_fanin_seg.wire_length

                #instance the fanin mux
                #the name of the mux to be instanced need to append with 3 optional tags '_on', '_off', '_partial'
                #the name of the instanced fanin mux is in the form of 'Xfanin_" + mux
                ref_fanin_seg_driver_mux_name = fanin_seg_driver_mux_name + '_on'
                inst_fanin_seg_driver_mux_name = 'X' + fanin_seg_name + "_driver_mux_" + ref_fanin_seg_driver_mux_name
                #the mux circuit have 6 ports: input, output, sram, sram_n, vdd, gnd; partial have 5; off have 5
                fp.write(inst_fanin_seg_driver_mux_name + " n_in n_1_1 vsram vsram_n vdd gnd " + ref_fanin_seg_driver_mux_name + "\n")

                #instance the fanout mux of the fanin wire segment
                if default_fanin_seg.wire_length == 0:
                    driver_mux_flag = False
                    ref_fanin_seg_name = "wire"
                    inst_fanin_seg_name = "Xwire_" + fanin_seg_name
                    fp.write(inst_fanin_seg_name + " n_1_1" + " n_1_2" + " " + ref_fanin_seg_name + " Rw='" + default_fanin_seg.seg_name + "_res" + "' Cw='" + default_fanin_seg.seg_name + "_cap" + "'\n")
                    for i in range(len(fanin_seg_load_muxes)):
                        fanin_seg_load_mux = fanin_seg_load_muxes[i]
                        fanin_seg_load_mux_name = utils.segid_to_name(fanin_seg_load_mux.mux_type, seg_name_dict) + "_size_" + str(fanin_seg_load_mux.mux_size) + "_mux"
                        ref_fanin_seg_load_mux_name = fanin_seg_load_mux_name + "_off"
                        inst_fanin_seg_load_mux_name = "X" + fanin_seg_name + "_load_mux_" + str(i) + "_" + ref_fanin_seg_load_mux_name
                        if driver_mux_flag or fanin_seg_load_mux_name != driver_mux_name:
                            fp.write(inst_fanin_seg_load_mux_name + " n_1_2" + " gnd gnd gnd gnd " + ref_fanin_seg_load_mux_name + "\n")
                        else:
                            #this is the dirver mux of seg
                            driver_mux_flag = True
                            ref_fanin_seg_load_mux_name = fanin_seg_load_mux_name + "_on"
                            inst_fanin_seg_load_mux_name = "X" + ref_fanin_seg_load_mux_name
                            fp.write(inst_fanin_seg_load_mux_name + " n_1_2" + " n_2_1 vsram vsram_n vdd gnd " + ref_fanin_seg_load_mux_name + "\n")

                            #trigger and target point for transient measure
                            # the naming ways here is determined by the structure of a mux, refer to the generation of mux
                            buf_delay_meas_points = (inst_fanin_seg_load_mux_name + ".n_in", inst_fanin_seg_load_mux_name + ".X" + driver_mux_name + "_driver.n_out")
                            inv_delay_meas_points = (inst_fanin_seg_load_mux_name + ".n_in", inst_fanin_seg_load_mux_name + ".X" + driver_mux_name + "_driver.n_1_1")

                            #record the driver mux of the seg
                            mux_instances.append(ref_fanin_seg_load_mux_name)
                else:
                    driver_mux_flag = False
                    for i in range(1, fanin_seg_len+1):
                        ref_fanin_seg_name = "wire" #this is determined by the subcircuit wire name in subcircuit.l
                        inst_fanin_seg_name = "Xwire_" + fanin_seg_name + "_" + str(i)

                        #add wire tile by tile
                        #the wire circuit have 2 ports: input, output
                        fp.write(inst_fanin_seg_name + " n_1_" + str(i) + " n_1_" + str(i+1) + " " + ref_fanin_seg_name + " Rw='" + default_fanin_seg.seg_name + "_res/" + str(fanin_seg_len) + "' Cw='" + default_fanin_seg.seg_name + "_cap/" + str(fanin_seg_len) + "'\n")
                        #add load mux that exactly hang on intermediate segment at length i
                        for k in [j for j in range(len(fanin_seg_load_muxes_distince)) if fanin_seg_load_muxes_distince[j] == i]:
                            fanin_seg_load_mux = fanin_seg_load_muxes[k]
                            fanin_seg_load_mux_name = utils.segid_to_name(fanin_seg_load_mux.mux_type, seg_name_dict) + '_size_' + str(fanin_seg_load_mux.mux_size) + '_mux'

                            #todo: temperorily assume all load mux except the driver mux on fanin segment is off, later should consider actual load distribution
                            ref_fanin_seg_load_mux_name = fanin_seg_load_mux_name + "_off"
                            inst_fanin_seg_load_mux_name = "X" + fanin_seg_name + "_load_mux_" + str(k) + "_" + ref_fanin_seg_load_mux_name
                            if driver_mux_flag or fanin_seg_load_mux_name != driver_mux_name:
                                fp.write(inst_fanin_seg_load_mux_name + " n_1_" + str(i+1) + " gnd gnd gnd gnd " + ref_fanin_seg_load_mux_name + "\n")
                            else:
                                #this is the driver mux of seg
                                driver_mux_flag = True
                                ref_fanin_seg_load_mux_name = driver_mux_name + "_on"
                                inst_fanin_seg_load_mux_name = 'X' + ref_fanin_seg_load_mux_name
                                fp.write(inst_fanin_seg_load_mux_name + " n_1_" + str(i+1) + " n_2_1 vsram vsram_n vdd gnd " + ref_fanin_seg_load_mux_name + "\n")

                                #trigger and target point for transient measure
                                buf_delay_meas_points = (inst_fanin_seg_load_mux_name + ".n_in", inst_fanin_seg_load_mux_name + ".X" + driver_mux_name + "_driver.n_out")
                                inv_delay_meas_points = (inst_fanin_seg_load_mux_name + ".n_in", inst_fanin_seg_load_mux_name + ".X" + driver_mux_name + "_driver.n_1_1")

                                #record the driver mux of the seg
                                mux_instances.append(ref_fanin_seg_load_mux_name)
            else:
                # assume a 2:1 mux driving seg
                # entering else branch means all fanin of the seg is 'OPIN',
                # i think assuming a 2:1 mux inside CLB driving 'OPIN' is
                # reasonable as general CLB output mux is usually the case
                opin_driver_mux_name = 'opin_size_2_mux_on'
                inst_opin_driver_mux_name = 'X' + opin_driver_mux_name
                fp.write(inst_opin_driver_mux_name + " n_in n_1_1 vsram vsram_n vdd gnd " + opin_driver_mux_name + "\n")

                #add a wire driven by opin_size_2_mux, this wire should have 0 length and muxt be parameterized!!!
                intra_tile_wire_name = "intra_tile_wire"
                inst_intra_tile_wire_name = "X" + intra_tile_wire_name
                fp.write(inst_intra_tile_wire_name + " n_1_1 n_1_2 wire " + "Rw='" + "tile_res" + "' Cw='" + "tile_cap'\n")

                #add the driver mux of current segment
                fp.write("X" + driver_mux_name + "_on" + " n_1_2 n_2_1 vsram vsram_n vdd gnd " + driver_mux_name + "_on\n")

                #get TRIG and TARG measurement points of the driver mux delay
                buf_delay_meas_points = ("X" + driver_mux_name + "_on.n_in", "X" + driver_mux_name + "_on.X" + driver_mux_name + "_driver.n_out")

                #get TRIG and TARG measurement points of the inverter delay
                inv_delay_meas_points = ("X" + driver_mux_name + "_on.n_in", "X" + driver_mux_name + "_on.X" + driver_mux_name + "_driver.n_1_1")

                # record the driver mux of the seg
                mux_instances.append(driver_mux_name + "_on")

            #instance the fanout wire segment
            #####################################3
            fanout_seg_name = "fanout_segment" + str(seg.segment_id)
            fanout_seg_load_muxes_distince = seg.get_load_distances()
            fanout_seg_load_muxes = seg.fanout_mux
            fanout_seg_len = seg.wire_length

            #the fanin mux is the driver mux, already instanced above

            #instance the fanout mux
            if fanout_seg_len == 0:
                on_mux_flag = False
                ref_fanout_seg_name = "wire"
                inst_fanout_seg_name = "Xwire_" + fanout_seg_name + "_0"
                fp.write(inst_fanout_seg_name + " n_2_1" + " n_2_2" + " " + ref_fanout_seg_name + " Rw='" + seg.seg_name + "_res" + "' Cw='" + seg.seg_name + "_cap" + "'\n")
                for i in range(len(fanout_seg_load_muxes)):
                    fanout_seg_load_mux = fanout_seg_load_muxes[i]
                    fanout_seg_load_mux_name = utils.segid_to_name(fanout_seg_load_mux.mux_type, seg_name_dict) + "_size_" + str(fanout_seg_load_mux.mux_size) + "_mux"
                    ref_fanout_seg_load_mux_name = fanout_seg_load_mux_name + "_off"
                    inst_fanout_seg_load_mux_name = "X" + fanout_seg_name + "_load_mux_" + str(i) + "_" + ref_fanout_seg_load_mux_name
                    if on_mux_flag:
                        fp.write(inst_fanout_seg_load_mux_name + " n_2_2" + " gnd gnd gnd gnd " + ref_fanout_seg_load_mux_name + "\n")
                    else:
                        on_mux_flag = True
                        ref_fanout_seg_load_mux_name = fanout_seg_load_mux_name + "_on"
                        inst_fanout_seg_load_mux_name = "X" + fanout_seg_name + "_load_mux_" + str(i) + "_" + ref_fanout_seg_load_mux_name
                        fp.write(inst_fanout_seg_load_mux_name + " n_2_2" + " n_out vsram vsram_n vdd gnd " + ref_fanout_seg_load_mux_name + "\n")

                    # record the driver mux of the seg
                    mux_instances.append(ref_fanout_seg_load_mux_name)
            else:
                #todo: assume the first load mux is 'on'
                on_mux_flag = False
                for i in range(1, fanout_seg_len + 1):
                    ref_fanout_seg_name = "wire"  # this is determined by the subcircuit wire name in subcircuit.l
                    inst_fanout_seg_name = "Xwire_" + fanout_seg_name + "_" + str(i)
                    # add wire tile by tile
                    # the wire circuit have 2 ports: input, output
                    fp.write(inst_fanout_seg_name + " n_2_" + str(i) + " n_2_" + str(i + 1) + " " + ref_fanout_seg_name + " Rw='" + seg.seg_name + "_res/" + str(fanout_seg_len) + "' Cw='" + seg.seg_name + "_cap/" + str(fanout_seg_len) + "'\n")
                    # add load mux that exactly hang on intermediate segment at length i
                    load_mux_index_at_length_i = [j for j in range(len(fanout_seg_load_muxes_distince)) if fanout_seg_load_muxes_distince[j] == i]
                    for k in load_mux_index_at_length_i:
                        fanout_seg_load_mux = fanout_seg_load_muxes[k]
                        fanout_seg_load_mux_name = utils.segid_to_name(fanout_seg_load_mux.mux_type, seg_name_dict) + '_size_' + str(fanout_seg_load_mux.mux_size) + '_mux'
                        # todo: temperorily assume all load mux on fanout segment is off, later should consider actual load distribution
                        ref_fanout_seg_load_mux_name = fanout_seg_load_mux_name + "_off"
                        inst_fanout_seg_load_mux_name = "X" + fanout_seg_name + "_load_mux_" + str(k) + "_" + ref_fanout_seg_load_mux_name
                        if on_mux_flag:
                            fp.write(inst_fanout_seg_load_mux_name + " n_2_" + str(i + 1) + " gnd gnd gnd gnd " + ref_fanout_seg_load_mux_name + "\n")
                        else:
                            on_mux_flag = True
                            ref_fanout_seg_load_mux_name = fanout_seg_load_mux_name + "_on"
                            inst_fanout_seg_load_mux_name = "X" + fanout_seg_name + "_load_mux_" + str(k) + "_" + ref_fanout_seg_load_mux_name
                            fp.write(inst_fanout_seg_load_mux_name + " n_2_" + str(i + 1) + " n_out vsram vsram_n vdd gnd " + ref_fanout_seg_load_mux_name + "\n\n")

                        # record the driver mux of the seg
                        mux_instances.append(ref_fanout_seg_load_mux_name)

            if buf_delay_meas_points is None:
                print("get buffer delay measure points failed!")
                print(driver_mux_name)
                sys.exit(1)
            else:
                seg_delay_meas_points = (buf_delay_meas_points[0], "Xwire_" + fanout_seg_name + "_" + str(fanout_seg_len) + ".n_out")
        fp.close()

        return buf_delay_meas_points, inv_delay_meas_points, seg_delay_meas_points, mux_instances
    except Exception as e:
        print("error:write_spice_circuit:%s"%e)