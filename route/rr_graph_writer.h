/*
 * This function writes the RR_graph generated by VPR into a file in XML format
 * Information included in the file includes rr nodes, rr switches, the grid, block info, node indices
 */

#ifndef RR_GRAPH_WRITER_H
#define RR_GRAPH_WRITER_H

void write_rr_graph(const char* file_name, const std::vector<t_segment_inf>& segment_inf);
void write_one_gsb_arch(const char* file_name, int x, int y, const std::vector<t_segment_inf>& segment_inf);
#endif
