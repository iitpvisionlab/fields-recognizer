Parcel segmentation algorithm.

Repository structure
--------------------
--------------------

- /README.md - This file;
- /fields_recognizer.py  - Python 3.8 implementation of the algorithm;
- /visualize.py - Python 3.8 script for visualizing parcel contours on the image;
- /requirements.txt      - Required Python packages;
- /schema.json - The json schema for validating the json-file with parcel contours.

Data description
----------
----------

### MSAVI2 images

**Image format**: tiff.

**Required data type**: float32.

**Required data range**: [0..1].

To compute instant (obtained  for a specific date) msavi2 image $I^t$ use follow formulas:
$$
I^t = \frac{(NIR^t - RED^t) * (1 + L^t)}{(NIR^t + RED^t + L^t)},
$$

$$
L^t = 1 - 0.5\cdot(2NIR^t + 1 - \sqrt{(2NIR^t + 1)^2 - 8(NIR^t - RED^t))}),
$$

where $NIR^t$, $RED^t$ - instant satellite images of near-infrared and red channels respectively.

Aggregated msavi2 image using in the algorithm is computed with:

$$
\tilde{I}_{i,j} = \frac{1}{k_{i,j}} \sum_{t=0}^{k_{i,j}-1} I^{t}_{i, j},
$$
where $(i,j)$ - the pixel coordinates, $t$ - the index of the msavi2 image in the historical dataset,  $k_{i,j}$ - the number of measurements available for $(i,j)$-th pixel.

Actual aggregated msavi2 lies in the range [-1..1]. For a correct result, set negative values ​​on the image to 0.

### Edges map images

**Image format**: tiff.

**Required data type**: float32.

**Required data range**: [0..1].

The accumulated edge map $\tilde{E}$ is calculated as the sum of instant boundaries normalized by the number of measurements:
$$
\tilde{E}_{i,j} = \frac{1}{k_{i,j}} \sum_{t=0}^{k_{i,j}-1} E(I^t)_{i, j},
$$
where $E(I^t)$ - the dilated edges map extracted from the instant msavi2 image using the Canny operator. $E(I^t)$ is dilated using disk structure element with radius 1.

### Json-files with field contours

Information about field contours (ground truth or extracted by the algorithm) is stored in a json-file.
Such file contains the following information:
- size - Image size for which the field map is created;
- objects - List of field contours;
  - data - List of the contour coordinates. First item represents exterior of the contour, next items represent holes in the contour.
  - type - Type of the object. It must be 'region'.

The detailed structure of the json-file with contours is described in the `schema.json`.

Demo materials
-----------------
-----------------

To test the program, you can download demo materials from the Zenodo repository:

https://hereisalink.com

The ground truth parcel contours and pre-computed images of the aggregated msavi2 and edges maps are available here.

Examples
--------
--------

Example of the algoithm usage (38ULB area).

Download the following files from https://hereisalink.com to the folder with the `fields_recognizer.py` script:
- ground truth parcel contours `38ULB_markup.json`;
- aggregated msavi2 image `38ULB_msavi2.tiff`;
- edges map `38ULB_edges.tiff`.

Next run the aglorithm with:
```
python3 fields_recognizer.py 38ULB_msavi2.tiff 38ULB_edges.tiff output.json
```

To visualize recognized parcel contours `output.json` on the msavi2 image run:
```
python3 visualize.py output.json vis_output.tiff -src 38ULB_msavi2.tiff
```
The result image with contours is saved in `vis_output.tiff`.

You can also visualize ground truth parcel contours:
```
python3 visualize.py 38ULB_markup.json vis_markup.tiff -src 38ULB_msavi2.tiff
```

Notes
-----
-----

The algorithm does not include the step of aggregating vegetation indices and edges. Compute the aggregated msavi2 and aggregated edges map before running the script or download demo from https://hereisalink.com.

