import json
import numpy as np
from typing import Union, Optional
from pathlib import Path

from PIL import Image, ImageDraw


def validate(
    img_array: np.ndarray,
    required_size: tuple
):
    """
    Data validator.

    Returns
    -------
    output: None

    Parameters
    ----------
    img_array : np.ndarray
        Array representing the image.
    required_size : tuple
        Required image size for correct drawing of fields.

    Notes
    -----
    Validates the following requirements:
      - image dtype is float32 or uint8;
      - image size is equal to the required size.
    In negative case an exception is returned.
    """

    if img_array.shape[:2][::-1] != required_size:
        raise ValueError(f"image size should be {required_size}")
    if img_array.dtype != np.uint8 and img_array.dtype != np.float32:
        raise TypeError(f"unsupported image dtype '{img_array.dtype}', ",
                         "should be float32 or uint8")
    return


def draw_contours(
    array: np.ndarray,
    json_contours: dict,
    color: Union[int, tuple],
    width: int
) -> np.ndarray:
    """
    Function for adding contours on an image.

    Returns
    -------
    output : np.ndarray
        The output image with the drawn contours.

    Parameters
    ----------
    array : np.ndarray
        The input image.
    json_contours : dict
        The json dictionary with the field contours.
    color : Union[int, tuple]
        Pixel intensity (or intensities for not single-channel
        input) of contours.
    width : int
        Contours width.
    """

    img = Image.fromarray(array)
    dr = ImageDraw.Draw(img)

    for obj in json_contours['objects']:
        if obj['type'] == 'region':
            for contour in obj['data']:
                coordinates = contour + [contour[0]]
                dr.line(list(map(tuple, coordinates)), fill=color, width=width)
        else:
            raise TypeError(obj['type'])
    return np.array(img)


def visualize(
    contours_path: Path,
    dst_img_path: Path,
    src_img_path: Optional[Path] = None,
    width: int = 2
):
    """
    Function for visualizing contours.

    Returns
    -------
    output : None
        The result is saved as an image with drawn field contours.

    Parameters
    ----------
    contours_path : Path
        Path to the json file with contours.
    dst_img_path : Path
        Path to save result.
    src_img_path : Path, optional
        Path to the input image.
        If src_img_path is ommited, contours are drawn on a black uint8 image.
    width : int, optional
        Contours width (default 2).

    Notes
    -----
    Expected 1- or 3-channel images of types uint8 or float32.
    For float32 dtype pixel values should be in [0..1].

    Pixel intensity of contours sets to:
      -- 255 for uint8 single-channel image;
      -- (255, 255, 255) for uint8 3-channel image;
      -- 1 for float32 image.
    """

    with open(contours_path, "r") as door:
        json_contours = json.load(door)
    img_size = tuple(json_contours['size'])

    if src_img_path:
        with Image.open(src_img_path) as src_img:
            src_array = np.array(src_img)
            validate(src_array, img_size)
            format = src_img.format
    else:
        src_array = np.zeros(img_size[::-1]).astype(np.uint8)
        format = 'PNG'

    if src_array.dtype == np.uint8:
        c_value = 255
    elif src_array.dtype == np.float32:
        c_value = 1
    if src_array.ndim == 2:
        color = c_value
    elif src_array.ndim == 3:
        color = tuple(np.repeat(c_value, src_array.shape[2]))

    dst_array = draw_contours(src_array, json_contours, color, width)
    dst_img = Image.fromarray(dst_array)
    dst_img.save(dst_img_path, format)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "contours_path", type=Path, help="path to the json file with contours")
    parser.add_argument(
        "dst_img_path", type=Path, help="path to save result")
    parser.add_argument(
        "-src", "--src-img-path", type=Path, help="path to the input image",
        default=None)
    parser.add_argument(
        "-w", "--width", type=int, help="contours width", default=2)
    args = parser.parse_args()
    visualize(**vars(args))

