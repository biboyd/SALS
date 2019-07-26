import sys
sys.path.insert(0, '/mnt/home/boydbre1/Repo/CGM/plotting_ray/')
import plotter
from mpi4py import MPI
import numpy as np
from sys import argv
import yt
from center_finder import find_center
from os import makedirs, listdir

def main():
    #init mpi
    comm = MPI.COMM_WORLD

    #setup conditions
    line_list = []#['H I', 'O VI', 'C IV']

    #take in arguments
    if len(argv) == 6:
        filename = argv[1]
        ray_dir = argv[2]
        i_name = argv[3]
        out_dir= argv[4]
        use_bv = argv[5]
    else:
        raise RuntimeError("Takes 5 arguments: Dataset_fname Ray_directory Ion_name Output_directory use_bv?")

    if comm.rank == 0:
        center, nvec, rshift, bulk_vel = find_center(filename)
        center = np.array( center.in_units('code_length'), dtype=np.float64)
        nvec = np.array(nvec, dtype=np.float64)
        rshift = np.array([rshift], dtype=np.float64)
        bulk_vel = np.array(bulk_vel, dtype=np.float64)
    else:
        center= np.zeros(3, dtype=np.float64)
        nvec = np.zeros(3, dtype=np.float64)
        rshift = np.zeros(1, dtype=np.float64)
        bulk_vel = np.zeros(3, dtype=np.float64)

    #broadcast information to all processes
    comm.Barrier()
    comm.Bcast([center, MPI.DOUBLE])
    comm.Bcast([nvec, MPI.DOUBLE])
    comm.Bcast([rshift, MPI.DOUBLE])
    comm.Bcast([bulk_vel, MPI.DOUBLE])
    comm.Barrier()

    #check to see if should use bulk velocity
    if use_bv != 'True':
        bulk_vel=None

    #set up multiplot settings
    mp_kwargs = dict(filename, in_dir, ion_name=i_name,
    				                absorber_fields=line_list,
                                    center_gal = center,
                                    north_vector = nvec,
                                    out_dir=out_dir,
                                    redshift=rshift[0],
                                    bulk_velocity=bulk_vel,
                                    use_spectacle= True,
                                    plot_spectacle=True,
                                    wavelength_width=20,
                                    resolution=0.1)


    #collect only ray files in ray_dir
    ray_files=[]
    for f in listdir(ray_dir):
        #check hdf5 file
        if (f[-3:] == ".h5"):
            ray_files.append("/".join(ray_dir, f))

    #sort the rays
    #ray_files = sorted(ray_files)

    #split up rays betweeen proccesors
    ray_files_split = np.array_split(ray_files, comm.size)
    my_rays = ray_files_split[ comm.rank ]

    #calc the number_density limits if root processor
    if comm.rank == 0:
        #get middle ray to represent scale
        num_rays = len(ray_files)
        middle_ray_file = ray_files[ int(num_rays/2) ]
        mid_ray= yt.load( f"{ray_dir}/{middle_ray_file}" )

        #get median num density
        num_density = np.array(mid_ray.data[ f"{ion_p_num(i_name)}" ], dtype=np.float64)
        med = np.median(num_density)

        #estimate min max values to number dense plot. and markers positioning
        num_density_range = np.array( [0.01*med, 1000*med] , dtype=np.float64)

    else:
        num_density_range = np.empty(2, dtype=np.float64)

    comm.Barrier()
    #broadcast the number density limits
    comm.Bcast( [num_density_range, MPI.DOUBLE] )

    mp_kwargs.update({'num_dense_max': num_density_range[0],
                      'num_dense_min': num_density_range[1],
                      'markers_nd_pos': num_density_range[1]*5})

    #create movie frames
    create_frames(rays=my_rays, **mp_kwargs)
    print("-------------- {} finished----------------".format(comm.rank))

def create_frames(rays,
                  slice_width=None,
                  slice_height=None, multi_plot_kwargs={}):
    """
    creates a movie by combining all the plots made from the ray in ray_dir

    Parameters:
        rays
        num_dense
        slice_width
        slice_height
    """

    #create fig to plot all on
    fig = plt.figure(figsize=(10, 10))

    #create initial slice
    mp = plotter.multi_plot(ray_filename=rays[0], **multi_plot_kwargs)
    mp.create_slice()

    #clear annotations
    mp.slice.annotate_clear()

    for ray_fname in rays:
        #load in new ray
        mp.ray = yt.load(ray_fname)

        #add ray and other annotations
        ray_num = get_ray_num(ray_fname)
        mp.add_annotations()
        mp.slice.annotate_title(f"ray {ray_num}")

        #create and save frame
        outfile = f"{mp.out_dir}/mp{ray_num}.png"
        mp.create_multi_plot(outfile)

        #close ray files and clear axes/annoations
        self.ray.close()

        mp.fig.clear()
        mp.slice.annotate_clear()


def get_ray_num(file_path):
    filename = file_path.split('/')[-1]
    num = filename[3:-3]

    return num
def ion_p_num(ion_name):
    """
    convert ion species name from trident style to one that
    can be used with h5 files
    """
    #split up the words in ion species name
    ion_split = ion_name.split()
    #convert num from roman numeral. subtract run b/c h5
    num = trident.from_roman(ion_split[1])-1

    #combine all the names
    outname = f"{ion_split[0]}_p{num}_number_density"
    return outname

if __name__ == '__main__':
    main()
