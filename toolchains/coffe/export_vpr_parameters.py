import os

import top_spice_writer as tsw
import utils


def write_mux_spice_files(spice_file, mux_inst):
    """write spice files for getting vpr interested parameters"""

    mux_name = mux_inst.name
    mux_name_ref = mux_name + "_on"
    mux_name_inst = "X" + mux_name_ref
    rise_delay_meas = mux_name + "_trise"
    fall_delay_meas = mux_name + "_tfall"

    par_dir = os.getcwd()
    if not os.path.exists(os.getcwd() + '/' + mux_name):
        os.mkdir(os.getcwd() + '/' + mux_name)
    os.chdir(os.getcwd() + '/' + mux_name)

    #write spice head
    with open(spice_file, 'a') as fp:
        fp.write(".TITLE " + mux_name + "\n\n")
        fp.write("********************************************************************************\n")
        fp.write("** Include libraries, parameters and other\n")
        fp.write("********************************************************************************\n\n")
        fp.write(".LIB \"../../../includes.l\" INCLUDES\n\n")
    fp.close()
    
    #write spice setup
    tsw.write_spice_setup_and_input(spice_file)
    
    #write spice circuits
    with open(spice_file, 'a') as fp:
        fp.write("\n***************************************************\n***MUX CIRCUIT\n")
        fp.write("****************************************************\n")
        fp.write(mux_name_inst + " n_in n_out vsram vsram_n vdd gnd " + mux_name_ref + "\n")
        
        fp.write("\n***************************************************\n***MEASUREMENT\n")
        fp.write("****************************************************\n")
        fp.write(".MEASURE TRAN " + rise_delay_meas + " TRIG V(" + mux_name_inst + ".n_1_1) VAL='supply_v/2' RISE=2\n")
        fp.write("+    TARG V(n_out) VAL='supply_v/2' RISE=2\n")
        fp.write(".MEASURE TRAN " + fall_delay_meas + " TRIG V(" + mux_name_inst + ".n_1_1) VAL='supply_v/2' FALL=2\n")
        fp.write("+    TARG V(n_out) VAL='supply_v/2' FALL=2\n")

        fp.write(".END")
    fp.close()

    spice_path = os.getcwd() + "/" + spice_file
    os.chdir(par_dir)
    
    return spice_path
        


def parse_cap(filepath):
    """parse input cap and output cap of a mux, stored in the .lis file"""
    in_cap, out_cap = '', ''
    with open(filepath, 'r') as lis:
        for line in lis.readlines():
            if line.startswith(" +"):
                if 'n_in' in line or 'n_out' in line:
                    frags = line.split(':')
                    for frag in frags:
                        if '=' in frag:
                            if 'n_in' in frag:
                                if 'a' in frag:
                                    equation = frag.split('a')[0].replace(' ', '')
                                    in_cap = equation.split('=')[1] + 'a'
                                elif 'f' in frag:
                                    equation = frag.split('f')[0].replace(' ', '')
                                    in_cap = equation.split('=')[1] + 'f'
                            if 'n_out' in frag:
                                if 'a' in frag:
                                    equation = frag.split('a')[0].replace(' ', '')
                                    out_cap = equation.split('=')[1] + 'a'
                                elif 'f' in frag:
                                    equation = frag.split('f')[0].replace(' ', '')
                                    out_cap = equation.split('=')[1] + 'f'
    return in_cap, out_cap



def export_vpr_parameters(file_name, complex_routing_inst, hspice, log):
    """After transistor sizing, parameters needed by VPR to perform architectural exploration are should be extracted from complex_routing_inst.
       Cin: capacitance of input mux
       Cout: capacitance of buffer's output
       Tdel: intrinsic delay of the buffer
       Buf_size: the num of units in MWTA of the buffer
       Mux_trans_size: the num of units in MWTA of the pass transistor
       R: equalent resistence of chain of the pass transistors
    """
    par_dir = os.getcwd()
    if not os.path.exists(os.getcwd() + "/sizing_results/mux_sp"):
        os.makedirs(os.getcwd() + "/sizing_results/mux_sp")
    os.chdir(os.getcwd() + "/sizing_results/mux_sp")

    
    #generate mux spice files which doesn't include any input resistors and output load
    mux_list = []
    for mux_name, mux in complex_routing_inst.muxes.items():
        if mux.num_per_tile != -1:
            spice_file = mux_name + ".sp"
            mux.spice_path =  write_mux_spice_files(spice_file, mux)
            mux_list.append(mux)
    
    #prepare parameters to do hspice sims
    param_dict = {}
    for trans_name, size in complex_routing_inst.transistor_sizes.items():
        param_dict[trans_name] = [size * complex_routing_inst.specs.min_tran_width * 1e-9]
    for wire_name, rc_data in complex_routing_inst.wire_rc_dict.items():
        param_dict[wire_name + "_res"] = [rc_data[0]]
        param_dict[wire_name + "_cap"] = [rc_data[1] * 1e-15]

    # do hspice sims for mux
    pool = utils.get_parallel_num(len(mux_list))
    mux_delay_meas = []
    for mux in mux_list:
        mux_delay_meas.append(pool.apply_async(utils.hspice_task, args=(hspice, mux.spice_path, param_dict,)))
    mux_delay_meas = [i.get() for i in mux_delay_meas]

    #get intrinsic delay of the mux
    mux_delay_dict = {}
    for i in range(len(mux_list)):
        mux_name = mux_list[i].name
        tfall_str = mux_delay_meas[i][mux_name + "_tfall"][0]
        trise_str = mux_delay_meas[i][mux_name + "_trise"][0]
        tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)
        mux_delay_dict[mux_name] = max(tfall, trise)

    #get input and output capacitance
    mux_cap_dict = {}
    for mux in mux_list:
        lis_file = os.path.dirname(mux.spice_path) + '/' + mux.name + '.lis'
        input_cap, output_cap = parse_cap(lis_file)
        mux_cap_dict[mux.name] = (input_cap, output_cap)

    #get buf_size and mux_trans_size
    mux_size_dict = {}
    for mux in mux_list:
        mux_name = mux.name
        buf_size = complex_routing_inst.area_dict[mux_name + "_buf_size"] / complex_routing_inst.specs.min_width_tran_area
        if (("ptran_" + mux_name + "_L1") in complex_routing_inst.area_dict) and (("ptran_" + mux_name + "_L1") in complex_routing_inst.transistor_sizes):
            mux_trans_size = complex_routing_inst.transistor_sizes["ptran_" + mux_name + "_L1"]
        elif (("ptran_" + mux_name) in complex_routing_inst.area_dict) and (("ptran_" + mux_name) in complex_routing_inst.transistor_sizes):
            mux_trans_size = complex_routing_inst.transistor_sizes["ptran_" + mux_name]
        else:
            mux_trans_size = -1
        mux_size_dict[mux_name] = (buf_size, mux_trans_size)

    #export above 3 dict to file
    os.chdir(par_dir + "/sizing_results")
    with open(file_name, 'w') as fp:
        for mux in mux_list:
            fp.write("********************\n" + mux.name + "\n************************\n")
            fp.write("Tdel".ljust(15) + ": " + str(mux_delay_dict[mux.name]) + "\n")
            fp.write("Cin".ljust(15) + ": " + mux_cap_dict[mux.name][0] + "\n")
            fp.write("Cout".ljust(15) + ": " + mux_cap_dict[mux.name][1] + "\n")
            fp.write("buf_size".ljust(15) + ": " + str(mux_size_dict[mux.name][0]) + "\n")
            fp.write("mux_trans_size".ljust(15) + ": " + str(mux_size_dict[mux.name][1]) + "\n\n")
    fp.close()

    return