import os
import time
from itertools import product
import math
import multiprocessing
from multiprocessing import Pool
import copy
from mpl_toolkits.axisartist.parasite_axes import HostAxes, ParasiteAxes
import matplotlib.pyplot as plt

import utils
import parse_rrg

CPU_CNT = multiprocessing.cpu_count()
RF_ERROR_TOLERANCE = 0.2
ERF_MAX_ITERATIONS = 3

def get_weighted_routing_delay(complex_routing_inst, sims_segs, delay_list):
    """Within sims_segs, there are segs that have mux as the driver mux and segs that have mux as load muxes.
        With delay list that indicates the updated delay of each seg in the sims_segs, we have to update each
        mux delay from associated segs"""
    weighted_routing_path_delay = 0.0
    for mux in complex_routing_inst.muxes.values():
        associated_segs = mux.associated_segs
        tfall_avg, trise_avg = 0.0, 0.0
        if associated_segs:
            for seg in associated_segs:
                if seg in sims_segs:
                    #this indicates the seg is alrealy simulated
                    index = sims_segs.index(seg)
                    tfall_avg = tfall_avg + delay_list[index][0]
                    trise_avg = trise_avg + delay_list[index][1]
                else:
                    #this indicates the seg is not simulated
                    tfall_avg = tfall_avg + seg.tfall
                    trise_avg = trise_avg + seg.trise
            weighted_routing_path_delay = weighted_routing_path_delay + (tfall_avg + trise_avg) / (2 * len(associated_segs)) * mux.weight
    return weighted_routing_path_delay

def get_cost(area, area_weight, delay, delay_weight):
    """return (area**area_weight)*(delay**delay_weight)"""
    return pow(area, area_weight) * pow(delay, delay_weight)

def format_transistor_sizes_to_sizing_primitives(transistor_sizes):
    """formot all the transistors names to primitive sizing names.
        Notably, nmos and pmos of a invertor are treated as one sizing unit"""
    format_sizes = {}
    for tran_name, size in transistor_sizes.items():
        stripped_name = tran_name.replace("_nmos", "")
        stripped_name = stripped_name.replace("_pmos", "")
        if "inv_" in stripped_name:
            if stripped_name in format_sizes.keys():
                if size < format_sizes[stripped_name]:
                    format_sizes[stripped_name] = size
            else:
                format_sizes[stripped_name] = size
        else:
            format_sizes[stripped_name] = size    
    return format_sizes

def find_initial_sizing_ranges(transistors_sizes):
    """for a dict containing transistor name and its size info, expand its size ranges based on current size"""
    sizing_ranges = {}
    #todo: set sizing ranges to 3, need admjustment or give contral to input options
    ranges_size = 2

    #for level restorer transistor, keep it size at 1
    #for other transistors, create a sizing ranges that makes the current size at the center
    for tran_name, size in transistors_sizes.items():
        if "rest_" in tran_name:
            #the bool is a tag to indicate whether this sizing range will be used to exclude some redundant sizing combs in the following sizing process
            #True: descartes product between the size(s) on the boundary and this sizing range will be excluded
            sizing_ranges[tran_name] = (1, 1, True)
        else:
            max = size + (ranges_size / 2)
            min = size - (ranges_size / 2)
            if min < 1:
                max = max - min + 1
                min = 1
            sizing_ranges[tran_name] = (min, max, True)

    return sizing_ranges

def expand_ranges(sizing_ranges, sizes_on_the_boundary):
    """ The input to this function is a dictionary that describes the SPICE sweep
		ranges. dict = {"name": (start_value, stop_value, bool)}
		To make it easy to run all the described SPICE simulations, this function
		creates a list of all possible combinations in the ranges.
		It also produces a 'name' list that matches the order of
		the parameters for each combination.
		The bool indicates whether the sizing ranges will be used with sizes in the
		sizes_on_the_boundary to exclude the descartes product of the both from all sizing combs
		sizes_on_the_boundary : {trans_name:size}"""

    #generate all sizing ranges
    sizing_ranges_copy = sizing_ranges.copy()
    for trans_name, size_ranges in sizing_ranges_copy.items():
        start_value = size_ranges[0]
        end_value = size_ranges[1]
        current_size_list = []
        while start_value <= end_value:
            current_size_list.append(start_value)
            start_value = start_value + 1
        sizing_ranges_copy[trans_name] = current_size_list

    #generate excluding sizing ranges
    excluding_sizing_ranges = {}
    if len(sizes_on_the_boundary):
        for trans_name, size_ranges in sizing_ranges.items():
            tag = size_ranges[2]
            if tag:
                excluding_sizing_ranges[trans_name] = sizing_ranges_copy[trans_name]
            else:
                #trans_name must exist in the sizes_on_the_boundary
                excluding_sizing_ranges[trans_name] = [sizes_on_the_boundary.get(trans_name)]

    #generate all sizing combs
    sizing_combinations = []
    for one_com in product(*[sizing_ranges_copy[i] for i in sorted(sizing_ranges_copy.keys())]):
        sizing_combinations.append(one_com)

    #generate all excluding sizing combs
    ex_sizing_combinations = []
    if len(sizes_on_the_boundary):
        for one_com in product(*[excluding_sizing_ranges[i] for i in sorted(excluding_sizing_ranges.keys())]):
            ex_sizing_combinations.append(one_com)

    trans_names = sorted(sizing_ranges_copy.keys())

    #exclud redundant sizing combs
    for one_com in ex_sizing_combinations:
        sizing_combinations.remove(one_com)

    return trans_names, sizing_combinations

def get_middle_sizing_combination(transistor_names, sizing_ranges):
    """"""
    sizing_combination = ()
    for trans_name in transistor_names:
        range = sizing_ranges[trans_name]
        min = range[0]
        max = range[1]
        mid = int(math.ceil((max - min) / 2 + min))
        sizing_combination = sizing_combination + (mid,)
    return sizing_combination

def create_hspcie_sweep_data(param_list, tar_param, sweep_data_list):
    """create a sweep param_list, which get the value from the existing param_list except that the tar_param uses the value in sweep_data_list"""
    # Make a new sweep parameter dict
    sweep_parameter_dict = {}
    for i in range(len(sweep_data_list)):
        for name in param_list.keys():
            # Get the value from the existing dictionary and only change it if it's our
            # target transistor.
            value = param_list[name][0]
            if name == tar_param:
                value = 1e-9 * sweep_data_list[i]

            # On the first iteration, we have to add the lists themselves, but every
            # other iteration we can just append to the lists.
            if i == 0:
                sweep_parameter_dict[name] = [value]
            else:
                sweep_parameter_dict[name].append(value)
    return sweep_parameter_dict

def print_erf_log(tar_trans_name, tfall, trise, inv_size, tar_trans_size, log):
    """verbose log info for observing erf process in running time"""
    abs_error = abs(trise - tfall)
    relative_error = abs(trise - tfall) / min(trise, tfall)
    if "pmos" in tar_trans_name:
        sizing_str = "NMOS=" + str(inv_size) + " PMOS=" + str(tar_trans_size)
    else:
        sizing_str = "NMOS=" + str(tar_trans_size) + " PMOS=" + str(inv_size)
    log.info(sizing_str + " | tfall=" + str(tfall) + " trise=" + str(trise) + " | absolute_error=" + str(
        abs_error) + " relative_error=" + str(relative_error))

def erf_inv_by_adjusting_pmos_nmos_size(complex_routing_inst, inv_name, nmos_size, pmos_size, tar_trans_name, param_dict, hspice, top_spice_path):
    """This function will balance the rise and fall delays of an inverter by either making the NMOS bigger or the PMOS bigger."""

    log = complex_routing_inst.log
    # The first thing we are going to do is increase the PMOS size in fixed increments
    # to get an upper bound on the PMOS size. We also monitor trise. We expect that
    # increasing the PMOS size will decrease trise and increase tfall (because we are making
    # the pull up stronger). If at any time, we see that increasing the PMOS is increasing
    # trise, we should stop increasing the PMOS size. We might be self-loading the inverter.

    if tar_trans_name.endswith("_nmos"):
        tar_trans_size = nmos_size
        another_trans_size = pmos_size
    else:
        tar_trans_size = pmos_size
        another_trans_size = nmos_size

    size_step = min(nmos_size, pmos_size)
    upper_bound_not_found = True
    self_loading = False
    valid_delays = True

    log.info("Looking for %s uppper size bound..." % tar_trans_name)
    previous_trise = float('inf')
    previous_tfall = float('inf')
    while upper_bound_not_found and not self_loading:
        #increase target transistor size and update param_dict
        param_dict[tar_trans_name][0] = tar_trans_size * 1e-9

        #call hspice sims
        spice_meas = hspice.run(top_spice_path, param_dict)

        log.info("the result of spice is %s and the name of inv is %s" % (spice_meas, inv_name))

        #get rise and fall delay results
        tfall_str = spice_meas["meas_" + inv_name + "_tfall"][0]
        trise_str = spice_meas["meas_" + inv_name + "_trise"][0]
        tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)

        #verbose log info for observing erf process in running time
        print_erf_log(tar_trans_name, tfall, trise, another_trans_size, tar_trans_size, log)

        #check whether there is negative delay
        if tfall < 0 or trise < 0:
            log.warning("Negative delay detected during ERF, stop finding upper bound")
            upper_bound_not_found = False
            valid_delays = False
            break

        #determine if a upper bound is found by checking tfall and trise
        #for pmos, tfall > trise means upper bound is found
        if "pmos" in tar_trans_name:
            if tfall > trise:
                upper_bound_not_found = False
                log.info("Upper bound found, %s=%d" % (tar_trans_name, tar_trans_size))
                break
            else:
                #check if trise is decreasing compared to previous trise, if so, self_loading happening
                #todo: adding another condition 'target_tran_size/inv_size > 4'
                if trise >= previous_trise:
                    self_loading = True
                    log.warning("Increasing PMOS is no longer descreasing trise, self loading happening!")
                    break
                previous_trise = trise
        else:
            if trise > tfall:
                upper_bound_not_found = False
                log.info("Upper bound found, NMOS=%d" % tar_trans_size)
                break
            else:
                #check if tfall is decreasing compared to previous tfall, if so, self_loading happening
                if tfall >= previous_tfall:
                    self_loading = True
                    log.warning("Increasing NMOS is no longer descreasing tfall, self loading happening!")
                    break
                previous_tfall = tfall
        #make tar_trans_size larger
        tar_trans_size = tar_trans_size + size_step

    # At this point, we have found an upper bound for our target transistor. If the
    # inverter is self-loaded, we are just going to use whatever transistor size we
    # currently have as the target transistor size. But if the inverter is not self-loaded,
    # we are going to find the precise transistor size that gives balanced rise/fall.
    if valid_delays:
        # The trise/tfall equality occurs in [target_tran_size-inv_size, target_tran_size]
        # To find it, we'll sweep this range in two steps. In the first step, we'll sweep
        # it in increments of min_tran_width. This will allow us to narrow down the range
        # where equality occurs. In the second step, we'll sweep the new smaller range with
        # a 1 nm granularity. This two step approach is meant to reduce runtime, but I have
        # no data proving that it actually does reduce runtime.

        nm_size_lower_bound = tar_trans_size - size_step
        nm_size_upper_bound = tar_trans_size
        interval = complex_routing_inst.specs.min_tran_width

        #create a sweep data list to make hspice sweep sizes
        nm_size_list = []
        current_nm_size = nm_size_lower_bound
        while current_nm_size <= nm_size_upper_bound:
            nm_size_list.append(current_nm_size)
            current_nm_size = current_nm_size + interval

        # Normally when we change transistor sizes, we should recalculate areas
        # and wire RC to account for the change. In this case, however, we are going
        # to make the simplifying assumption that the changes we are making will not
        # have a significant impact on area and on wire lengths. Thus, we save CPU time
        # and just use the same wire RC for this part of the algorithm.
        #
        # So what we are going to do here is use the parameter_dict that we defined earlier
        # in this function to populate a new parameter dict for the HSPICE sweep that we
        # want to do. All parameters will keep the same value as the one in parameter_dict
        # except for the target transistor that we want to sweep.
        sweep_param_dict = create_hspcie_sweep_data(param_dict, tar_trans_name, nm_size_list)

        #call hspice to sweep sizes
        spice_meas = hspice.run(top_spice_path, sweep_param_dict)

        #find the ranges that trise is less than tfall for the first time, if pmos need to be resized, vice versa
        
        log.info("the length of nm_size_list is %d, the result list is %s" % (len(nm_size_list), spice_meas["meas_" + inv_name + "_tfall"]))
        for i in range(len(nm_size_list)):
            tfall_str = spice_meas["meas_" + inv_name + "_tfall"][i]
            trise_str = spice_meas["meas_" + inv_name + "_trise"][i]
            #up to here, measure reasults shouldn't be "failed"
            assert tfall_str != "failed" and trise_str != "failed"
            tfall = float(tfall_str)
            trise = float(trise_str)
            assert tfall > 0 and trise > 0

            if "pmos" in tar_trans_name:
                if tfall > trise:
                    nm_size_upper_bound = nm_size_list[i]
                    nm_size_lower_bound = nm_size_list[i-1]
                    break
            else:
                if trise > tfall:
                    nm_size_upper_bound = nm_size_list[i]
                    nm_size_lower_bound = nm_size_list[i-1]
                    break

        assert nm_size_lower_bound < nm_size_upper_bound
        log.info("Tighten searching range, fall-rise balanced size is between (%d, %d)" % (nm_size_lower_bound, nm_size_upper_bound))

        # We know that ERF is in between nm_size_lower_bound and nm_size_upper_bound
        # Now we'll sweep this interval with a nano-meter granularity step.
        # from experimental results, i think 15 sweeps is enough
        interval = (nm_size_upper_bound - nm_size_lower_bound) / 5
        # create a sweep list we want to try
        nm_size_list = []
        current_nm_size = nm_size_lower_bound
        while current_nm_size <= nm_size_upper_bound:
            nm_size_list.append(current_nm_size)
            current_nm_size = current_nm_size + interval

        #prepare sweep data for hspice sims
        log.info("Calling hspice to sweeping sizes %s for %s" % (nm_size_list, tar_trans_name))
        sweep_param_dict = create_hspcie_sweep_data(param_dict, tar_trans_name, nm_size_list)

        #call hspice sims
        spice_meas = hspice.run(top_spice_path, sweep_param_dict)

        # This time around, we want to select the PMOS size that makes the difference
        # between trise and tfall as small as possible. (we know that the minimum
        # was in the interval we just swept)
        current_rf_error = float("inf")
        best_index = 0
        for i in range(len(nm_size_list)):
            log.info("the length of nm_size_list is %d, the result list is %s" % (len(nm_size_list), spice_meas["meas_" + inv_name + "_tfall"]))
            tfall_str = spice_meas["meas_" + inv_name + "_tfall"][i]
            trise_str = spice_meas["meas_" + inv_name + "_trise"][i]
            assert tfall_str != "failed" and trise_str != "failed"
            tfall = float(tfall_str)
            trise = float(trise_str)
            assert tfall > 0 and trise > 0
            rf_error = abs(tfall - trise)
            if rf_error < current_rf_error:
                current_rf_error = rf_error
                best_index = i
        tar_trans_size = nm_size_list[best_index]
        best_tfall =float(spice_meas["meas_" + inv_name + "_tfall"][best_index])
        best_trise =float(spice_meas["meas_" + inv_name + "_trise"][best_index])

        relative_error = abs(best_tfall - best_trise) / min(best_tfall, best_trise)
        log.info("Choose size %s for %s, tfall=%s, trise=%s, relative_error=%s" % (tar_trans_size, tar_trans_name, best_tfall, best_trise, relative_error))
    else:
        log.warning("Invalid delays(negative): tfall=%s trise=%s", tfall, trise)


    return tar_trans_size


def erf_inverter(complex_routing_inst, inv_name, nmos_size, pmos_size, param_dict, hspice, erf_spice_file):
    """equalize the rise and fall times of an inverter by increasing or descreasing the size of the nmos or pmos sizes"""

    log = complex_routing_inst.log
    nmos_name = inv_name + "_nmos"
    pmos_name = inv_name + "_pmos"
    nmos_size = nmos_size * complex_routing_inst.specs.min_tran_width # in the form of nm, not final value used by hspice which should *1e-9
    pmos_size = pmos_size * complex_routing_inst.specs.min_tran_width

    #there are multiple spice files needed to be simulated. 
    #First, choose the erf_spice_file_list[0] as simulation file to guide the erf sizing of inverter.
    #Then, for every other spice files, do hspice simulation in the basis of the rf_ratio got from first step.
    #Third, check total delay("meas_total_delay") of other simulation. If more than a half(a reasonable proportion) are severely skewed, 
    #choose a spice file within those severely skewed ones as the guidance for re-ref.
    #Accepting condition is when total delay of all spice files are reasonable(20%?)
    #Give a warning when accepting condition not met


    #for spice_file_path in erf_spice_file_list:
    if type(erf_spice_file) != str:
        print(erf_spice_file)
    hspice_meas = hspice.run(erf_spice_file, param_dict)
    tfall_str = hspice_meas["meas_" + inv_name + "_tfall"][0]
    trise_str = hspice_meas["meas_" + inv_name + "_trise"][0]
    #check whether hspice sim failed
    tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)

    #if tfall and trise is close, no need to perform erf
    rf_error = abs(tfall - trise) / min(tfall, trise)
    if rf_error < RF_ERROR_TOLERANCE / 2:
        log.info("Error between tfall and trise for %s is within %f(%f), no need to erf" % (inv_name, RF_ERROR_TOLERANCE, rf_error))
        nmos_size = float(nmos_size) / complex_routing_inst.specs.min_tran_width
        pmos_size = float(pmos_size) / complex_routing_inst.specs.min_tran_width
        return nmos_size, pmos_size

    # If the rise time is faster, nmos must be made bigger.
    # If the fall time is faster, pmos must be made bigger.
    if trise > tfall:
        pmos_size = erf_inv_by_adjusting_pmos_nmos_size(complex_routing_inst, inv_name, nmos_size, pmos_size, pmos_name, param_dict, hspice, erf_spice_file)
        # update param_dict
        param_dict[pmos_name][0] = pmos_size * 1e-9
        # update complex_routing_inst object's attribute transistor_sizes
        complex_routing_inst.transistor_sizes[pmos_name] = (float(pmos_size) / complex_routing_inst.specs.min_tran_width)

        log.info("%s has equalized, NMOS=%s, PMOS=%s" % (pmos_name, nmos_size, pmos_size))
    else:
        nmos_size = erf_inv_by_adjusting_pmos_nmos_size(complex_routing_inst, inv_name, nmos_size, pmos_size, nmos_name, param_dict, hspice, erf_spice_file)
        # update param_dict
        param_dict[nmos_name][0] = nmos_size * 1e-9
        # update complex_routing_inst object's attribute transistor_sizes
        complex_routing_inst.transistor_sizes[nmos_name] = (float(nmos_size) / complex_routing_inst.specs.min_tran_width)

        log.info("%s has equalized, NMOS=%s, PMOS=%s" % (nmos_name, nmos_size, pmos_size))

    #update nmos_size and pmos_size
    nmos_size = float(nmos_size) / complex_routing_inst.specs.min_tran_width
    pmos_size = float(pmos_size) / complex_routing_inst.specs.min_tran_width
    return nmos_size, pmos_size

def erf_combo(complex_routing_inst, transistors_names, middle_size_combination, hspice, erf_spice_file_list):
    """ Equalize the rise and fall of all inverters in a transistor sizing combination.
		Returns the inverter ratios that give equal rise and fall for this combo. """
    log = complex_routing_inst.log

    #update transistor sizes for complex_routing_inst object
    complex_routing_inst.update_transistor_sizes(transistors_names, middle_size_combination)

    #update complex routing
    complex_routing_inst.update_itself()

    #generate the parameters dict needed by hspice sims, including the sizes of all the transistors and RC data
    param_dict = {}
    for trans_name, size in complex_routing_inst.transistor_sizes.items():
        param_dict[trans_name] = [size * complex_routing_inst.specs.min_tran_width * 1e-9]
    for wire_name, rc_data in complex_routing_inst.wire_rc_dict.items():
        param_dict[wire_name + "_res"] = [rc_data[0]]
        param_dict[wire_name + "_cap"] = [rc_data[1] * 1e-15]

    #get inverter names
    inv_names_list = []
    for i in range(len(transistors_names)):
        sizing_primitive_name = transistors_names[i]
        primitive_size = middle_size_combination[i]
        if sizing_primitive_name.startswith("inv_"):
            #this tuple means (inverter name, nmos_size, pmos_size), implying pn_ratio default to 1 which is reasonable as initial value
            inv_names_list.append((sizing_primitive_name, primitive_size, primitive_size))

    iter_cnt = 0
    max_iter_cnt = 4
    accepted = False
    while not accepted:
        if iter_cnt == max_iter_cnt:
            log.warning("Pn ratios is not well refed")
            break
        accepted = True

        if iter_cnt == 0:
            spice_file_path = erf_spice_file_list[0]
        else:
            # choose one of spice path that is within the severely skewed ones
            spice_file_path = most_severely_skewed_one

        log.info("Iteration #%d with %s as guidance spice file\n+++++++++++++++++++++" % (iter_cnt + 1, os.path.basename(spice_file_path)))

        #erf all inverters, that is 2
        for i in range(len(inv_names_list)):
            inv_name, nmos_size, pmos_size = inv_names_list[i]

            log.info("Equalize rf for inverter %s, current NMOS=%s, current PMOS=%s" % (inv_name, nmos_size, pmos_size))
            nmos_size, pmos_size = erf_inverter(complex_routing_inst, inv_name, nmos_size, pmos_size, param_dict, hspice, spice_file_path)
            log.info("Equalize %s completed!" % inv_name)
            if nmos_size < 1 or pmos_size < 1:
                print(nmos_size + pmos_size)
            #update inv_name_list
            inv_names_list[i] = (inv_name, nmos_size, pmos_size)

        # At this point, all inverters have been ERFed.
        # Parameter dict, and the FPGA object itself both contain the ERFed transistor sizes.
        # check meas_total_delay of every other spice file
        log.info("With the above pn ratios, check whether the tfall and trise of other associated spice files are balanced!")
        if len(erf_spice_file_list) > 0:
            total_delay_results = []
            pool = utils.get_parallel_num(len(erf_spice_file_list))
            for spice_path in erf_spice_file_list:
                #spice_file_index = erf_spice_file_list.index(spice_path)
                total_delay_results.append((pool.apply_async(utils.hspice_task, args=(hspice, spice_path, param_dict,)), spice_path))
            pool.close()
            pool.join()
            total_delay_results = [(i[0].get(), i[1]) for i in total_delay_results]
            for i in range(len(total_delay_results)):
                tfall_str = total_delay_results[i][0]["meas_total_tfall"][0]
                trise_str = total_delay_results[i][0]["meas_total_trise"][0]
                tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)
                rf_error = abs(tfall - trise) / min(tfall, trise)
                total_delay_results[i] = (rf_error, total_delay_results[i][1])

            # get those spice files that are severely skewed
            # severely skewed spice files
            severely_skewed_spice_files = []
            most_severely_skewed_one = ""
            tmp_error = 0
            for a, b in total_delay_results:
                if a > RF_ERROR_TOLERANCE:
                    severely_skewed_spice_files.append(b)
                if a > tmp_error:
                    tmp_error = a
                    most_severely_skewed_one = b

            # check accpeting condition
            if len(severely_skewed_spice_files) > math.floor(len(erf_spice_file_list) / float(2)):
                log.info("Above pn ratios rejected by other associated spice files, (%s severely unbalanced)re-erf..." % len(severely_skewed_spice_files))
                accepted = False

        iter_cnt = iter_cnt + 1
    log.info("Above pn ratios accepted by other associated spice files")
    """
    spice_meas_list = []
    pool = utils.get_parallel_num(len(erf_spice_file_list))
    for i in range(len(erf_spice_file_list)):
        spice_path = erf_spice_file_list[i]
        spice_meas_list.append((pool.apply_async(utils.hspice_task, args=(hspice, erf_spice_file_list[i], param_dict,)), spice_path))
    pool.close()
    pool.join()
    spice_meas_list = [i[0].get() for i in spice_meas_list]

    for spice_meas, spice_path in spice_meas_list:
        log.info("ERF inverters for %s completed!" % os.path.basename(spice_path))
        # Check the trise/tfall error of all inverters and if at least one of them
        # doesn't meet the ERF tolerance, we'll set the erf_tolerance_met flag to false
        for trans_name in transistors_names:
            if not trans_name.startswith("inv_"):
                continue

            #get measure results
            tfall_str = spice_meas["meas_" + trans_name + "_tfall"][0]
            trise_str = spice_meas["meas_" + trans_name + "_trise"][0]
            tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)
            rf_error = abs(tfall - trise) / min(tfall, trise)

            #log sizing info
            nmos_nm_size = int(param_dict[trans_name + "_nmos"][0] * 1e9)
            pmos_nm_size = int(param_dict[trans_name + "_pmos"][0] * 1e9)
            log.info("%s (N=%d P=%d tfall=%.4e trise=%.4e rf_error=%.3f%%)" % (trans_name, nmos_nm_size, pmos_nm_size, tfall, trise, 100*round(rf_error, 4)))
    """
    #get erf ratios
    erf_ratios = {}
    for trans_name in transistors_names:
        if trans_name.startswith("inv_"):
            pmos_size = complex_routing_inst.transistor_sizes[trans_name + "_pmos"]
            nmos_size = complex_routing_inst.transistor_sizes[trans_name + "_nmos"]
            erf_ratios[trans_name] = float(pmos_size) / nmos_size
    return erf_ratios

def run_single_sizing_comb(complex_routing_inst, transistor_names, sizing_combination, pn_ratios, hspice,
                           top_spice_path_list):
    """ Run HSPICE to measure delay for this transistor sizing combination. Returns tfall, trise """
    # update complex routing object
    complex_routing_inst.update_transistor_sizes(transistor_names, sizing_combination, pn_ratios)
    complex_routing_inst.update_itself()

    # prepare parameter dict
    param_dict = {}
    for trans_name, size in complex_routing_inst.transistor_sizes.items():
        param_dict[trans_name] = [size * complex_routing_inst.specs.min_tran_width * 1e-9]
    for wire_name, rc_data in complex_routing_inst.wire_rc_dict.items():
        param_dict[wire_name + "_res"] = [rc_data[0]]
        param_dict[wire_name + "_cap"] = [rc_data[1] * 1e-15]

    # call hspice in parallel
    spice_meas_list = []
    pool = utils.get_parallel_num(len(top_spice_path_list))
    for spice_path in top_spice_path_list:
        spice_meas_list.append(pool.apply_async(utils.hspice_task, args=(hspice, spice_path, param_dict,)))
    pool.close()
    pool.join()
    spice_meas_list = [i.get() for i in spice_meas_list]
    
    tfall_trise_list = []
    for i in range(len(top_spice_path_list)):
        spice_meas = spice_meas_list[i]
        tfall = float(spice_meas["meas_total_tfall"][0])
        trise = float(spice_meas["meas_total_trise"][0])
        tfall_trise_list.append((tfall, trise))

    return tfall_trise_list

def search_sizing_solution(sizing_ranges, sizes_on_the_boundary, complex_routing_inst, routing_mux_inst, area_opt_weight, delay_opt_weight, hspice):
    """"""
    log = complex_routing_inst.log

    # apply Descartes product to sizing ranges, this will produce all possible sizing combinations
    transistor_names_under_sizing, sizing_combinations = expand_ranges(sizing_ranges, sizes_on_the_boundary)

    # find sizing combinations that is at the middle of all ranges
    middle_size_combo = get_middle_sizing_combination(transistor_names_under_sizing, sizing_ranges)

    # get associated segment profiles that have the mux as the driver mux or load mux with enough proportion
    # then, get spice paths for doing get pn ratios and simulating all sizing combs
    associated_segs = complex_routing_inst.get_segs_by_routing_mux(routing_mux_inst)
    if len(associated_segs) == 0:
        return (float("inf"), {}, {}, 0, 0, 0, 0)

    spice_path_list = [i.top_spice_path for i in associated_segs]
    erf_spice_path_list = []
    erf_spice_path_index_list = []
    mux_name = routing_mux_inst.name
    for i in range(len(spice_path_list)):
        spice_path = spice_path_list[i]
        if mux_name in os.path.basename(spice_path):
            erf_spice_path_list.append(spice_path)
            erf_spice_path_index_list.append(i)

    # find erf ratios for middle size combination
    # some mux does not need to be ref-ed, because there is no top spice file
    # ready for measuring it, it is just as fanout mux but not driver mux
    # Because there is possibility not parsing rrg completedly(seldom)!
    erf_ratios = None
    erf_flag = False
    if len(erf_spice_path_list) > 0:
        log.info("Find pn ratios for %s with middle sizing combination %s\n++++++++++++++++++++++++" % (mux_name, middle_size_combo))
        erf_ratios = erf_combo(complex_routing_inst, transistor_names_under_sizing, middle_size_combo, hspice, erf_spice_path_list)
        erf_flag = True

    # For each transistor sizing combination, re-calculate area, wire sizes, and wire R and C
    area_list = []
    wire_rc_list = []
    delay_list = []
    for sizing_comb in sizing_combinations:
        if erf_flag:
            complex_routing_inst.update_transistor_sizes(transistor_names_under_sizing, sizing_comb, erf_ratios)
        else:
            erf_flag = None
            complex_routing_inst.update_transistor_sizes(transistor_names_under_sizing, sizing_comb, None)
        complex_routing_inst.update_itself()
        area_list.append(complex_routing_inst.get_routing_area())
        wire_rc_list.append(complex_routing_inst.wire_rc_dict)
        delay_list.append([])
    
    #prepare param_dict for hspice sims
    current_trans_sizes = {}
    for trans_name, size in complex_routing_inst.transistor_sizes.items():
        current_trans_sizes[trans_name] = 1e-9 * size * complex_routing_inst.specs.min_tran_width
    param_dict = {}
    for trans_name in current_trans_sizes.keys():
        param_dict[trans_name] = []
    for wire_name in wire_rc_list[0].keys():
        param_dict[wire_name + "_res"] = []
        param_dict[wire_name + "_cap"] = []
    
    for i in range(len(sizing_combinations)):
        for trans_name, size in current_trans_sizes.items():
            pruned_trans_name = trans_name.replace("_nmos", "")
            pruned_trans_name = pruned_trans_name.replace("_pmos", "")
            
            if pruned_trans_name in transistor_names_under_sizing:
                index = transistor_names_under_sizing.index(pruned_trans_name)

                size = 1e-9 * sizing_combinations[i][index] * complex_routing_inst.specs.min_tran_width

                if pruned_trans_name.startswith("inv_"):
                    if trans_name.endswith("_nmos"):
                        if erf_flag:
                            if erf_ratios[pruned_trans_name] < 1:
                                nmos_size = float(size) / erf_ratios[pruned_trans_name]
                            else:
                                nmos_size = size
                        else:
                            nmos_size = size
                        param_dict[trans_name].append(nmos_size)
                    else:
                        if erf_flag:
                            if erf_ratios[pruned_trans_name] < 1:
                                pmos_size = size
                            else:
                                pmos_size = size * erf_ratios[pruned_trans_name]
                        else:
                            pmos_size = size
                        param_dict[trans_name].append(pmos_size)
                  
                else:
                    param_dict[trans_name].append(size)
            else:
                param_dict[trans_name].append(size)
        for wire_name, rc_data in wire_rc_list[i].items():
            param_dict[wire_name + "_res"].append(rc_data[0])
            param_dict[wire_name + "_cap"].append(rc_data[1] * 1e-15)

    #running hspice parallel
    log.info("Running hspice sims(%d tasks) for %s with %d sizing combinations..." % (len(associated_segs) ,mux_name, len(sizing_combinations)))
    start_t = time.time()
    spice_meas_list = []
    pool = utils.get_parallel_num(len(associated_segs))
    for spice_path in spice_path_list:
        spice_meas_list.append(pool.apply_async(utils.hspice_task, args=(hspice, spice_path, param_dict,)))
    pool.close()
    pool.join()
    end_t = time.time()
    log.info("Hspice sims(%d tasks) for %s with %d sizing combinations costs %f seconds" % (len(associated_segs) ,mux_name, len(sizing_combinations), (end_t - start_t)))

    #get total delay for each sizing combination
    spice_meas_list = [i.get() for i in spice_meas_list]
    
    # log.info("the result of spice is %s and the size of sizing_combination is %d" % (spice_meas_list, len(sizing_combinations)))
    for i in range(len(sizing_combinations)):
        for spice_meas in spice_meas_list:
            if len(spice_meas["meas_total_tfall"]) <= i:
                log.info("the result of spice is %s and the size of sizing_combination is %d" % (spice_meas_list, len(sizing_combinations)))
            tfall_str = spice_meas["meas_total_tfall"][i]
            trise_str = spice_meas["meas_total_trise"][i]
            tfall, trise = utils.valid_delay_results(tfall_str, trise_str, log)
            delay_list[i].append((tfall, trise))

    # Calculate cost based on area and delay and their weight
    cost_list = []
    for i in range(len(delay_list)):
        area = area_list[i]
        assert len(associated_segs) == len(delay_list[i])
        delay = get_weighted_routing_delay(complex_routing_inst, associated_segs, delay_list[i]) # the average is more appropriate because it could reflect the impact of change sizes to delay
        cost = get_cost(area, area_opt_weight, delay, delay_opt_weight)
        cost_list.append((cost, i, delay))

    cost_list.sort()

    #get top 5 results
    log.info("\n Top 5 best cost results\n++++++++++++++++++++++++++++++")
    for i in range(min(5, len(cost_list))):
        comb_index = cost_list[i][1]
        tfall, trise = 0, 0
        if len(erf_spice_path_index_list) > 0:
            for index in erf_spice_path_index_list:
                tfall = tfall + delay_list[comb_index][index][0]
                trise = trise + delay_list[comb_index][index][1]
            tfall = tfall / len(erf_spice_path_index_list)
            trise = trise / len(erf_spice_path_index_list)
        log.info("Sizing combination: " + str(sizing_combinations[comb_index]) +
                 "\n    cost: " + str(cost_list[i][0]) +
                 "\n    area: " + str(area_list[comb_index]) +
                 "\n    tfall: " + str(tfall) +
                 "\n    trise: " + str(trise) +
                 "\n    weighted_routing_path_delay: " + str(cost_list[i][2]) + 
                 "\n    pn_ratios=" + str(erf_ratios))

    #re-erf top 3 sizing combinations
    best_results = []
    for i in range(3):
        comb_index = cost_list[i][1]
        sizing_comb = sizing_combinations[comb_index]
        log.info("\nRe-equalizing rise and fall times on sizing combination: " + str(sizing_comb) + "(now ranked #" + str(i + 1) + ")")

        if len(erf_spice_path_list) > 0:
            erf_ratios = erf_combo(complex_routing_inst, transistor_names_under_sizing, sizing_comb, hspice, erf_spice_path_list)

        #apply this sizing combination to all associated segment profile, call hspcice, so the 'associated_segs' not the 'erf_spice_path_list'
        delay_results = run_single_sizing_comb(complex_routing_inst, transistor_names_under_sizing, sizing_comb, erf_ratios, hspice, spice_path_list)

        #note that area has been updated due to re-ref
        area = complex_routing_inst.get_routing_area()
        delay = get_weighted_routing_delay(complex_routing_inst, associated_segs, delay_results)
        cost = get_cost(area, area_opt_weight, delay, delay_opt_weight)

        tfall, trise = 0, 0
        if len(erf_spice_path_index_list) > 0:
            for index in erf_spice_path_index_list:
                tfall = tfall + delay_results[index][0]
                trise = trise + delay_results[index][1]
            tfall = tfall / len(erf_spice_path_index_list)
            trise = trise / len(erf_spice_path_index_list)

        best_results.append((cost, sizing_comb, area, delay, tfall, trise, erf_ratios))

    #sort newly best results
    best_results.sort()

    log.info("3 BEST COST RESULTS AFTER RE-BALANCING\n+++++++++++++++++++++++++++")
    for result in best_results:
        log.info("Combo #" + str(result[1]) +
                 "\n    cost=" + str(round(result[0], 6)) +
                 "\n    area=" + str(result[2]) +
                 "\n    tfall=" + str(result[4]) +
                 "\n    trise=" + str(result[5]) + 
                 "\n    weighted_routing_path_delay=" + str(result[3]) + 
                 "\n    pn_ratios=" + str(result[6]))

    #udpate complex_routing_inst with best sizing combs
    best_result = best_results[0]
    complex_routing_inst.update_transistor_sizes(transistor_names_under_sizing, best_result[1], best_result[-1])
    complex_routing_inst.update_itself()
    complex_routing_inst.update_delays(hspice)

    # return the sizing combination which contain all NMOS and PMOS values because the sizing combination
    # have to be valid(size not on the boundary)
    best_comb_detailed = {}
    best_comb_dict = {}
    best_comb = best_result[1]
    print(best_result)
    for i in range(len(transistor_names_under_sizing)):
        trans_name = transistor_names_under_sizing[i]
        if "ptran_" in trans_name:
            best_comb_dict[trans_name] = best_comb[i]
            best_comb_detailed[trans_name + "_nmos"] = best_comb[i]
        elif "rest_" in trans_name:
            best_comb_dict[trans_name] = best_comb[i]
            best_comb_detailed[trans_name + "_pmos"] = best_comb[i]
        elif "inv_" in trans_name:
            best_comb_dict[trans_name] = best_comb[i]
            if erf_ratios:
                if best_result[-1][trans_name] < 1:
                    best_comb_detailed[trans_name + "_nmos"] = best_comb[i] / best_result[-1][trans_name]
                    best_comb_detailed[trans_name + "_pmos"] = best_comb[i]
                else:
                    best_comb_detailed[trans_name + "_nmos"] = best_comb[i]
                    best_comb_detailed[trans_name + "_pmos"] = best_comb[i] * best_result[-1][trans_name]
            else:
                best_comb_detailed[trans_name + "_nmos"] = best_comb[i]
                best_comb_detailed[trans_name + "_pmos"] = best_comb[i]


    #return best sizing results
    best_cost = best_result[0]
    best_area = best_result[2]
    best_weight_delay = best_result[3]
    best_delay = (best_result[4], best_result[5])
    best_pn_ratios = best_result[-1]
    
    return (best_cost, best_comb_dict, best_comb_detailed, best_area, best_weight_delay, best_delay, best_pn_ratios)

def update_sizing_ranges(sizing_ranges, sizing_results, log):
    """ This function does two things. First, it checks whether the transistor sizing results are valid.
    	That is, if the results are on the boundaries of the ranges, they are not valid. In this case,
    	the function will adjust 'sizing_ranges' around the 'sizing_results'
    	Returns: True if 'sizing_results' are valid, False otherwise."""

    valid_sizes = True
    sizes_on_the_boundary = {}
    for trans_name, result_size in sizing_results.items():
        #exclude level restorer pmos whose size is fixed
        if "rest_" in trans_name:
            continue

        min = sizing_ranges[trans_name][0]
        max = sizing_ranges[trans_name][1]

        #on the upper boundary
        if result_size == max:
            valid_sizes = False
            #update range with growing sizes based on max
            min = max
            max = max + 2
            log.info("Updating sizing ranges of %s:%s --> %s" % (trans_name, sizing_ranges[trans_name], (min, max, False)))
            sizing_ranges[trans_name] = (min, max, False)
            sizes_on_the_boundary[trans_name] = min
        #on the lower boundary
        elif result_size == min:
            #when min is 1(the lowest possible size, no need to update size)
            if min > 1:
                valid_sizes = False
                #update range with shrinking sizs based on min
                max = min
                min = min - 2
                if min < 1:
                    min = 1
                    max = 3
                log.info("Updating sizing ranges of %s:%s --> %s" % (trans_name, sizing_ranges[trans_name], (min, max, False)))
                sizing_ranges[trans_name] = (min, max, False)
                sizes_on_the_boundary[trans_name] = max
            else:
                sizing_ranges[trans_name] = (min, max, True)
        else:
            #make tag to True for those not on the boundary
            sizing_ranges[trans_name] = (min, max, True)
    return valid_sizes, sizes_on_the_boundary


def size_routing_mux_transistors(complex_routing_inst, routing_mux_inst, area_opt_weight, delay_opt_weight, sizing_transistors, hspice):
    """size transistors of routing mux"""
    log = complex_routing_inst.log

    #transistors sizing ranges
    sizing_ranges = find_initial_sizing_ranges(sizing_transistors)

    #list to store each sizing results for every tried sizing ranges, later sizing ranges may not better than previous one
    sizing_results_list = []
    sizes_on_the_boundary = {}
    last_best_cost = float("inf")

    #keep sizing until all sizes are valid(not on the boundary)
    valid_sizes = False

    mux_name = routing_mux_inst.name
    iter_cnt = 0

    while not valid_sizes:
        if iter_cnt > 3:
            log.info("Sizing iteration reached %d, stop!" % (iter_cnt - 1))
            break
        log.info("Sizing iteration #%d for %s with sizing ranges %s...(be patient)\n+++++++++++++++++++++++++" % (iter_cnt + 1, mux_name, sizing_ranges))
        #sizing_results in the form of (cost, sizing_comb, sizing_comb_detailed, area, weighted_delay, delay, pn_ratios)
        sizing_results = search_sizing_solution(sizing_ranges, sizes_on_the_boundary, complex_routing_inst, routing_mux_inst, area_opt_weight, delay_opt_weight, hspice)

        if iter_cnt > 0:
            previous_cost = sizing_results_list[-1][0]
            current_cost = sizing_results[0]
            if current_cost < previous_cost:
                #previous sizing ranges change produce better results
                sizing_results_list.append(sizing_results)
                valid_sizes, sizes_on_the_boundary = update_sizing_ranges(sizing_ranges, sizing_results[1], log)
            else:
                #refuse the previous sizing ranges change, because it does not produce better results
                #todo: is it resonable to think the previous sizing solution is the best when the current one is worse than the previous?
                #   should try another sizing ranges!!
                valid_sizes = True
        else:
            sizing_results_list.append(sizing_results)
            valid_sizes, sizes_on_the_boundary = update_sizing_ranges(sizing_ranges, sizing_results[1], log)

        iter_cnt = iter_cnt + 1
    log.info("Sizing %s completed!" % mux_name)

    #update complex routing inst with final best sizing solution
    best_sizing_comb = sizing_results_list[-1][1]
    best_inv_ratios = sizing_results_list[-1][-1]
    complex_routing_inst.update_transistor_sizes(list(best_sizing_comb.keys()), list(best_sizing_comb.values()), best_inv_ratios)
    complex_routing_inst.update_itself()
    complex_routing_inst.update_delays(hspice)

    return sizing_results_list[-1]
    

def size_routing_transistors(complex_routing_inst, run_options, hspice):
    """"""

    seg_profiles = complex_routing_inst.seg_profiles
    log = complex_routing_inst.log

    area_opt_weight = run_options.area_opt_weight
    delay_opt_weight = run_options.delay_opt_weight
    max_iterations = run_options.max_iterations

    #create sizing results folder
    if not os.path.exists("sizing_results"):
        os.makedirs("sizing_results")

    log.info("Starting transistor sizing...\n+++++++++++++++++++++++++++++++++\n")

    # there are certain number of muxes of different type(different fanin, driving different wire segment),
    # and each type of mux has different level of impact to routing area and delay. Intuitively, a type of mux
    # of more quantity in the routing channel is likely to impact routing area and delay more significantly.
    # So, i size the muxes by the order of the quantity in a tile which can be referenced from attribute num_per_tile
    # of each mux(num_per_tile equal to -1 means this type of mux doesn't exist on the selected tile, and i just consider
    # it less important).
    # Sizing process:
    #               1, choose most significant mux to size
    #               2, keep searching sizing ranges, until a optimal solution is included
    #               3, equalize rise and fall delay times of buffer
    #               4, sweep all sizing compositions and call hspice sims for every segment profile
    #               5, determine the most optimal sizing solution of this mux
    #               6, choose less significant mux to size...
    #               ...
    # A sizing iteration means all type of muxes have been sized. The subsequent sizing iteration is necessary to undertake,
    # in order to find better sizing solution for each type of mux. However, if the subsequent sizing iteration doesn't find
    # a better solution for a particular type of mux than last iteration, the algrithm will bypass it in the following iteration,
    # because algrithm thinks this type of mux is well sized enough. When all mux is well sized enough in a sizing iteration,
    # the sizing algrithm will terminate

    # a dict to store a tag to indicate whether a mux is well sized enough
    well_sized_tag = {}
    for mux in complex_routing_inst.muxes.values():
        mux_name = mux.name
        well_sized_tag[mux_name] = False


    # sort muxes by the quantity
    muxes = sorted(complex_routing_inst.muxes.values(), key=lambda x : x.num_per_tile, reverse=True)

    # the following list store sizing results for each sizing iteration
    sizing_results_dict = {}
    sizing_results_detailed = {}
    area_results_list = []
    delay_results_dict = {}
    weighted_delay_results_list = []
    cost_results_list = []
    pn_ratios_dict = {}

    iteration_index = 0

    #initialize complex routing delays
    complex_routing_inst.update_delays(hspice)

    #copy the original data, to verify the validility of sizing algrithm
    previous_cost = get_cost(complex_routing_inst.get_routing_area(), area_opt_weight, complex_routing_inst.get_routing_delay(), delay_opt_weight)
    org_transistor_sizes = copy.deepcopy(complex_routing_inst.transistor_sizes)
    org_weighted_delay = copy.deepcopy(complex_routing_inst.delay_dict["weighted_routing_delay"])
    org_area = copy.copy(complex_routing_inst.get_routing_area())

    #trace of sizing mux
    trace_sizing_mux_list = []

    start_t_g = time.time()
    while not utils.check_dict_all_true(well_sized_tag):
        if iteration_index >= max_iterations:
            log.info("Sizing algrithm terminated: maximum number of iterations(%d) has been reached" % max_iterations)
            break

        log.info("++++++++++++++Sizing iteration %d+++++++++++++" % iteration_index)

        for mux in muxes:
            mux_name = mux.name

            if not well_sized_tag[mux_name]:
                log.info("\n++++++++++++++++++++++++++++Starting sizing %s...\n++++++++++++++++++++++++++++++++++++++++" % mux_name)
                start_t = time.time()

                assert mux_name in well_sized_tag

                mux_transistor_sizes = {trans_name: complex_routing_inst.transistor_sizes[trans_name] for trans_name in mux.transistor_names}
                mux_transistor_sizes = format_transistor_sizes_to_sizing_primitives(mux_transistor_sizes)
                
                sizing_results = size_routing_mux_transistors(complex_routing_inst, mux, area_opt_weight, delay_opt_weight, mux_transistor_sizes, hspice)

                trace_sizing_mux_list.append(mux_name)

                #record the changes of cost, area, and weighted delay when each sizing of the routing mux is finished, 
                #indexed by trace_sizing_mux_list
                if sizing_results == (float("inf"), {}, {}, 0, 0, 0, 0):
                    cost_results_list.append(cost_results_list[-1])
                    area_results_list.append(area_results_list[-1])
                    weighted_delay_results_list.append(weighted_delay_results_list[-1])

                    sizing_results_dict[mux_name] = sizing_results[1]
                    sizing_results_detailed[mux_name] = sizing_results[2]
                    delay_results_dict[mux_name] = sizing_results[5]
                    pn_ratios_dict[mux_name] = sizing_results[6]
                else:
                    cost_results_list.append(sizing_results[0])
                    area_results_list.append(sizing_results[3])
                    weighted_delay_results_list.append(sizing_results[4])

                    sizing_results_dict[mux_name] = sizing_results[1]
                    sizing_results_detailed[mux_name] = sizing_results[2]
                    delay_results_dict[mux_name]  = sizing_results[5]
                    pn_ratios_dict[mux_name] = sizing_results[6]

                end_t = time.time()
                log.info("sizing %s costs %f seconds" % (mux_name, end_t-start_t))
        iteration_index = iteration_index + 1

    end_t_g = time.time()
    print("initial cost: " + str(previous_cost))
    print("initial area: " + str(org_area))
    print("initial delay: " + str(org_weighted_delay))
    print("total sizing time %.1fm" %((end_t_g - start_t_g) / 60))


    #export transistor sizes
    os.chdir("sizing_results")
    export_sizing_results("final_sizing_results.txt", complex_routing_inst, sizing_results_detailed, delay_results_dict, previous_cost, org_area, org_weighted_delay, cost_results_list[-1])

    # final delay of every seg
    for seg in complex_routing_inst.seg_profiles:
        if hasattr(seg, "top_spice_path"):
            print(seg.seg_name + str(seg.tfall) + str(seg.trise))

    #export trend of cost, area, and delay to a graph
    graph_name = "Area%sDelay%sIter%s" % (area_opt_weight, delay_opt_weight, len(trace_sizing_mux_list)) + ".png"
    export_to_graph(trace_sizing_mux_list, cost_results_list, area_results_list, weighted_delay_results_list, graph_name)

def export_sizing_results(sizing_results_filename, complex_routing_inst, sizing_results_detailed, delay_results_dict, previous_cost, org_area, org_weighted_delay, final_cost):
    """export final sizing results to file"""
    with open(sizing_results_filename, 'w') as fp:
        sizing_mux_names = sorted(sizing_results_detailed.keys())
        fp.write("********************\n*****SIZING RESULTS\n********************\n")
        for mux_name in sizing_mux_names:
            delay = delay_results_dict[mux_name]
            #Indirectly exclude muxes whose attribute is -1, those muxes didn't do transistor sizing and delay is assigned to 0
            if delay != 0:
                mux_sizes = sizing_results_detailed[mux_name]
                if mux_name + "_total" in complex_routing_inst.area_dict:
                    area = complex_routing_inst.area_dict[mux_name + "_total"]
                else:
                    area = None
                
                if (mux_sizes != None) and (area != None):

                    #column width
                    if len(mux_sizes.keys()) == 0:
                        col_width = 50
                    else:
                        col_width = max(map(len, mux_sizes.keys())) + 1

                    #sizes
                    fp.write("%s(area=%.4f, delay=%s): \n" % (mux_name, area, delay))
                    for trans_name, trans_size in mux_sizes.items():
                        fp.write("".join(trans_name.ljust(col_width)) + ": " + str(trans_size) + "\n")
                    fp.write("\n")

        final_area = complex_routing_inst.area_dict["total_routing_area"]
        final_delay = complex_routing_inst.delay_dict["weighted_routing_delay"]
        fp.write("\n*********************\n*****Conclusion\n************************\n")
        fp.write("initial cost: %.4f    final cost: %.4f    diff: %.4f\n" % (previous_cost, final_cost, abs(final_cost-previous_cost)/previous_cost))
        fp.write("initial area: %.4f    final area: %.4f    diff: %.4f\n" % (org_area, final_area, abs(final_area-org_area)/org_area))
        fp.write("initial delay: %s   final delay: %s   diff: %.4f\n" % (org_weighted_delay, final_delay, abs(final_delay-org_weighted_delay)/org_weighted_delay))
    fp.close()

def export_to_graph(trace_sizing_muxes, cost_list, area_list, delay_list, graph_name):
    """with trace_sizing_muxes as x-axis, cost, area, and delay values as y-axis, to generate the trend of these 3 parameters"""

    fig = plt.figure(1, figsize=(10, 5))

    cost = HostAxes(fig, [0.15, 0.1, 0.65, 0.8])
    area = ParasiteAxes(cost, sharex=cost)
    delay = ParasiteAxes(cost, sharex=cost)

    cost.parasites.append(area)
    cost.parasites.append(delay)

    cost.axis['right'].set_visible(False)
    area.axis['right'].set_visible(True)
    area.axis['right'].major_ticklabels.set_visible(True)
    area.axis['right'].label.set_visible(True)

    cost.set_xlabel('Muxes')
    cost.set_ylabel('Cost')
    area.set_ylabel('Area')
    delay.set_ylabel('Delay')

    offset = (60, 0)
    new_axisline = delay.get_grid_helper().new_fixed_axis
    delay.axis['right2'] = new_axisline(loc='right', axes=delay, offset=offset)

    fig.add_axes(cost)

    x = range(len(trace_sizing_muxes))
    p1, = cost.plot(x, cost_list, label="Cost", color="black")
    p2, = area.plot(x, area_list, label="Area", color="red")
    p3, = delay.plot(x, delay_list, label="Delay", color="green")
    #plt.xticks(x, trace_sizing_muxes, rotation=90, fontsize=1)

    #area.set_ylim(0,4)
    #delay.set_ylim(1,55)

    cost.legend()

    #color setting
    cost.axis['left'].label.set_color(p1.get_color())

    area.axis['right'].label.set_color(p2.get_color())
    delay.axis['right2'].label.set_color(p3.get_color())

    area.axis['right'].major_ticklabels.set_color(p2.get_color())
    delay.axis['right2'].major_ticklabels.set_color(p3.get_color())

    area.axis['right'].line.set_color(p2.get_color())
    delay.axis['right2'].line.set_color(p3.get_color())

    tmp = plt.gca()
    tmp.yaxis.get_major_formatter().set_powerlimits((0,1),)

    plt.savefig(graph_name)




