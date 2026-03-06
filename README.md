# Noise-Aware Circuit Clustering

This repository contains the code for the paper "Noise-Aware Circuit Clustering based on Analytical Placement Evolution" Published in SLIP '24: 2024 ACM International Workshop on System-Level Interconnect Pathfinding. The paper is available at [ACM Digital Library](https://dl.acm.org/doi/10.1145/3708358.3709348).

Fork Notes: if you change the code
------------
- rm -rf `build` and `install` directories
- `mkdir build` and `cd build`
- `cmake .. -DCMAKE_INSTALL_PREFIX=/DREAMPlace/install -DPython_EXECUTABLE=$(which python) -DCMAKE_DISABLE_FIND_PACKAGE_CUDA=ON`
- `make -j<# of threads to use for job>`
- `make install`

Fork Notes: how to reproduce clustering pipeline
------------
In DREAMPlace:
- Go to `test/<benchmark suite>/<benchmark>.json`
- add at the end of the file: `"dump_snapshot_interval" : 100, "dump_snapshot_count" : 10`
- rerun DREAMPlace
- go to `results/<benchmark>`, copy paste everything in `snapshots` folder to designated folder in noise-aware-circuit-clustering repo
- edit `.ipynb` file accordingly
- run `.ipynb` file to analyze clusters and ICNs given your snapshots

Requirements
------------
- Python 3.6 or higher
- Numpy
- Networkx
- Matplotlib
------------

Running the Code
-------------------
1. Create a virtual environment and install the required packages 
2. Run the following python notebook files ./main.ipynb
-------------------

Using Different Benchmarks
-------------------
We provide an example of using adaptec1 benchmark from ispd'05. You can replace the benchmark with your own benchmark by following the steps below:
1. When running DREAMPlace, save the intermediate results of the placement as new .pl files. An interval of 50-100 iterations is recommended.
2. Copy the .nets file and the .nodes files under the ./test and set the path `lef_file` and `def_file` in [main.ipynb](https://github.com/Hikipeko/noise-aware-circuit-clustering/blob/master/main.ipynb) accordingly.
3. You may want to change `prefix` to the prefix of your intermediate placement files.
4. You may also want to change the `cluster_file` and `output_file` to the path where you want to save the clustering results.
4. Run the code in [main.ipynb](https://github.com/Hikipeko/noise-aware-circuit-clustering/blob/master/main.ipynb).

If you have any questions, please feel free to open an issue.

Acknowledgements
-------------------
This codebase is mainly contributed by Zhiyuan Chen and Zhan Song.
