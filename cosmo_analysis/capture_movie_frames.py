import sys
sys.path.insert(0, '../plotting_ray/')
import plotter
from mpi4py import MPI
import numpy as np
from sys import argv
import yt
from center_finder import find_center

#init mpi
comm = MPI.COMM_WORLD

#setup conditions
line_list = []#['H I', 'O VI', 'C IV']

#take in arguments
if len(argv) == 5:
    filename = argv[1]
    in_dir = argv[2]
    i_name = argv[3]
    out_dir= argv[4]
else:
    raise RuntimeError("Takes 4 arguments: Dataset_fname Ray_directory Ion_name Output_directory")

if comm.rank == 0:
    center, nvec = find_center(filename)
    center = np.array( center.in_units('code_length'), dtype=np.float64)
    nvec = np.array(nvec, dtype=np.float64)
else:
    center= np.zeros(3, dtype=np.float64)
    nvec = np.zeros(3, dtype=np.float64)

comm.Barrier()
comm.Bcast([center, MPI.DOUBLE])
comm.Bcast([nvec, MPI.DOUBLE])
comm.Barrier()

#now actual test
movie =plotter.movie_multi_plot(filename, in_dir, ion_name=i_name,
				absorber_fields=line_list,
                center_gal = center,
                north_vector = nvec,
				out_dir=out_dir,
				wavelength_width=100,
				resolution=0.1)

#split up ray id numbers betweeen proccesors
rayrange = np.arange( len(movie.ray_files) )
rayrange_split = np.array_split(rayrange, comm.size)
my_range = rayrange_split[ comm.rank ]

#calc the number_density limits if root processor
if comm.rank == 0:
    #get middle ray to represent scale
    num_rays = len(movie.ray_files)
    middle_ray_file = movie.ray_files[ int(num_rays/2) ]
    mid_ray= yt.load( f"{movie.ray_dir}/{middle_ray_file}" )

    #get median num density
    num_density = np.array(mid_ray.data[ f"{movie.ion_p_name()}_number_density" ], dtype=np.float64)
    med = np.median(num_density)

    #estimate min max values to number dense plot. and markers positioning
    num_density_range = np.array( [0.01*med, 1000*med] , dtype=np.float64)

else:
    num_density_range = np.empty(2, dtype=np.float64)

comm.Barrier()
#broadcast the number density limits
comm.Bcast( [num_density_range, MPI.DOUBLE] )

#create movie frames
movie.create_movie(num_dense=num_density_range, ray_range = my_range)
print("-------------- {} finished----------------".format(comm.rank))

comm.Barrier()
if comm.rank==0:
    print("-"*76)
    print("All process finished :)")
    print("-"*76)