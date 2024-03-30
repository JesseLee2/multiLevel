import xml.etree.ElementTree as ET
from hyperopt import hp, space_eval, STATUS_OK, STATUS_FAIL
from hyperopt.mongoexp import MongoTrials
# from hyper_opt_parallel import gen_new_arch, get_args, get_rval, gen_space
from Seeker_bayes_seg import *
import pandas as pd
from bson.json_util import dumps
import matplotlib.pyplot as plt 

def sort_trials_concern_key(elem):
    return float(elem['geom imp'])
def get_failed_arch(trials, archTree):
    fail_arch_var = []
    i = 0
    os.system('mkdir arch_failed')
    print(os.getcwd())
    archfile = os.getcwd() + '/arch_failed'
    
    for trial in trials.trials:
        if trial['result']['status'] == STATUS_FAIL:
            if 'results' in trial['result']:
                i = i + 1
                fail_arch_var.append(trial["misc"]["vals"])
                vars_dic = {}
                arch_var = []
                for (k, v) in trial['misc']['vals'].items():
                    k = int(k[3:])
                    vars_dic[k] = v[0]
                for var in sorted(vars_dic.items(), key = lambda x: x[0]):
                    arch_var.append(var[1])
                segments, relations, chanWidth, typeToNum = genArch(arch_var)
                modifyArch_V3(segments, relations, archTree)
                modifyArch_addMedium(archTree)
                (gsbMUXFanin, imuxMUXFanin) = generateTwoStageMux_v200(archTree)
                modifyMUXSize(archTree, gsbMUXFanin, imuxMUXFanin, typeToNum)
                new_arch_name = 'test'+str(i) + '.xml'
                writeArch(archTree["root"].getroot(), './arch_failed/' + new_arch_name)

def get_best_arch(trials, archTree):
    fail_arch_var = []
    i = 0
    vars_dic = {}
    work_dir = 'best_arch'
    os.system('mkdir best_arch')
    print(os.getcwd())
    archfile = os.getcwd() + '/best_arch'
    best_trail = trials.best_trial
    arch_var = []
    trial_var = best_trail['misc']['vals']
    for (k, v) in trial_var.items():
        k = int(k[3:])
        vars_dic[k] = v[0]
    for var in sorted(vars_dic.items(), key = lambda x: x[0]):
        arch_var.append(var[1])
    segments, relations, chanWidth, typeToNum = genArch(arch_var)
    modifyArch_V3(segments, relations, archTree)
    modifyArch_addMedium(archTree)
    (gsbMUXFanin, imuxMUXFanin) = generateTwoStageMux_v200(archTree)
    modifyMUXSize(archTree, gsbMUXFanin, imuxMUXFanin, typeToNum)
    new_arch_name = 'searched.xml'
    writeArch(archTree["root"].getroot(), './best_arch/' + new_arch_name)
    print("generate searched arch done")


def show_trial_info(trials, arch_name):

    for trial in trials.trials:
        if (trial['result']['status'] == 'ok') and (trial['result']['arch_name'] == arch_name) and (float(trial['result']['loss']) < -0.1):
            result_df = pd.DataFrame.from_dict(trial['result']['results'])
            print(trial['result']['loss'])
            print(result_df)


def statistic_runner_con(trials):

    print('total:', len(trials.trials))
    why_num = {}

    trials_OK = []
    nTrial_OK =0
    nTrial_FAIL = 0; nTrial_FAIL_Why = 0; nTrial_FAIL_run = 0
    for trial in trials.trials:
        if trial['result']['status'] == STATUS_OK:
            trials_OK.append(trial)
            nTrial_OK += 5
        elif trial['result']['status'] == STATUS_FAIL:
            nTrial_FAIL += 1
            if 'why' in trial['result']:
                if trial['result']['why'] in why_num:
                    why_num[trial['result']['why']] += 1
                else:
                    why_num[trial['result']['why']] = 0
                nTrial_FAIL_Why += 1
            if 'results' in trial['result']:
                nTrial_FAIL_run += 1
        vals = trial["misc"]["vals"]
        rval = {}
        for k, v in list(vals.items()):
            if v:
                rval[k] = v[0]
        # print(space_eval(space, rval))
        # print(trial['result']['why'])
    print('STATUS_OK:', nTrial_OK)
    print('STATUS_FAIL:', nTrial_FAIL)
    print('STATUS_FAIL_Why:', nTrial_FAIL_Why)
    print('nTrial_FAIL_run:', nTrial_FAIL_run)
    print(why_num)

if __name__ == "__main__":

    args = get_args()
    base_arch_file = args.base_arch_file
    base_csv_file = args.base_csv_file
    new_arch_name = args.new_arch_name
    parallel_number = args.parallel_number
    base_arch_tree = {}

    with open(base_arch_file) as base_arch_f:
        base_arch_tree['root'] = ET.parse(base_arch_f)
        base_arch_tree['segOrigin'] = getOriginSeg(base_arch_tree["root"])
    with open(base_csv_file, 'r') as base_csv_f:
        base_result = pd.read_csv(base_csv_f, index_col=0)

    connect_string = "mongo+ssh://asicskl06:1234/foo_db/jobs"
    trials = MongoTrials(connect_string)

    # get_failed_arch(trials, base_arch_tree)

    # print(trials.trials[0])
    statistic_runner_con(trials)
    # print(trials.trials[0])
    # print('sFull28_8.xml')
    show_trial_info(trials, 'sFullRe47_10.xml')
    if trials.best_trial['result']['bench_PASS_number'] > 13:
        print(trials.best_trial['result']['loss'])
        print(trials.best_trial['result']['delay imp'])
        print(trials.best_trial['result']['area imp'])
        print(trials.best_trial['result']['bench_PASS_number'])
        print(trials.best_trial['result']['arch_name'])
        result_df = pd.DataFrame.from_dict(trials.best_trial['result']['results'])
        print(result_df)