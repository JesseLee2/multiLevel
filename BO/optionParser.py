# -*- coding: utf-8 -*-

from optparse import OptionParser


class CallerOptParser:
    
    def __init__(self, argv):
        self.args = argv[1:]

        self.optParser = OptionParser(description="The Option list of the caller")
        self.optParser.add_option("-t", "--task", action="store", type="string",dest="task_name",help="The task need to run, the taks dir should already been put in VTR_DIR/vtr_flow/tasks")
        self.optParser.add_option("-o", "--output_dir", action="store", type="string", dest="output_dir", help="The output file of this script. (default: ./temp)",default="./temp")
        self.optParser.add_option("-j", "--multiprocesses", action="store", type="int", dest="processes", help="The processes used to run the task (defult : 1)",default=1)
        self.optParser.add_option("-s", "--seed", action="store", type="int", dest="seed", help="The seed used in the seeker (defult : 1)",default=1)
        self.optParser.add_option("-a", "--analyze", action="store", type="string", dest="static_type", help="The type of static analysis ['type','length','rate'] (defult : Bent Type)",default="type")
        self.optParser.add_option("-m", "--area_cons", action="store", type="int", dest="area_cons", help="area_cons or not (defult : 1)", default=1)
        self.optParser.add_option("-d", "--run_dir", action="store", type="string", dest="run_dir", help="run_dir (defult : run001)",default="run001")
    def parse(self):
        (options, args) = self.optParser.parse_args(args=self.args)
        return (options, args)

    