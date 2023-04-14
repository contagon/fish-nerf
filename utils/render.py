import sys
from scipy.spatial.transform import Rotation

sys.path.append("../fish_nerf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from pytorch3d.renderer import PerspectiveCameras  # noqa: E402
from pytorch3d.renderer import look_at_view_transform  # noqa: E402

from fish_nerf.ray import get_pixels_from_image  # noqa: E402
from fish_nerf.ray import get_rays_from_pixels  # noqa: E402


def create_surround_cameras(radius, n_poses=20, up=(0.0, 1.0, 0.0), focal_length=1.0):
    """
    Spiral cameras looking at the origin
    """
    cameras = []

    for theta in np.linspace(0, 2 * np.pi, n_poses + 1)[:-1]:
        if np.abs(up[1]) > 0:
            eye = [
                np.cos(theta + np.pi / 2) * radius,
                0,
                -np.sin(theta + np.pi / 2) * radius,
            ]
        else:
            eye = [
                np.cos(theta + np.pi / 2) * radius,
                np.sin(theta + np.pi / 2) * radius,
                2.0,
            ]

        R, T = look_at_view_transform(
            eye=(eye,),
            at=([0.0, 0.0, 0.0],),
            up=(up,),
        )

        cameras.append(
            PerspectiveCameras(
                focal_length=torch.tensor([focal_length])[None],
                principal_point=torch.tensor([0.0, 0.0])[None],
                R=R,
                T=T,
            )
        )

    return cameras


def render_images(model, translation, num_images, save=False, file_prefix=""):
    # TODO: Make this work for both regular / fisheye cameras
    # (would be cool to see renders for both!)
    """
    Render a list of images from the given viewpoints.

    """
    all_images = []
    device = list(model.parameters())[0].device


    # Rotate around the origin of the camera. Aka, assign rotations to the input translation.
    for theta_ix, theta in enumerate(np.linspace(0, 2 * np.pi, num_images + 1)[:-1]):
        quat = Rotation.from_euler('z', theta, degrees=True).as_quat()
        pose = np.array([*translation, *quat])

        pixel_coords, pixel_xys = get_pixels_from_image(
            model.camera_model, valid_mask=model.valid_mask, filter_valid=True
        )

        # A ray bundle is a collection of rays. RayBundle Object includes origins, directions, sample_points, sample_lengths. Origins are tensor (N, 3) in NED world frame, directions are tensor (N, 3) of unit vectors our of the camera origin defined in its own NED origin, sample_points are tensor (N, S, 3), sample_lengths are tensor (N, S - 1) of the lengths of the segments between sample_points.
        ray_bundle = get_rays_from_pixels(pixel_coords, model.camera_model, model.X_ned_cam, pose, debug=False)
        
        ray_bundle.origins = ray_bundle.origins.to(dtype=torch.float32)
        ray_bundle.directions = ray_bundle.directions.to(dtype=torch.float32)

        # Run model forward
        out = model(ray_bundle)

        # Return rendered features (colors)
        image = np.zeros((model.camera_model.ss.W, model.camera_model.ss.H, 3))
        image[model.valid_mask == 1, :] = out["feature"].cpu().detach().numpy()
        all_images.append(image)

        # Save
        if save:
            plt.imsave(f"{file_prefix}_{theta}.png", image)

    return all_images
