/*
 * This file defines the writing rr graph function in XML format.
 * The rr graph is separated into channels, nodes, switches,
 * grids, edges, block types, and segments. Each tag has several
 * children tags such as timing, location, or some general
 * details. Each tag has attributes to describe them */

#include <fstream>
#include <iostream>
#include <string.h>
#include <iomanip>
#include <limits>
#include "vpr_error.h"
#include "globals.h"
#include "read_xml_arch_file.h"
#include "vtr_version.h"
#include "rr_graph_writer.h"

using namespace std;

/* All values are printed with this precision value. The higher the
 * value, the more accurate the read in rr graph is. Using numeric_limits
 * max_digits10 guarentees that no values change during a sequence of
 * float -> string -> float conversions */
constexpr int FLOAT_PRECISION = std::numeric_limits<float>::max_digits10;
/*********************** Subroutines local to this module *******************/
void write_rr_channel(fstream& fp);
void write_rr_node(fstream& fp);
void write_rr_switches(fstream& fp);
void write_rr_grid(fstream& fp);
void write_rr_edges(fstream& fp);
void write_rr_block_types(fstream& fp);
void write_rr_segments(fstream& fp, const std::vector<t_segment_inf>& segment_inf);
void write_bent_rr_edges(fstream& fp);

/************************ Subroutine definitions ****************************/

/* This function is used to write the rr_graph into xml format into a a file with name: file_name */
void write_rr_graph(const char* file_name, const std::vector<t_segment_inf>& segment_inf) {
    fstream fp;
    fp.open(file_name, fstream::out | fstream::trunc);

    /* Prints out general info for easy error checking*/
    if (!fp.is_open() || !fp.good()) {
        vpr_throw(VPR_ERROR_OTHER, __FILE__, __LINE__,
                  "couldn't open file \"%s\" for generating RR graph file\n", file_name);
    }
    cout << "Writing RR graph" << endl;
    fp << "<rr_graph tool_name=\"vpr\" tool_version=\"" << vtr::VERSION << "\" tool_comment=\"Generated from arch file "
       << get_arch_file_name() << "\">" << endl;

    /* Write out each individual component*/
    write_rr_channel(fp);
    write_rr_switches(fp);
    write_rr_segments(fp, segment_inf);
    write_rr_block_types(fp);
    write_rr_grid(fp);
    write_rr_node(fp);
    write_rr_edges(fp);
    //write_bent_rr_edges(fp);
    fp << "</rr_graph>";

    fp.close();

    cout << "Finished generating RR graph file named " << file_name << endl
         << endl;
}

static void add_metadata_to_xml(fstream& fp, const char* tab_prefix, const t_metadata_dict& meta) {
    fp << tab_prefix << "<metadata>" << endl;

    for (const auto& meta_elem : meta) {
        const std::string& key = meta_elem.first;
        const std::vector<t_metadata_value>& values = meta_elem.second;
        for (const auto& value : values) {
            fp << tab_prefix << "\t<meta name=\"" << key << "\"";
            fp << ">" << value.as_string() << "</meta>" << endl;
        }
    }
    fp << tab_prefix << "</metadata>" << endl;
}

/* Channel info in device_ctx.chan_width is written in xml format.
 * A general summary of the min and max values of the channels are first printed. Every
 * x and y channel list is printed out in its own attribute*/
void write_rr_channel(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();
    fp << "\t<channels>" << endl;
    fp << "\t\t<channel chan_width_max =\"" << device_ctx.chan_width.max << "\" x_min=\"" << device_ctx.chan_width.x_min << "\" y_min=\"" << device_ctx.chan_width.y_min << "\" x_max=\"" << device_ctx.chan_width.x_max << "\" y_max=\"" << device_ctx.chan_width.y_max << "\"/>" << endl;

    auto& list = device_ctx.chan_width.x_list;
    for (size_t i = 0; i < device_ctx.grid.height() - 1; i++) {
        fp << "\t\t<x_list index =\"" << i << "\" info=\"" << list[i] << "\"/>" << endl;
    }
    auto& list2 = device_ctx.chan_width.y_list;
    for (size_t i = 0; i < device_ctx.grid.width() - 1; i++) {
        fp << "\t\t<y_list index =\"" << i << "\" info=\"" << list2[i] << "\"/>" << endl;
    }
    fp << "\t</channels>" << endl;
}

/* All relevant rr node info is written out to the graph.
 * This includes location, timing, and segment info*/
void write_rr_node(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();

    fp << "\t<rr_nodes>" << endl;

    for (size_t inode = 0; inode < device_ctx.rr_nodes.size(); inode++) {
        auto& node = device_ctx.rr_nodes[inode];
        fp << "\t\t<node";
        fp << " id=\"" << inode;
        fp << "\" type=\"" << node.type_string();
        if (node.type() == CHANX || node.type() == CHANY) {
            fp << "\" direction=\"" << node.direction_string();
        }
        fp << "\" capacity=\"" << node.capacity();
        fp << "\">" << endl;
        fp << "\t\t\t<loc";
        fp << " xlow=\"" << node.xlow();
        fp << "\" ylow=\"" << node.ylow();
        fp << "\" xhigh=\"" << node.xhigh();
        fp << "\" yhigh=\"" << node.yhigh();
        if (node.type() == IPIN || node.type() == OPIN) {
            fp << "\" side=\"" << node.side_string();
        }
        fp << "\" ptc=\"" << node.ptc_num();
        fp << "\"/>" << endl;
        fp << "\t\t\t<timing R=\"" << setprecision(FLOAT_PRECISION) << node.R()
           << "\" C=\"" << setprecision(FLOAT_PRECISION) << node.C() << "\"/>" << endl;

        if (device_ctx.rr_indexed_data[node.cost_index()].seg_index != -1) {
            fp << "\t\t\t<segment segment_id=\"" << device_ctx.rr_indexed_data[node.cost_index()].seg_index << "\"";
            fp << " cost_index=\"" << node.cost_index() << "\"/>" << endl;
        }

        const auto iter = device_ctx.rr_node_metadata.find(inode);
        if (iter != device_ctx.rr_node_metadata.end()) {
            const t_metadata_dict& meta = iter->second;
            add_metadata_to_xml(fp, "\t\t\t", meta);
        }

        fp << "\t\t</node>" << endl;
    }

    fp << "\t</rr_nodes>" << endl
       << endl;
}

/* Segment information in the t_segment_inf data structure is written out.
 * Information includes segment id, name, and optional timing parameters*/
void write_rr_segments(fstream& fp, const std::vector<t_segment_inf>& segment_inf) {
    fp << "\t<segments>" << endl;

    for (size_t iseg = 0; iseg < segment_inf.size(); iseg++) {
        fp << "\t\t<segment id=\"" << iseg << "\" name=\"" << segment_inf[iseg].name << "\">" << endl;
        fp << "\t\t\t<timing R_per_meter=\"" << setprecision(FLOAT_PRECISION) << segment_inf[iseg].Rmetal << "\" C_per_meter=\"" << setprecision(FLOAT_PRECISION) << segment_inf[iseg].Cmetal << "\"/>" << endl;
        fp << "\t\t</segment>" << endl;
    }
    fp << "\t</segments>" << endl
       << endl;
}

/* Switch info is written out into xml format. This includes
 * general, sizing, and optional timing information*/
void write_rr_switches(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();
    fp << "\t<switches>" << endl;

    for (size_t iSwitch = 0; iSwitch < device_ctx.rr_switch_inf.size(); iSwitch++) {
        t_rr_switch_inf rr_switch = device_ctx.rr_switch_inf[iSwitch];

        fp << "\t\t<switch id=\"" << iSwitch;

        if (rr_switch.type() == SwitchType::TRISTATE) {
            fp << "\" type=\"tristate";
        } else if (rr_switch.type() == SwitchType::MUX) {
            fp << "\" type=\"mux";
        } else if (rr_switch.type() == SwitchType::PASS_GATE) {
            fp << "\" type=\"pass_gate";
        } else if (rr_switch.type() == SwitchType::SHORT) {
            fp << "\" type=\"short";
        } else if (rr_switch.type() == SwitchType::UNISHORT) {
            fp << "\" type=\"unishort";
        } else if (rr_switch.type() == SwitchType::BUFFER) {
            fp << "\" type=\"buffer";
        } else {
            VPR_THROW(VPR_ERROR_ROUTE, "Invalid switch type %d\n", rr_switch.type());
        }
        fp << "\"";

        if (rr_switch.name) {
            fp << " name=\"" << rr_switch.name << "\"";
        }
        fp << ">" << endl;

        fp << "\t\t\t<timing R=\"" << setprecision(FLOAT_PRECISION) << rr_switch.R << "\" Cin=\"" << setprecision(FLOAT_PRECISION) << rr_switch.Cin << "\" Cout=\"" << setprecision(FLOAT_PRECISION) << rr_switch.Cout << "\" Tdel=\"" << setprecision(FLOAT_PRECISION) << rr_switch.Tdel << "\"/>" << endl;
        fp << "\t\t\t<sizing mux_trans_size=\"" << setprecision(FLOAT_PRECISION) << rr_switch.mux_trans_size << "\" buf_size=\"" << setprecision(FLOAT_PRECISION) << rr_switch.buf_size << "\"/>" << endl;
        fp << "\t\t</switch>" << endl;
    }
    fp << "\t</switches>" << endl
       << endl;
}

/* Block information is printed out in xml format. This includes general,
 * pin class, and pins */
void write_rr_block_types(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();
    fp << "\t<block_types>" << endl;

    for (int iBlock = 0; iBlock < device_ctx.num_block_types; iBlock++) {
        auto& btype = device_ctx.block_types[iBlock];

        fp << "\t\t<block_type id=\"" << btype.index;

        /*since the < symbol is not allowed in xml format, converted to only print "EMPTY"*/
        if (btype.name) {
            fp << "\" name=\"" << btype.name;
        }

        fp << "\" width=\"" << btype.width << "\" height=\"" << btype.height << "\">" << endl;

        for (int iClass = 0; iClass < btype.num_class; iClass++) {
            auto& class_inf = btype.class_inf[iClass];

            char const* pin_type;
            switch (class_inf.type) {
                case -1:
                    pin_type = "OPEN";
                    break;
                case 0:
                    pin_type = "OUTPUT"; //driver
                    break;
                case 1:
                    pin_type = "INPUT"; //receiver
                    break;
                default:
                    pin_type = "NONE";
                    break;
            }

            //the pin list is printed out as the child values
            fp << "\t\t\t<pin_class type=\"" << pin_type << "\">\n";
            for (int iPin = 0; iPin < class_inf.num_pins; iPin++) {
                auto pin = class_inf.pinlist[iPin];
                fp << vtr::string_fmt("\t\t\t\t<pin ptc=\"%d\">%s</pin>\n",
                                      pin, block_type_pin_index_to_name(&btype, pin).c_str());
            }
            fp << "\t\t\t</pin_class>" << endl;
        }
        fp << "\t\t</block_type>" << endl;
    }
    fp << "\t</block_types>" << endl
       << endl;
}

/* Grid information is printed out in xml format. Each grid location
 * and its relevant information is included*/
void write_rr_grid(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();

    fp << "\t<grid>" << endl;

    for (size_t x = 0; x < device_ctx.grid.width(); x++) {
        for (size_t y = 0; y < device_ctx.grid.height(); y++) {
            t_grid_tile grid_tile = device_ctx.grid[x][y];

            fp << "\t\t<grid_loc x=\"" << x << "\" y=\"" << y << "\" block_type_id=\"" << grid_tile.type->index << "\" width_offset=\"" << grid_tile.width_offset << "\" height_offset=\"" << grid_tile.height_offset << "\"/>" << endl;
        }
    }
    fp << "\t</grid>" << endl
       << endl;
}

/* Edges connecting to each rr node is printed out. The two nodes
 * it connects to are also printed*/
void write_rr_edges(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();
    fp << "\t<rr_edges>" << endl;

    for (size_t inode = 0; inode < device_ctx.rr_nodes.size(); inode++) {
        auto& node = device_ctx.rr_nodes[inode];
        for (int iedge = 0; iedge < node.num_edges(); iedge++) {
            fp << "\t\t<edge src_node=\"" << inode << "\" sink_node=\"" << node.edge_sink_node(iedge) << "\" switch_id=\"" << node.edge_switch(iedge) << "\"";

            bool wrote_edge_metadata = false;
            const auto iter = device_ctx.rr_edge_metadata.find(std::make_tuple(inode, node.edge_sink_node(iedge), node.edge_switch(iedge)));
            if (iter != device_ctx.rr_edge_metadata.end()) {
                fp << ">" << endl;

                const t_metadata_dict& meta = iter->second;
                add_metadata_to_xml(fp, "\t\t\t", meta);
                wrote_edge_metadata = true;
            }

            if (wrote_edge_metadata == false) {
                fp << "/>" << endl;
            } else {
                fp << "\t\t</edge>" << endl;
            }
        }
    }
    fp << "\t</rr_edges>" << endl
       << endl;
}

void write_bent_rr_edges(fstream& fp) {
    auto& device_ctx = g_vpr_ctx.device();
    int iSwitch;
    for (iSwitch = 0; iSwitch < device_ctx.rr_switch_inf.size(); iSwitch++) {
        t_rr_switch_inf rr_switch = device_ctx.rr_switch_inf[iSwitch];
        if (rr_switch.type() == SwitchType::UNISHORT)
            break;
    }
    if (iSwitch < device_ctx.rr_switch_inf.size()){
        return;
    }
    //VTR_ASSERT(iSwitch < device_ctx.rr_switch_inf.size());
    fp << "\t<rr_edges>" << endl;

    for (size_t inode = 0; inode < device_ctx.rr_nodes.size(); inode++) {
        auto& node = device_ctx.rr_nodes[inode];
        for (int iedge = 0; iedge < node.num_edges(); iedge++) {
            if (node.edge_switch(iedge) != iSwitch)
                continue;
            fp << "\t\t<edge src_node=\"" << inode << "\" sink_node=\"" << node.edge_sink_node(iedge) << "\" switch_id=\"" << node.edge_switch(iedge) << "\""<<"</>"<< endl;
            auto& node = device_ctx.rr_nodes[inode];
            fp << "\t\t<node";
            fp << " id=\"" << inode;
            fp << "\" type=\"" << node.type_string();
            if (node.type() == CHANX || node.type() == CHANY) {
                fp << "\" direction=\"" << node.direction_string();
            }
            fp << "\" capacity=\"" << node.capacity();
            fp << "\">" << endl;
            fp << "\t\t\t<loc";
            fp << " xlow=\"" << node.xlow();
            fp << "\" ylow=\"" << node.ylow();
            fp << "\" xhigh=\"" << node.xhigh();
            fp << "\" yhigh=\"" << node.yhigh();
            if (node.type() == IPIN || node.type() == OPIN) {
                fp << "\" side=\"" << node.side_string();
            }
            fp << "\" ptc=\"" << node.ptc_num();
            fp << "\"/>" << endl;

            if (device_ctx.rr_indexed_data[node.cost_index()].seg_index != -1) {
                fp << "\t\t\t<segment segment_id=\"" << device_ctx.rr_indexed_data[node.cost_index()].seg_index << "\"/>" << endl;
                fp << "\t\t\t<segment cost_index=\"" << node.cost_index() << "\"/>" << endl;
            }
            fp << "\t\t</node>" << endl;

            auto& to_node = device_ctx.rr_nodes[node.edge_sink_node(iedge)];
            fp << "\t\t<to_node";
            fp << " id=\"" << inode;
            fp << "\" type=\"" << to_node.type_string();
            if (to_node.type() == CHANX || to_node.type() == CHANY) {
                fp << "\" direction=\"" << to_node.direction_string();
            }
            fp << "\" capacity=\"" << to_node.capacity();
            fp << "\">" << endl;
            fp << "\t\t\t<loc";
            fp << " xlow=\"" << to_node.xlow();
            fp << "\" ylow=\"" << to_node.ylow();
            fp << "\" xhigh=\"" << to_node.xhigh();
            fp << "\" yhigh=\"" << to_node.yhigh();
            if (to_node.type() == IPIN || to_node.type() == OPIN) {
                fp << "\" side=\"" << to_node.side_string();
            }
            fp << "\" ptc=\"" << to_node.ptc_num();
            fp << "\"/>" << endl;

            if (device_ctx.rr_indexed_data[to_node.cost_index()].seg_index != -1) {
                fp << "\t\t\t<segment segment_id=\"" << device_ctx.rr_indexed_data[to_node.cost_index()].seg_index << "\"/>" << endl;
                fp << "\t\t\t<segment cost_index=\"" << to_node.cost_index() << "\"/>" << endl;
            }
            fp << "\t\t</to_node>" << endl;
        }
    }
    fp << "\t</rr_edges>" << endl
       << endl;
}

void write_one_gsb_arch(const char* file_name, int x_coord, int y_coord, const std::vector<t_segment_inf>& segment_inf){
    fstream fp;
    fp.open(file_name, fstream::out | fstream::trunc);

    /* Prints out general info for easy error checking*/
    if (!fp.is_open() || !fp.good()) {
        vpr_throw(VPR_ERROR_OTHER, __FILE__, __LINE__,
                  "couldn't open file \"%s\" for generating RR graph file\n", file_name);
    }

    auto& device_ctx = g_vpr_ctx.device();
    int imux_seg_id = segment_inf.size() - 3;
    int omux_seg_id = segment_inf.size() - 2;
    int gsb_seg_id = segment_inf.size() - 1;
    const std::vector<std::string> opin_str = {"o", "q", "mux"};
    const std::vector<std::string> lut_str = {"a","b","c","d","e","f","g","h"};
    std::map<int, std::vector<int>> to_from_map;//{to_node, [from_nodes]}
    //std::map<int, std::vector<int>> medium_from_map; //{medium_node, [from_nodes]}

    //
    std::vector<std::vector<std::vector<int>>> from_seg_vec; //{side, seg_type_id, <track_num, name>}
    from_seg_vec.resize(4);
    for (int i = 0; i < 4; i++){
        from_seg_vec[i].resize(segment_inf.size() - 3);
    }

    std::vector<int> pb_opin_vec;

    std::vector<std::vector<int>> medium_vec; //[IMUX/OMUX/GSB][medium_num]
    medium_vec.resize(3);

    std::map<int, std::string> node_name_map;

    std::vector<std::vector<std::vector<int>>> to_seg_vec; //{side, seg_type_id, track_num}
    to_seg_vec.resize(4);
    for (int i = 0; i < 4; i++) {
        to_seg_vec[i].resize(segment_inf.size() - 3);
    }

    int xlow, xhigh, ylow, yhigh, seg_id;
    e_direction seg_dir;
    char* name = (char*)malloc(sizeof(char)*100);
    //sprintf(name, "sw_end_eb");
    std::vector<int> medium_index = {0, 0, 0, 0};//imux, imux_ipin, omux, gsb
    int opin_index = 0;
    int ipin_index = 0;

    for (size_t inode = 0; inode < device_ctx.rr_nodes.size(); inode++) {
        auto& node = device_ctx.rr_nodes[inode];
        xlow = node.xlow();
        xhigh = node.xhigh();
        ylow = node.ylow();
        yhigh = node.yhigh();
        seg_id = node.seg_id();

        if(node.type() == SOURCE || node.type() == SINK){
            continue;
        }

        if(node.type() == OPIN && (xlow != x_coord || ylow != y_coord))
            continue;

        if(node.type() == CHANX)
            if(ylow != y_coord || (xhigh != x_coord && xlow != x_coord +1))
                continue;

        if(node.type() == CHANY)
            if(xlow != x_coord || (yhigh != y_coord && ylow != y_coord +1))
                continue;

        bool can_be_from = true;
        bool can_be_to = true;
        if(segment_inf[seg_id].isbend){
            if(node.is_bend_end()){
                can_be_to = false;
            }
            else if(node.is_bend_first()){
                can_be_from = false;
            }
            else{
                continue;
            }
        }

        //auto const& seg_inf = segment_inf[seg_id];
        //auto bend = segment_inf[seg_id].isbend ? segment_inf[seg_id].bend : vector<int>();
        int bendIdx = seg_id >= 0 && segment_inf[seg_id].isbend ? segment_inf[seg_id].length - segment_inf[seg_id].part_len.back() - 1 : 0;
        //收集互连线对应node及medium对应node
        //VTR_LOG("node = %d\n", inode);
        switch(node.type()){
            case CHANX:
                seg_dir = node.direction();
                if (seg_id < imux_seg_id) { //imux_seg_id是最小的
                    if (xhigh == x_coord) {
                        if(seg_dir == INC_DIRECTION && can_be_from){
                            from_seg_vec[LEFT][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if(bendType == UP_TYPE){
                                    sprintf(name, "sw_end_s%de%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[LEFT][seg_id].size() - 1);
                                }else{
                                    sprintf(name, "sw_end_n%de%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[LEFT][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_end_e%d-b%d", segment_inf[seg_id].length, from_seg_vec[LEFT][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        } else if (seg_dir == DEC_DIRECTION && can_be_to) {
                            //VTR_ASSERT(seg_dir == DEC_DIRECTION);
                            to_seg_vec[LEFT][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_beg_w%ds%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[LEFT][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_beg_w%dn%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[LEFT][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_beg_w%d-b%d", segment_inf[seg_id].length, to_seg_vec[LEFT][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        }
                    } else if (xlow == x_coord + 1) {
                        if (seg_dir == DEC_DIRECTION && can_be_from) {
                            from_seg_vec[RIGHT][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_end_n%dw%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[RIGHT][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_end_s%dw%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[RIGHT][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_end_w%d-b%d", segment_inf[seg_id].length, from_seg_vec[RIGHT][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        } else if (seg_dir == INC_DIRECTION && can_be_to) {
                            //VTR_ASSERT(seg_dir == INC_DIRECTION);
                            to_seg_vec[RIGHT][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_beg_e%dn%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[RIGHT][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_beg_e%ds%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[RIGHT][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_beg_e%d-b%d", segment_inf[seg_id].length, to_seg_vec[RIGHT][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        }
                    }
                } else {
                    if(xhigh == x_coord && yhigh == y_coord){
                        if(seg_id == imux_seg_id){
                            //imux
                            bool is_ipin = false;
                            for(int e = 0; e < node.num_edges(); e++){
                                if(node.edge_switch(e)==0){
                                    is_ipin = true;
                                }
                            }
                            if(is_ipin){
                                //ipin medium
                                if(medium_index[1] < 48){
                                    sprintf(name, "fn_end_b%d-%s", medium_index[1]%6+1, lut_str[medium_index[1]/6].c_str());
                                }else if(medium_index[1] < 56){
                                    sprintf(name, "fn_end_i-%s", lut_str[medium_index[1]%8].c_str());
                                }
                                else{
                                    sprintf(name, "fn_end_x-%s", lut_str[medium_index[1]%8].c_str());
                                }

                                medium_vec[0].push_back(inode);
                                node_name_map[inode] = name;
                                medium_index[1] += 1;
                            }
                            else{
                                sprintf(name, "swvir_ept_t1-mux-%d", medium_index[0]+1);
                                medium_vec[0].push_back(inode);
                                node_name_map[inode] = name;
                                medium_index[0] += 1;
                            }
                        }
                        else if(seg_id == omux_seg_id){
                            //omux
                            sprintf(name, "swvir_ept_oxbar-b%d", medium_index[2]);
                            medium_vec[1].push_back(inode);
                            node_name_map[inode] = name;
                            medium_index[2] += 1;
                        }
                        else{
                            VTR_ASSERT(seg_id == gsb_seg_id);
                            //gsb
                            sprintf(name, "swvir_ept_mux-%d-%d", medium_index[3]/4, medium_index[3]%4);
                            medium_vec[2].push_back(inode);
                            node_name_map[inode] = name;
                            medium_index[3] += 1;
                        }
                    }
                }
                break;

            case CHANY:
                seg_dir = node.direction();
                if (seg_id < imux_seg_id) { //imux_seg_id是最小的
                    if (yhigh == y_coord) {
                        if (seg_dir == INC_DIRECTION && can_be_from) {
                            from_seg_vec[BOTTOM][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_end_e%dn%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[BOTTOM][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_end_w%dn%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[BOTTOM][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_end_n%d-b%d", segment_inf[seg_id].length, from_seg_vec[BOTTOM][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        } else if (seg_dir == DEC_DIRECTION && can_be_to) {
                            //VTR_ASSERT(seg_dir == DEC_DIRECTION);
                            to_seg_vec[BOTTOM][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_beg_s%de%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[BOTTOM][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_beg_s%dw%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[BOTTOM][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_beg_s%d-b%d", segment_inf[seg_id].length, to_seg_vec[BOTTOM][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        }
                    } else if (ylow == y_coord + 1) {
                        if (seg_dir == DEC_DIRECTION && can_be_from) {
                            from_seg_vec[TOP][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_end_w%ds%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[TOP][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_end_e%ds%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], from_seg_vec[TOP][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_end_s%d-b%d", segment_inf[seg_id].length, from_seg_vec[TOP][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        } else if (seg_dir == INC_DIRECTION && can_be_to) {
                            VTR_ASSERT(seg_dir == INC_DIRECTION);
                            to_seg_vec[TOP][seg_id].push_back(inode);
                            if (segment_inf[seg_id].isbend) {
                                VTR_ASSERT(segment_inf[seg_id].bend[bendIdx] != 0);
                                auto bendType = segment_inf[seg_id].bend[bendIdx] == 1 ? UP_TYPE : DOWN_TYPE;
                                if (bendType == UP_TYPE) {
                                    sprintf(name, "sw_beg_n%dw%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[TOP][seg_id].size() - 1);
                                } else {
                                    sprintf(name, "sw_beg_n%de%d-b%d", segment_inf[seg_id].part_len[0], segment_inf[seg_id].part_len[1], to_seg_vec[TOP][seg_id].size() - 1);
                                }
                            } else {
                                sprintf(name, "sw_beg_n%d-b%d", segment_inf[seg_id].length, to_seg_vec[TOP][seg_id].size() - 1);
                            }
                            node_name_map[inode] = name;
                        }
                    }
                }
                else{
                    if (xhigh == x_coord && yhigh == y_coord) {
                        if (seg_id == imux_seg_id) {
                            //imux
                            bool is_ipin = false;
                            for(int e = 0; e < node.num_edges(); e++){
                                if(node.edge_switch(e)==0){
                                    is_ipin = true;
                                }
                            }
                            if (is_ipin) {
                                //ipin medium
                                if(medium_index[1] < 48){
                                    sprintf(name, "fn_end_b%d-%s", medium_index[1]%6+1, lut_str[medium_index[1]/6].c_str());
                                }else if(medium_index[1] < 56){
                                    sprintf(name, "fn_end_i-%s", lut_str[medium_index[1]%8].c_str());
                                }
                                else{
                                    sprintf(name, "fn_end_x-%s", lut_str[medium_index[1]%8].c_str());
                                }
                                medium_vec[0].push_back(inode);
                                node_name_map[inode] = name;
                                medium_index[1] += 1;
                            } else {
                                sprintf(name, "swvir_ept_t1-mux-%d", medium_index[0]+1);
                                medium_vec[0].push_back(inode);
                                node_name_map[inode] = name;
                                medium_index[0] += 1;
                            }
                        } else if (seg_id == omux_seg_id) {
                            //omux
                            sprintf(name, "swvir_ept_oxbar-b%d", medium_index[2]);
                            medium_vec[1].push_back(inode);
                            node_name_map[inode] = name;
                            medium_index[2] += 1;
                        } else {
                            VTR_ASSERT(seg_id == gsb_seg_id);
                            //gsb
                            sprintf(name, "swvir_ept_mux-%d-%d", medium_index[3] / 4, medium_index[3] % 4);
                            medium_vec[2].push_back(inode);
                            node_name_map[inode] = name;
                            medium_index[3] += 1;
                        }
                    }
                }
                break;

            case OPIN:
                if(xlow==xhigh && xlow==x_coord && ylow==yhigh && ylow == y_coord){
                    VTR_ASSERT(opin_index <= 23);
                    sprintf(name, "fn_beg_%s-%s", opin_str[opin_index/8].c_str(), lut_str[opin_index%8].c_str());
                    opin_index++;
                    pb_opin_vec.push_back(inode);
                    node_name_map[inode] = name;
                }
                break;

            case IPIN:
                if (xlow == xhigh && xlow == x_coord && ylow == yhigh && ylow == y_coord) {
                    if(ipin_index < 48){
                        sprintf(name, "fn_end_b%d-%s", ipin_index%6+1, lut_str[ipin_index/6].c_str());
                    }else if(ipin_index < 56){
                        sprintf(name, "fn_end_i-%s", lut_str[ipin_index%8].c_str());
                    }
                    else{
                        sprintf(name, "fn_end_x-%s", lut_str[ipin_index%8].c_str());
                    }
                    //pb_opin_vec.push_back(inode);
                    node_name_map[inode] = name;
                    ipin_index++;
                }
                break;

            default:
                break;
        }
    }

    //segment
    for(e_side side : {LEFT, TOP, RIGHT, BOTTOM}){
        for (int i = 0; i < segment_inf.size() - 3; i++){
            for (int j = 0; j < from_seg_vec[side][i].size(); j++){
                auto& node = device_ctx.rr_nodes[from_seg_vec[side][i][j]];
                for (int iedge = 0; iedge < node.num_edges(); iedge++) {
                    int to_node = node.edge_sink_node(iedge);
                    to_from_map[to_node].push_back(from_seg_vec[side][i][j]);
                }
            }
        }
    }

    //medium node
    for (int i = 0; i < 3; i++){
        for (int j = 0; j < medium_vec[i].size(); j++) {
            auto& node = device_ctx.rr_nodes[medium_vec[i][j]];
            for (int iedge = 0; iedge < node.num_edges(); iedge++) {
                int to_node = node.edge_sink_node(iedge);
                to_from_map[to_node].push_back(medium_vec[i][j]);
            }
        }
    }

    //opin
    for (int j = 0; j < pb_opin_vec.size(); j++) {
        auto& node = device_ctx.rr_nodes[pb_opin_vec[j]];
        for (int iedge = 0; iedge < node.num_edges(); iedge++) {
            int to_node = node.edge_sink_node(iedge);
            to_from_map[to_node].push_back(pb_opin_vec[j]);
        }
    }


    //print ********************************
    //gsb

    std::string to_name, from_name;
    fp << "from" << "\t\t" << "to(gsb_medium)" << endl;
    for (auto const& to_from : to_from_map) {
        auto& node = device_ctx.rr_nodes[to_from.first];
        if((node.type() == CHANX || node.type() == CHANY) && node.seg_id() == gsb_seg_id) {
            for (auto fn : to_from.second) {
                fp << node_name_map[fn] << "\t" << node_name_map[to_from.first] << endl;
            }
            fp << endl;
        }
    }

    fp << "from" << "\t\t" << "to(seg)" << endl;
    for (auto const& to_from : to_from_map) {
        auto& node = device_ctx.rr_nodes[to_from.first];
        if((node.type() == CHANX || node.type() == CHANY) && node.seg_id() < segment_inf.size() - 3) {
            for (auto fn : to_from.second) {
                fp << node_name_map[fn] << "\t\t" << node_name_map[to_from.first] << endl;
            }
            fp << endl;
        }
    }

    //imux
    fp << "from" << "\t\t" << "to(imux medium)" << endl;
    for (auto const& to_from : to_from_map) {
        auto& node = device_ctx.rr_nodes[to_from.first];
        if((node.type() == CHANX || node.type() == CHANY) && node.seg_id() == imux_seg_id) {
            for (auto fn : to_from.second) {
                fp << node_name_map[fn] << "\t\t" << node_name_map[to_from.first] << endl;
            }
            fp << endl;
        }
    }

    fp << "from" << "\t\t" << "to(ipin)" << endl;
    for (auto const& to_from : to_from_map) {
        auto& node = device_ctx.rr_nodes[to_from.first];
        if(node.type() == IPIN) {
            for (auto fn : to_from.second) {
                fp << node_name_map[fn] << "\t\t" << node_name_map[to_from.first] << endl;
            }
            fp << endl;
        }
    }

    //omux
    fp << "from" << "\t\t" << "to(omux)" << endl;
    for (auto const& to_from : to_from_map) {
        auto& node = device_ctx.rr_nodes[to_from.first];
        if((node.type() == CHANX || node.type() == CHANY) && node.seg_id() == omux_seg_id) {
            for (auto fn : to_from.second) {
                fp << node_name_map[fn] << "\t\t" << node_name_map[to_from.first] << endl;
            }
            fp << endl;
        }
    }
}