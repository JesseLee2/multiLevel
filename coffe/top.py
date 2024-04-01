import argparse
import os
import time
from datetime import datetime
import traceback

import complex_routing
import utils
import hspice_api
import parse_rrg
import transistor_sizing
import export_vpr_parameters as evp

try:
    #parse the input
    parser = argparse.ArgumentParser()
    parser.add_argument('arch_description', help="path to architecture file")
    parser.add_argument('rrg_file', help='path to rrg file generated from vpr')
    parser.add_argument('-n', '--no_sizing', help="dont perform transistor sizing", action='store_true')
    parser.add_argument('-s', '--initial_sizes', type=str, default="default", help="path to initial sizes")
    parser.add_argument('-a', '--area_opt_weight', type=float, default=0.5, help='area optimization weight')
    parser.add_argument('-d', '--delay_opt_weight', type=float, default=0.5, help="delay optimization weight")
    parser.add_argument('-i', '--max_iterations', type=int, default=3, help="max FPGA sizing iterations")
    parser.add_argument('-echo_level', '--echo_level', type=str, choices=["info", "warning", "debug", "error", "critical"], default="info", help="echo log with which level")

    args = parser.parse_args()

    #create top spice folder to store intermediate files and final results
    arch_folder = utils.create_output_dir(args.arch_description)

    #create log file
    log_file = os.path.join(arch_folder, "logfile.log")
    log = utils.Logger(log_file, args.echo_level)

    #log run options
    utils.log_run_options(log, args)

    #parse arch_description file
    arch_params_dict = utils.parse_arch_parameters(args.arch_description, log)

    #create a hspcie object
    hspice = hspice_api.SpiceInterface()

    #start time
    start_t = time.time()

    #parse rrg file from vpr, this may takes a bit long time
    rrg_path = args.rrg_file
    segment_profiles, tile_muxes = parse_rrg.parse_rrg(rrg_path, arch_params_dict['segment_length_by_name'], log)

    #create a complex routing object
    complex_routing_inst = complex_routing.ComplexRouting(segment_profiles, tile_muxes, arch_params_dict, log)
    complex_routing_inst.generate(arch_folder)


    #doing Hspice simulation and transistor sizing
    print(arch_folder)
    os.chdir(arch_folder)
    transistor_sizing.size_routing_transistors(complex_routing_inst, args, hspice)

    #export vpr intersted parameters according to sized complexed routing
    os.chdir(arch_folder)
    evp.export_vpr_parameters("vpr_parameters.txt", complex_routing_inst, hspice, log)



except BaseException as e:
    print(datetime.now())
    traceback.print_exc()
    traceback.print_stack()
    #remove all files and dirs generated
    #utils.remove_all_contents(arch_folder)



