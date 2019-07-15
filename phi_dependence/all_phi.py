# Measure a large collection of azimuthal angles
# to create a statistical analysis btwn col density and the polar angle
# phi = polar in this case (bugs me too but just following convention)
import sys
sys.path.insert(0, '/mnt/home/boydbre1/Repo/CGM/cosmo_analysis/')
import yt
import trident
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation
from mpi4py import MPI
from measure_phi import get_coord, construct_rays
from sys import argv
from center_finder import find_center
from os import listdir
def main(ds_fname, center,
         impact_param,
         north_vector=[0, 0, 1],
         n_az_angle=50,
         n_rays=50,
         ray_length=200,
         rand_seed=None,
         out_dir="./"):
    """
    Main function for measuring the polar angle at many azimuthal angles
    to produce a statistical analysis betweeen column density and polar angle

    Parameters:
        ds_fname : string/path : path/filename of dataset to load
        center : array like object : Center of galaxy in code_length
        impact_param : float : impact parameter of rays in kpc
        north_vector : array like object : north/normal vector of galaxy.
                Perpendicular to the disk
        n_az_angle : int : number of azimuthal angles to compute over
        n_rays : int : number of rays to compute per azimuthal angle
        ray_length : float : length of rays in kpc
        rand_seed : int : seed to give to random number generator. Defaults to no seed
        out_dir : str/path : directory where rays and polar angle and column density
                data will be output

        Returns:
            none
    """
    #start parallelization
    comm = MPI.COMM_WORLD
    #divy up the angles evenly
    n_procs = comm.size
    num_angles_arr = np.zeros(comm.size, dtype=int) + n_az_angle//n_procs
    #add remaining angles to firt processes
    num_angles_arr[:n_az_angle%n_procs] += 1

    ds = yt.load(ds_fname)
    ion = 'H I'
    north_vector = np.array(north_vector)/np.linalg.norm(north_vector)
    #give units to inputs
    north_vector = ds.arr(north_vector, 'dimensionless')
    center = ds.arr(center, 'code_length').in_units('kpc')
    ray_length = ds.quan(ray_length, 'kpc')

    #define initial axis of rotation
    init_ax_rotation = np.array( [north_vector[2], 0, -north_vector[0]] )
    #check not zero vector
    if init_ax_rotation[0] == 0 and init_ax_rotation[2] == 0:
        #switch to a non zero vector
        init_ax_rotation = np.array( [0, north_vector[2], -north_vector[1]] )

    if comm.rank == 0:
        if rand_seed is not None:
            np.random.seed(rand_seed)

        #randomly compute azimuthal angles
        az_angles = np.random.uniform(0, 2*np.pi, n_az_angle)
    else:
        az_angles = np.zeros(2)
    #create array to store phi_array/col dense data
    phi_col_dense = np.empty((n_az_angle*n_rays,2), dtype=np.float64)
    my_az_angles = np.empty(num_angles_arr[comm.rank], dtype=np.float64)
    comm.Scatterv([az_angles, num_angles_arr, MPI.DOUBLE],
                  [my_az_angles, MPI.DOUBLE])

    my_phi_col_dense = np.empty((num_angles_arr[comm.rank]*n_rays, 2))
    #use az_angle to construct vectors to rotate about
    for i, azimuth_angle in enumerate(my_az_angles):
        #create rotation vector. use to rotate initial axis of rotation
        north_rot_vector = north_vector*azimuth_angle
        az_rot = Rotation.from_rotvec(north_rot_vector)

        ax_rotation = az_rot.apply(init_ax_rotation)

        #get coordinates and angles rel to center
        rs_rel, phi_array = get_coord(north_vector, impact_param, ax_rotation, n_rays)
        rs_rel = ds.arr(rs_rel, 'kpc')

        #construct rays
        rout_dir = f"{out_dir}/rank{comm.rank}_angle{i}"

        ray_dir = construct_rays(ds, rs_rel, center,
                                 ax_rotation, ray_length,
                                 n_rays, ion, rout_dir)
        #get files from directory
        ray_files = []
        for file in listdir(ray_dir):
            if file[-3:] == ".h5":
                ray_files.append(file)
        ray_files = sorted(ray_files)

        #get column density from rays
        col_dense = np.empty(n_rays)
        for j in range(n_rays):
            fname="/".join((ray_dir, ray_files[j]))
            ray = yt.load(f"{fname}")
            col_dense = np.sum( ray.data["H_p0_number_density"] * ray.data['dl'])

            #store data
            my_phi_col_dense[i*n_rays + j] = [phi_array[j], col_dense]

            ray.close()

    #calc the number of entries for each process
    num_cnts =  num_angles_arr*2*n_rays
    #collect all data from processes
    comm.Gatherv([my_phi_col_dense, MPI.DOUBLE],
                 [phi_col_dense,num_cnts, MPI.DOUBLE])

    if comm.rank==0:
        np.save(f"{out_dir}/phi_col_dense_data", phi_col_dense)

        plt.scatter(np.rad2deg(phi_col_dense[:, 0]), np.log10(phi_col_dense[:,1]))
        plt.savefig(f"{out_dir}/myplot.png")
        print('all done')


if __name__ == '__main__':
    ds = argv[1]
    b = float(argv[2])
    c, nv, r, bv = find_center(ds)
    main(ds, c, b, north_vector=nv, n_rays=5, n_az_angle=4, rand_seed=16)