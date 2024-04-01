import os
import shutil
import logging
from logging import handlers
import sys
import multiprocessing

CPU_CNT = multiprocessing.cpu_count()

class Logger:
    level_map = {'debug':logging.DEBUG,
                 'info':logging.INFO,
                 'warning':logging.WARNING,
                 'error':logging.ERROR,
                 'critical':logging.CRITICAL}
    
    def __init__(self, file_name, level='info', when='D', backCount=3, fmt='%(asctime)s - %(pathname)s[line:%(lineno)d] - %(levelname)s: %(message)s'):
        self.logger = logging.getLogger(file_name)
        fmt_str = logging.Formatter(fmt)
        self.logger.setLevel(self.level_map.get(level, 'info'))
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        fh = handlers.TimedRotatingFileHandler(filename=file_name, when=when, backupCount=backCount, encoding='utf-8')
        fh.setFormatter(fmt_str)
        self.logger.addHandler(sh)
        self.logger.addHandler(fh)
    def info(self, message):
        self.logger.info(message)
    def error(self, message):
        self.logger.error(message)
        sys.exit(1)
    def warning(self, message):
        self.logger.warning(message)

def create_output_dir(arch_file_name):
    """
    This function created the architecture folder and returns its name
    it also deletes the content of the folder in case it's already created
    to avoid any errors in case of multiple runs on the same architecture file
    """

    arch_desc_words = arch_file_name.split('.')
    arch_folder = arch_desc_words[0]
    if not os.path.exists(arch_folder):
        os.mkdir(arch_folder)
    else:
        # Delete contents of sub-directories
        # COFFE generates several 'intermediate results' files during sizing
        # so we delete them to avoid from having them pile up if we run COFFE
        # more than once.
        dir_contents = os.listdir(arch_folder)
        for content in dir_contents:
            if os.path.isdir(arch_folder + "/" + content):
                shutil.rmtree(arch_folder + "/" + content)
    arch_folder = os.getcwd() + '/' + arch_folder
    return arch_folder

def remove_all_contents(dir_path):
    dir_contents = os.listdir(dir_path)
    for content in dir_contents:
        if os.path.isdir(dir_path + "/" + content):
            shutil.rmtree(dir_path + "/" + content)
        else:
            os.remove(dir_path + "/" + content)
def log_run_options(log, args):
    """ 
    This function prints the run options entered by the user
    when running COFFE, in the terminal and the report file  
    """
    
    log.info("###############################################")
    log.info("#############  RUN OPTIONS:")
    log.info("###############################################")
    if not args.no_sizing:
        log.info("  Transistor sizing: on")
    else:
        log.info("  Transistor sizing: off")
    log.info("  Area optimization weight: " + str(args.area_opt_weight))
    log.info("  Delay optimization weight: " + str(args.delay_opt_weight))
    log.info("  Maximum number of sizing iterations: " + str(args.max_iterations))

def parse_arch_parameters(arch_file, log):
    """parse segment length specification, process parameters, and return a dict"""
    #process parameters expected to find
    arch_params = {
        'segment_length_by_name':{},
        'transistor_type': "",
        'switch_type': "",
        'use_tgate': False,
        'read_to_write_ratio': 1.0,
        'vdd': -1,
        'vsram': -1,
        'vsram_n': -1,
        'vref': 0.627,
        'vdd_low_power': 0.95,
        'gate_length': -1,
        'rest_length_factor': -1,
        'min_tran_width': -1,
        'min_width_tran_area': -1,
        'sram_cell_area': -1,
        'trans_diffusion_length' : -1,
        'model_path': "",
        'model_library': "",
        "metal": []
    }
    with open(arch_file, 'r') as fp:
        segment_length_by_name = {}
        for line in fp:
            #ignore nonsense line
            if line.startswith('#'):
                continue
            line = line.replace('\n', '')
            line = line.replace('\r', '')
            line = line.replace('\t', '')
            line = line.replace(' ', '')
            if line == '':
                continue

            #here is the info needed
            param, value = line.split('=')

            if param.startswith('segment'):
                # get segment length specification
                segment_length_by_name[param.replace('segment_', '',1)] = int(value)
            else:
                #add process param
                if not param in arch_params.keys():
                    log.error("Found invalid architecture parameter (" + param + ") in" + arch_file)
                    sys.exit()

                if param == 'transistor_type':
                    arch_params[param] = value
                elif param == 'switch_type':
                    arch_params[param] = value
                    if value == 'transmission_gate':
                        arch_params['use_tgate'] = True
                elif param == 'vdd':
                    arch_params[param] = float(value)
                elif param == 'vsram':
                    arch_params[param] = float(value)
                elif param == 'vsram_n':
                    arch_params[param] = float(value)
                elif param == 'gate_length':
                    arch_params[param] = int(value)
                elif param == 'rest_length_factor':
                    arch_params[param] = int(value)
                elif param == 'min_tran_width':
                    arch_params[param] = int(value)
                elif param == 'trans_diffusion_length':
                    arch_params[param] = int(value)
                elif param == 'min_width_tran_area':
                    arch_params[param] = int(value)
                elif param == 'sram_cell_area':
                    arch_params[param] = int(value)
                elif param == 'model_path':
                    arch_params[param] = value
                elif param == 'model_library':
                    arch_params[param] = value
                elif param == 'metal':
                    value_words = value.split(',')
                    r = value_words[0].replace(' ', '')
                    r = r.replace(' ', '')
                    r = r.replace('\n', '')
                    r = r.replace('\r', '')
                    r = r.replace('\t', '')
                    c = value_words[1].replace(' ', '')
                    c = c.replace(' ', '')
                    c = c.replace('\n', '')
                    c = c.replace('\r', '')
                    c = c.replace('\t', '')
                    arch_params[param].append((float(r), float(c)))
        arch_params['segment_length_by_name'] = segment_length_by_name
    fp.close()
    #check every parameter is not none
    for param, value in arch_params.items():
        if value == -1 or value == '':
            log.error("Architecture parameter " + param + " not found in " + arch_file)
            sys.exit()

    #log parameters
    log.info("#######################################")
    log.info("###### parameters read")
    log.info("#######################################")
    for param, value in arch_params.items():
        log.info(param + ": " + str(value))

    return  arch_params

def segid_to_name(seg_id, lookup):
    """transfrom segment id to its string name"""
    if lookup.get(seg_id, None) is None:
        return str(seg_id)
    else:
        return lookup[seg_id]

def check_dict_all_true(dict_to_check):
    """for a dict whose value is bool, return True when all values are True, otherwise False"""
    for _, v in dict_to_check.items():
        if not v:
            return False
    return True

def get_parallel_num(total_task_num):
    """return a Pool object"""
    num_processes = total_task_num
    if num_processes < CPU_CNT / 2:
        pool = multiprocessing.Pool(num_processes)
    else:
        pool = multiprocessing.Pool(CPU_CNT - 2)

    return pool

def hspice_task(hspice, spice_file_path, param_list):
    """open a process to run hspice"""
    return hspice.run(spice_file_path, param_list)

def valid_delay_results(tfall_str, trise_str, log):
    """input param is the result parsed from hspice results, return float if not failed, error if failed"""
    if tfall_str == "failed" or trise_str == "failed":
        log.error("HSPICE measurement failed.\nConsider increasing level-restorers gate length by increasing the 'rest_length_factor' parameter in the input file.")
    tfall = float(tfall_str)
    trise = float(trise_str)
    if tfall < 0:
        log.error("negative value for tfall(%f)" % tfall)
    if trise < 0:
        log.error("negative value for trise(%f)" % trise)
    return tfall, trise