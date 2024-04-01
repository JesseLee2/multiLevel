# multiLevel MUX 
FPGA routing arcitecture based on multi-level MUX framework, including:
1. toolchains: modified COFFE2 and VTR.
2. multiLevel-BO: automatic design space exploration based on Bayesian Optimization.
3. archFiles: example architecture description file of multi-level MUX.

# Getting Started
## Dependencies
#### HSPICE (for COFFE2 in toolchains)
#### Python3 (for COFFE2 in toolchains)
#### CMake (for VTR in toolchains)
#### GCC (for VTR in toolchains)
#### Mongdb (not necessary, for BO)

## clone the repository

## Build and run

Compile VTR at first. The libs and route folders need to replace the ones in VTR 8.0
```sh
cd ./toolchains/VTR
make
```

For running the DSE flow
```sh
cd multiLevel-BO
./run_hyperopt_seg.sh
```

change the VTR file path as you need. And the baseline archtecture are changable too.
