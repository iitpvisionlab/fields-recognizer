import numpy as np
from pathlib import Path

from shapely.geometry import Polygon
from skimage.io import imread
from skimage.feature import canny
from skimage.filters import threshold_otsu
from skimage.morphology import disk, closing, binary_dilation
from skimage.measure import label, regionprops,  find_contours,\
                            approximate_polygon


def write_json(
    json_obj: dict,
    filepath: Path
):
    """
    Function for saving json dictionary.

    Returns
    -------
    output : None

    Parameters
    ----------
    json_obj : dict
        Input json dictionary.
    filepath : Path
        Path to save json dictionary.
    """

    import json
    with open(filepath, 'w') as door:
        json.dump(json_obj, door, indent=2, ensure_ascii=False)


def fix_object(
    obj: dict,
    skip_unfixable: bool = True
) -> list:
    """
    Function for fixing invalid contour.

    Returns
    -------
    output : list
        List of fixed contours.

    Parameters
    ----------
    obj : dict
        Input contour dictionary.
    skip_unfixable : bool, optional
        Raise RuntimeError if can not repair a contour, True by default.

    Notes
    -----
    - Contour with self-intersections will be splited into few contours
    at the points where they touch.
    - Point or segment (1-point or 2-point contour respectively)
    will be removed.
    - If value of 'type' key in contour dictionary is not 'region',
    contours will be removed.
    """

    if obj['type'] != 'region' or len(obj['data']) < 3:
        return [None]
    p = Polygon(obj['data'])
    if not p.is_valid:
        p_clean = p.buffer(0)
        if p_clean.is_valid and p_clean.type == 'MultiPolygon':
            objs = []
            for g in p_clean.geoms:
                tmp = obj.copy()
                tmp['data'] = g.exterior.coords[:]
                objs.append(tmp)
            return objs
        if p_clean.is_valid and p_clean.exterior.coords:
            obj['data'] = p_clean.exterior.coords[:]
        elif skip_unfixable:
            return [None]
        else:
            raise RuntimeError(f"can't fix polygon {p}")
    return [obj]


def fix_contours(
    json_contours: dict,
    skip_unfixable: bool = True
) -> dict:
    """
    Function for fixing invalid contours in json.

    Returns
    -------
    output : dict
        Json dictionary with fixed contours.

    Parameters
    ----------
    json_contours : dict
        Input json dictionary with contours.
    skip_unfixable : bool, optional
        Raise RuntimeError if can not repair a contour, True by default.

    Notes
    -----
    Input json dictionary also will be fixed.
    """

    new_objs = list()
    for obj in json_contours['objects']:
        new_objs.extend(fix_object(obj, skip_unfixable))
    json_contours['objects'] = list(filter(None, new_objs))
    return json_contours


def get_region_json(
    region
) -> dict:
    """
    The function to convert the RegionProperties of the contour
    to the dictionary with the contour coordinates.

    Returns
    -------
    output : dict
        The dictionary with contour coordinates.
        Dictionary structure: {'type': 'region', 'data': [coordinates]}

    Parameters
    ----------
    region : RegionProperties
        The RegionProperties object described contour.
    """

    field_mask = region.filled_image
    field_mask = np.pad(field_mask, 1, mode='constant') != 0
    contours = find_contours(field_mask, 0)
    contours = [approximate_polygon(c, 1) - 1 for c in contours]
    bbox = region.bbox
    new_bbox = (bbox[0], bbox[1], bbox[3], bbox[2])
    r_json = list()
    for cont in contours:
        new_coord = list()
        for point in cont:
            new_coord.append((point[1]+new_bbox[1], point[0]+new_bbox[0]))

        region_json = {'type': 'region', 'data': new_coord}
        r_json.append(region_json)
    return r_json


def regionprops_to_json(
    regions: list,
    size: list,
) -> dict:
    """
    The function to convert a list of contour' RegionProperties to a
    json dictionary with contours.

    Returns
    -------
    output : dict
        The json dictionary with contours.
        It contains float pixel coordinates of each contour.

    Parameters
    ----------
    regions : list
        List of contour' RegionProperties.
    size : list
        Image size where contours is defined.
    """

    json_contours = {
        'objects': list(),
        'size': size
    }
    for reg in regions:
        json_contours['objects'].extend(get_region_json(reg))
    return json_contours


def filter_contours(
    json_contours: dict,
    min_t: int,
    max_t: int
) -> dict:
    """
    Function for filtering contours by area.

    Returns
    -------
    output : dict
        Filtered json dictionary.

    Parameters
    ----------
    json_contours : dict
        Input json dictionary.
    min_t : int, optional
        Minimum area threshold
    max_t : int, optional
        Maximum area threshold

    Notes
    -----
    Since json_contours contains pixel coordinates,
    area thresholds must be specified in pixels.
    """

    filtered_contours = json_contours.copy()
    filtered_contours['objects'] = []
    if not max_t:
        max_t = np.inf
    for obj in json_contours['objects']:
        p = Polygon(obj['data'])
        if p.area >= min_t and p.area <= max_t:
            filtered_contours['objects'].append(obj)
    return filtered_contours


def coordinates_formatting(
    json_contours: dict,
) -> dict:
    """
    Function for formatting representation of the contours coordinates.

    Input coordinates representation:
    [[x1,y1], [x2,y2]...[xn, yn]],
    where xi,yi - contour coordinates.

    Output coordinates representation:
    [[[x1,y1], [x2,y2]...[xn, yn]]].
    This representation assumes that the first item in the list is the
    exterior of the contour, the next items are holes in the contour.

    Returns
    -------
    output : dict
        Json dictionary with correct coordinates representation.

    Parameters
    ----------
    json_contours : dict
        Input json dictionary.
    """

    for obj in json_contours['objects']:
        obj['data'] = [obj['data']]
    return json_contours


def find_fields(
    index_img: np.ndarray,
    edges: np.ndarray,
    w_dilate: int,
    w_closing: int,
    low_veg_thresh: float,
    min_area_thresh: float,
    max_area_thresh: float
) -> dict:
    """
    Algorithm of field boundaries searching.
    Steps:
    1. Generate mask of low vegetation regions.
    2. Detect mask of potential field regions.
    3. Morphological filtration of Canny edges map.
    4. Segment fields using binary edges map.
    5. Obtain connected components.
    6. Obtain field contours and vectorization.
    7. Validate and fix contours.
    8. Filter contours by area.

    Returns
    -------
    output : dict
        The json dictionary with float pixel coordinates of the contours
        on the image.

    Parameters
    ----------
    index_img : np.ndarray
        2D array of msavi2 image.
    edges : np.ndarray
        2D array of edges image.
    w_dilate : int
        The radius of the disk-shaped footprint
        used for dilate low vegetation mask.
    w_closing : int
        The radius of the disk-shaped footprint
        used for closing edges map.
    low_veg_thresh : float
        The low vegetation threshold used for generate the low vegetation mask.
        It lies in range (0; 1).
    min_area_thresh : float
        The minimum field area threshold.
    max_area_thresh : float
        The maximum field area threshold.
    """

    #  Generate mask of low vegetation regions
    low_veg_mask = np.zeros(index_img.shape, dtype=bool)
    low_veg_mask[index_img <= low_veg_thresh] = True
    binary_dilation(low_veg_mask, disk(w_dilate), out=low_veg_mask)

    #  Detect mask of potential field regions
    field_mask = np.zeros(index_img.shape, dtype=bool)
    t_otsu_fields = threshold_otsu(index_img[~low_veg_mask])
    field_mask[(index_img < t_otsu_fields) & (~low_veg_mask)] = True

    #  Morphological filtration of Canny edges map
    if edges is not None:
        t_otsu_edges = threshold_otsu(edges)
        edges_b = (edges >= t_otsu_edges).astype(bool)
    else:
        edges = canny(index_img, sigma=0.01)
        edges_b = edges.astype(bool)

    edges_b = closing(edges_b, disk(w_closing)).astype(np.int16, copy=False)

    #  Segmenting fields using binary edges map
    field_mask_wo_edges = field_mask - edges_b
    np.clip(field_mask_wo_edges, 0, 1, out=field_mask_wo_edges)

    #  Obtaining connected components
    labeled_img = label(field_mask_wo_edges)

    #  Obtaining field contours and vectorization
    src_regions = regionprops(labeled_img)
    dst_regions = regionprops_to_json(src_regions, list(labeled_img.shape))

    #  Validating and fixing contours
    dst_regions = fix_contours(dst_regions)

    #  Filtering contours by area
    dst_regions = filter_contours(dst_regions, min_area_thresh, max_area_thresh)

    dst_regions = coordinates_formatting(dst_regions)

    return dst_regions


def run(
    index_img_path: Path,
    edges_img_path: Path,
    output_path: Path,
    w_dilate: int,
    w_closing: int,
    low_veg_thresh: float,
    min_area_thresh: float,
    max_area_thresh: float,
    spatial_resolution: int
):
    """
    The main runner function.

    Returns
    -------
    output : None
        The result is saved as json file with found fields contours.

    Parameters
    ----------
    index_img_path : Path
        The aggregated msavi2 image path.
    edges_img_path : Path
        The accumulated edges image path.
    w_dilate : int
        The radius of the disk-shaped footprint
        used for dilate low vegetation mask.
    w_closing : int
        The radius of the disk-shaped footprint
        used for closing edges map.
    low_veg_thresh : float
        The low vegetation threshold used for generate the low vegetation mask.
        It lies in range (0; 1).
    min_area_thresh : float
        The minimum field area threshold.
    max_area_thresh : float
        The maximum field area threshold.
    spatial_resolution : int
        The image spatial resolution, m/pixel.

    Notes
    -----
    For correct result the images should be of float32 type with values in
    [0; 1] range.
    """

    index_img = imread(index_img_path)
    np.clip(index_img, 0, 1, out=index_img)

    edges_img = imread(edges_img_path)

    resolution_factor = (spatial_resolution * 1e-3) ** 2
    min_area_thresh = min_area_thresh / resolution_factor
    max_area_thresh = max_area_thresh / resolution_factor

    result_json = find_fields(
        index_img, edges_img, w_dilate, w_closing,
        low_veg_thresh, min_area_thresh, max_area_thresh
        )

    write_json(result_json, output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "index_img_path", type=Path, help="path to the index image")
    parser.add_argument(
        "edges_img_path", type=Path, help="path to the edges image")
    parser.add_argument(
        "output_path", type=Path, help="path to output directory")
    parser.add_argument(
        "-wd", "--w-dilate", type=int, help="struct element size", default=5)
    parser.add_argument(
        "-wc", "--w-closing", type=int, help="struct element size", default=2)
    parser.add_argument(
        "-low", "--low-veg-thresh", type=float, help="low vegetation threshold value",
        default=0.1569)
    parser.add_argument(
        "-minar", "--min-area-thresh", type=float, help="min area threshold, km^2", default=0.05)
    parser.add_argument(
        "-maxar", "--max-area-thresh", type=float, help="max area threshold, km^2", default=1e3)
    parser.add_argument(
        "-res", "--spatial-resolution", type=int, help="image spatial resolution, m/pixel", default=10)
    args = parser.parse_args()
    run(**vars(args))

