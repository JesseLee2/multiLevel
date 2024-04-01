# -*- coding: utf-8 -*-

import optionParser
import os.path
import sys
import re
import Regex
import datetime
import multiprocessing
import time as tt
import subprocess

class CallerError(Exception):
    pass

class TimeoutError(Exception):
    pass

class Caller:

    def __init__(self, args):

        callerOptionParser = optionParser.CallerOptParser(args)
        (options, args) = callerOptionParser.parse()

        self.area_cons = options.area_cons
        self.run_dir = options.run_dir

        self.circuits = []
        self.archs = []
        self.commands = None
        self.optimizeArchs = []

        self.task = options.task_name
        self.out_dir = options.output_dir 
        self.placer_type = "VPR"
        self.processes = options.processes
        self.seed = options.seed
        self.analyze_type = options.static_type
        
        self.script_dir = sys.path[0]
        self.vpr_bin = sys.path[0] + "/../build/vpr/vpr"
        self.vtr_flow_dir = sys.path[0] + "/../vtr_flow"

        self.compare_pair = []
        self.analyze_pairs = []

        self.is_mutable_chan_width = False
        self.mutable_chan_width = {}

        if not os.path.exists(self.vpr_bin):
            raise CallerError("The vpr binary file is not exist.")

        self.circuits_dir = None
        self.arch_dir = None

        if not os.path.exists(self.out_dir):
            raise CallerError("Output dir : ("+ self.out_dir +") is not exist")
            
        if self.placer_type != "VPR":
            raise CallerError("Placer type ("+ self.placer_type  +") Error")

        if self.task != None and not os.path.exists(self.script_dir + "/../vtr_flow/tasks/" + self.task):
            raise CallerError("task ("+ self.task +") is not exist")
        elif self.task == None:
            raise CallerError("You should give a task.")
        elif not os.path.exists(self.script_dir + "/../vtr_flow/tasks/" + self.task + "/config/config.txt"):
            raise CallerError("The config file is not exist in task dir.")

        self.task_dir = self.script_dir + "/../vtr_flow/tasks/" + self.task
        self.run_dir = None
        self.parse_task()

        if self.circuits_dir == None or not os.path.exists(self.vtr_flow_dir + "/" + self.circuits_dir):
            raise CallerError("Circuits dir : ("+ self.vtr_flow_dir + "/" + self.circuits_dir +") is not exist")

        if self.arch_dir == None or not os.path.exists(self.vtr_flow_dir + "/" + self.arch_dir):
            raise CallerError("Arch dir : ("+ self.vtr_flow_dir + "/" + self.arch_dir +") is not exist")

        self.new_run_dir()
        if len(self.optimizeArchs) > 0:
            self.new_optimize_dirs()

    def new_run_dir(self):
        self.run_dir = [b.strip() for b in os.popen("ls " + self.task_dir).readlines()]
        if len(self.run_dir) > 1:
            os.system("mkdir " + self.task_dir + "/run" + str(int(self.run_dir[-1][-3:])+1).zfill(3))#大于1表示已经有runxxx存在，按序号建一个更大的
        elif len(self.run_dir) == 1:
            os.system("mkdir " + self.task_dir + "/run001")#等于1表示没有runxxx存在，建run001
        self.run_dir = [b.strip() for b in os.popen("ls " + self.task_dir).readlines()]

    def new_optimize_dirs(self):
        os.system("mkdir " + self.task_dir + "/" + self.run_dir[-1] + "/optimizeArchs")
        for arch in self.optimizeArchs:
            os.system("mkdir " + self.task_dir + "/" + self.run_dir[-1] + "/optimizeArchs/" + arch)


    def parse_task(self):
        
        conf_file = open(self.script_dir + "/../vtr_flow/tasks/" + self.task + "/config/config.txt")

        for line in conf_file.readlines():
            if line[0] == "#":
                continue
            if re.match(Regex.regex_task("circuit"), line) != None:
                self.circuits.append(re.match(Regex.regex_task("circuit"), line).group(1))
            elif re.match(Regex.regex_task("arch"), line) != None:
                self.archs.append(re.match(Regex.regex_task("arch"), line).group(1))
            elif re.match(Regex.regex_task("circuits_dir"), line) != None:
                self.circuits_dir = re.match(Regex.regex_task("circuits_dir"), line).group(1)
            elif re.match(Regex.regex_task("archs_dir"), line) != None:
                self.arch_dir = re.match(Regex.regex_task("archs_dir"), line).group(1)
            elif re.match(Regex.regex_task("vpr_params"), line) != None:
                if self.commands is not None:
                    raise CallerError("Multiple vpr_params.")
                self.commands = re.match(Regex.regex_task("vpr_params"), line).group(1)
            elif re.match(Regex.regex_task("compare_pair"), line) != None:
                self.compare_pair.append( (re.match(Regex.regex_task("compare_pair"), line).group(1),\
                                          re.match(Regex.regex_task("compare_pair"), line).group(2)) )
            elif re.match(Regex.regex_task("analyze_single"), line) != None:
                self.analyze_pairs.append( (re.match(Regex.regex_task("analyze_single"), line).group(1),\
                                          re.match(Regex.regex_task("analyze_single"), line).group(2),\
                                          re.match(Regex.regex_task("analyze_single"), line).group(3)) )
            elif re.match(Regex.regex_task("analyze_all"), line) != None:
                self.analyze_pairs.append( (re.match(Regex.regex_task("analyze_all"), line).group(1),\
                                            re.match(Regex.regex_task("analyze_all"), line).group(2)) )
            elif re.match(Regex.regex_task("optimize_arch"), line) != None:
                self.optimizeArchs.append(re.match(Regex.regex_task("optimize_arch"), line).group(1))


    def run_single(self, arch, circuit):
        task_start_time = datetime.datetime.now()
        status = "Failed"

        archRun = self.vtr_flow_dir + "/" + self.arch_dir + "/" + arch
        if not os.path.exists(archRun) :
            raise CallerError("Arch is not exist")

        circuitRun = self.vtr_flow_dir + "/" + self.circuits_dir + "/" + circuit
        if not os.path.exists(circuitRun):
            raise CallerError("circuit is not exist")

        
        work_dir = self.task_dir + "/" + self.run_dir[-1] + "/"+ arch + "/" + circuit
     

        if not os.path.exists(work_dir):
            os.system("mkdir " + work_dir)
        os.system("cp " + archRun + " " + work_dir)
        os.system("cp " + circuitRun + " " + work_dir)

        isPack = re.search(Regex.regex_task("pack"), self.commands)
        isPlace = re.search(Regex.regex_task("place"), self.commands)
        isRoute = re.search(Regex.regex_task("route"), self.commands)


        is_fixed_route_chan_width = re.search(Regex.regex_task("route_chan_width"), self.commands)
        if not is_fixed_route_chan_width:
            raise CallerError("Route_chan_width should be fixed!")

        if not isPack and isPlace and len(self.run_dir) > 1:
            os.system("cp " + self.task_dir + "/" + self.run_dir[-2] + "/" + arch + "/" + circuit + "/*.net " +  work_dir)
        elif not isPlace and isRoute and len(self.run_dir) > 1:
            os.system("cp " + self.task_dir + "/" + self.run_dir[-2] + "/" + arch + "/" + circuit + "/*.net " +  work_dir)
            os.system("cp " + self.task_dir + "/" + self.run_dir[-2] + "/" + arch + "/" + circuit + "/*.place " +  work_dir)

        os.chdir(work_dir)

        time_para = "time"
        if (not self.is_mutable_chan_width):
            os.system(time_para + "  " + self.vpr_bin + " " + arch.split("/")[-1] + " " + circuit.split("/")[-1] +  " "  + self.commands + " > vpr.out 2>&1")
        else:
            raise CallerError("Route_chan_width should be fixed!")
        

        f = open(work_dir + "/vpr.out")
        for line in f.readlines():
            if re.match(Regex.regex_task("status"), line) != None:
                status = "Successed"
                break
        f.close()

        task_end_time = datetime.datetime.now()
        if (task_end_time-task_start_time).seconds > 600 :
            time =  str(round((task_end_time-task_start_time).seconds/60.0,2)) + "min" 
        else :
            time = str((task_end_time-task_start_time).seconds) + "s"

        
        print("Arch: " + arch + "  circuit: " + circuit + "......................."+ status +".     ( " + str(time) + " )")


    def run_sa_single(self, work_dir, arch, arch_name, circuit, chan_width, isFirst, timelimit=10800):
        task_start_time = datetime.datetime.now()
        status = "Failed"

        archRun = arch
        if not os.path.exists(archRun) :
            raise CallerError("Arch is not exist")

        circuitRun = self.vtr_flow_dir + "/" + self.circuits_dir + "/" + circuit
        if not os.path.exists(circuitRun):
            raise CallerError("circuit is not exist")

        circuit_name = re.search(r'(.*).blif', circuit, re.M | re.I).group(1)
        netfile = self.vtr_flow_dir + "/" + self.circuits_dir + "/net/" + circuit_name + ".net"
        if not os.path.exists(netfile):
            raise CallerError("circuit netfile is not exist")

        if not os.path.exists(work_dir):
            os.system("mkdir " + work_dir)
        os.system("cp " + archRun + " " + work_dir)
        os.system("cp " + circuitRun + " " + work_dir)
        os.system("cp " + netfile + " " + work_dir)

        os.chdir(work_dir)

        time_para = "time timeout " + str(timelimit)
        
        commands = "--route_chan_width " + str(chan_width) + " --full_stats on --timing_report_detail aggregated --verify_file_digests off --astar_fac 1.7"
        #commands += " --router_lookahead map"
        if (isFirst == False):
            commands += " --place --route"
        '''#print("start")
        p = subprocess.Popen(time_para + "  " + self.vpr_bin + " " + arch_name + " " + circuit +  " "  + commands + " > vpr.out 2>&1", shell=True) 
        #print("start")
        timeout = 3600
        t_beginning = tt.time()
        seconds_passed = 0.0 
        print("start")
        while True: 
            print("True")
            if p.poll() is not None: 
                print("OK")
                break 
            seconds_passed = tt.time() - t_beginning 
            if seconds_passed > timeout:
                print("timeout") 
                p.terminate() 
                raise TimeoutError("timeout") 
            tt.sleep(10) 
        #return p.stdout.read() '''
        os.system(time_para + "  " + self.vpr_bin + " " + arch_name + " " + circuit +  " "  + commands + " > vpr.out 2>&1")


        f = open(work_dir + "/vpr.out")
        for line in f.readlines():
            if re.match(Regex.regex_task("status"), line) != None:
                status = "Successed"
                break
        f.close()

        task_end_time = datetime.datetime.now()
        if (task_end_time-task_start_time).seconds > 600 :
            time =  str(round((task_end_time-task_start_time).seconds/60.0,2)) + "min" 
        else :
            time = str((task_end_time-task_start_time).seconds) + "s"

        statusfile = open(work_dir + "/result.txt", "w")
        statusfile.write("Arch: " + arch + "  circuit: " + circuit + "......................."+ status +".     ( " + str(time) + " )")
        statusfile.close()
        print("Arch: " + arch + "  circuit: " + circuit + "......................."+ status +".     ( " + str(time) + " )")

        #delete medium file
        bliffile = work_dir + "/" + circuit_name + ".blif"
        netfile = work_dir + "/" + circuit_name + ".net"
        placefile = work_dir + "/" + circuit_name + ".place"
        routefile = work_dir + "/" + circuit_name + ".route"
        os.system("rm -f " + bliffile)
        os.system("rm -f " + netfile)
        os.system("rm -f " + placefile)
        os.system("rm -f " + routefile)

        if status == "Failed":        
            raise CallerError("Run Failed")

    def run_arch_test(self, work_dir, arch, arch_name, circuit, chan_width, isFirst):
        task_start_time = datetime.datetime.now()
        status = "Failed"

        '''archRun = arch
        if not os.path.exists(archRun) :
            raise CallerError("Arch is not exist")'''

        circuitRun = self.vtr_flow_dir + "/" + self.circuits_dir + "/" + circuit
        if not os.path.exists(circuitRun):
            raise CallerError("circuit is not exist")

        netfile = self.vtr_flow_dir + "/" + self.circuits_dir + "/net/" + re.search(r'(.*).blif', circuit, re.M | re.I).group(1) + ".net"
        if not os.path.exists(netfile):
            raise CallerError("circuit netfile is not exist")

        if not os.path.exists(work_dir):
            os.system("mkdir " + work_dir)
        #os.system("cp " + archRun + " " + work_dir)
        os.system("cp " + circuitRun + " " + work_dir)
        os.system("cp " + netfile + " " + work_dir)

        os.chdir(work_dir)

        time_para = "time timeout 600"
        
        commands = "--route_chan_width " + str(chan_width) + " --full_stats on --timing_report_detail aggregated --verify_file_digests off --astar_fac 1.7"
        if (isFirst == False):
            commands += " --place --route"
        os.system(time_para + "  " + self.vpr_bin + " " + arch_name + " " + circuit +  " "  + commands + " > vpr.out 2>&1")

        f = open(work_dir + "/vpr.out")
        for line in f.readlines():
            if re.match(Regex.regex_task("status"), line) != None:
                status = "Successed"
                break
        f.close()

        task_end_time = datetime.datetime.now()
        if (task_end_time-task_start_time).seconds > 600 :
            time =  str(round((task_end_time-task_start_time).seconds/60.0,2)) + "min" 
        else :
            time = str((task_end_time-task_start_time).seconds) + "s"

        #print("Arch: " + arch + "  circuit: " + circuit + "......................."+ status +".     ( " + str(time) + " )")

        if status == "Failed":        
            return False
        else:
            return True


class Caller4Parse:

    def __init__(self, args):

        callerOptionParser = optionParser.CallerOptParser(args)
        (options, args) = callerOptionParser.parse()

        self.area_cons = options.area_cons
        #print(options.run_dir)
        self.run_dir = options.run_dir
        #print(self.run_dir)

        self.circuits = []
        self.archs = []
        self.commands = None
        self.optimizeArchs = []

        self.task = options.task_name
        self.out_dir = options.output_dir
        self.placer_type = "VPR"
        self.processes = options.processes
        self.seed = options.seed
        self.analyze_type = options.static_type

        self.script_dir = sys.path[0]
        self.vpr_bin = sys.path[0] + "/../build/vpr/vpr"
        self.vtr_flow_dir = sys.path[0] + "/../vtr_flow"

        self.compare_pair = []
        self.analyze_pairs = []

        self.is_mutable_chan_width = False
        self.mutable_chan_width = {}

        if not os.path.exists(self.vpr_bin):
            raise CallerError("The vpr binary file is not exist.")

        self.circuits_dir = None
        self.arch_dir = None

        if self.task != None and not os.path.exists(self.script_dir + "/../vtr_flow/tasks/" + self.task):
            raise CallerError("task (" + self.task + ") is not exist")
        elif self.task == None:
            raise CallerError("You should give a task.")
        elif not os.path.exists(self.script_dir + "/../vtr_flow/tasks/" + self.task + "/config/config.txt"):
            raise CallerError("The config file is not exist in task dir.")

        self.task_dir = self.script_dir + "/../vtr_flow/tasks/" + self.task
        self.parse_task()


    def parse_task(self):

        conf_file = open(self.script_dir + "/../vtr_flow/tasks/" +
                      self.task + "/config/config.txt")

        for line in conf_file.readlines():
            if line[0] == "#":
                continue
            if re.match(Regex.regex_task("circuit"), line) != None:
                self.circuits.append(
                    re.match(Regex.regex_task("circuit"), line).group(1))
            elif re.match(Regex.regex_task("arch"), line) != None:
                self.archs.append(
                    re.match(Regex.regex_task("arch"), line).group(1))
            elif re.match(Regex.regex_task("circuits_dir"), line) != None:
                self.circuits_dir = re.match(
                    Regex.regex_task("circuits_dir"), line).group(1)
            elif re.match(Regex.regex_task("archs_dir"), line) != None:
                self.arch_dir = re.match(
                    Regex.regex_task("archs_dir"), line).group(1)
            elif re.match(Regex.regex_task("vpr_params"), line) != None:
                if self.commands is not None:
                    raise CallerError("Multiple vpr_params.")
                self.commands = re.match(
                    Regex.regex_task("vpr_params"), line).group(1)
            elif re.match(Regex.regex_task("compare_pair"), line) != None:
                self.compare_pair.append((re.match(Regex.regex_task("compare_pair"), line).group(1),
                                          re.match(Regex.regex_task("compare_pair"), line).group(2)))
            elif re.match(Regex.regex_task("analyze_single"), line) != None:
                self.analyze_pairs.append((re.match(Regex.regex_task("analyze_single"), line).group(1),
                                           re.match(Regex.regex_task("analyze_single"), line).group(2),
                                           re.match(Regex.regex_task("analyze_single"), line).group(3)))
            elif re.match(Regex.regex_task("analyze_all"), line) != None:
                self.analyze_pairs.append((re.match(Regex.regex_task("analyze_all"), line).group(1),
                                           re.match(Regex.regex_task("analyze_all"), line).group(2)))
            elif re.match(Regex.regex_task("optimize_arch"), line) != None:
                self.optimizeArchs.append(
                    re.match(Regex.regex_task("optimize_arch"), line).group(1))
