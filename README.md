# Historical Street View Dataset for MixVPR

This folder contains a cleaned test dataset built from the GPS route metadata of
`Robot_Visual_Navigation_V3`.

The goal is to test visual place recognition with MixVPR on older Google Street
View images.

## What Is Included

```text
streetview-master/
├── data/input/
│   └── route_current_streetview_metadata.csv
├── outputs/from_route_metadata/
│   ├── historical_metadata.csv
│   └── mixvpr_dataset_by_date/
│       ├── 2009-05/
│       ├── 2009-06/
│       ├── 2011-08/
│       ├── 2014-05/
│       ├── downloaded_static_metadata.csv
│       └── README.md
├── scripts/
│   ├── historical_from_csv.py
│   ├── download_static_from_historical_csv.py
│   └── historical_streetview.py
├── src/streetview/
├── .env-example
├── pyproject.toml
└── README.md
```

## Dataset Summary

```text
Route points: 43
Historical candidates per point: 3
Downloaded images: 129
Download errors: 0
Image format: JPG
Image size: 640 x 640
```

Date distribution:

```text
2009-05: 42 images
2009-06: 1 image
2011-08: 43 images
2014-05: 43 images
```

The images are sorted by historical date in:

```text
outputs/from_route_metadata/mixvpr_dataset_by_date/
```

The main CSV index for MixVPR tests is:

```text
outputs/from_route_metadata/mixvpr_dataset_by_date/downloaded_static_metadata.csv
```

## Direction Of Travel

For MixVPR, the images were downloaded in the direction of the route.

The script computes a heading from:

```text
current GPS point -> next GPS point
```

This heading is then used in the Google Street View Static API. The value is
stored in the CSV column:

```text
static_heading
```

## Environment

Use the existing Python environment if available:

```bash
source "/Users/enzocampofranco/Library/Mobile Documents/com~apple~CloudDocs/TPS/Stage/Streetview_env/bin/activate"
```

Or install the package dependencies manually:

```bash
pip install requests pillow pydantic httpx
```

## API Key

The API key is not stored in this cleaned folder.

To download more images, create a local `.env` file:

```bash
cp .env-example .env
```

Then fill it like this:

```text
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
```

## Rebuild The Historical Metadata

From the project folder:

```bash
python scripts/historical_from_csv.py --candidate-limit 3 --before 2015-01
```

This generates:

```text
outputs/from_route_metadata/historical_metadata.csv
```

## Download The MixVPR Test Images

From the project folder:

```bash
python scripts/download_static_from_historical_csv.py \
  --candidate-rank all \
  --limit 0 \
  --heading-source route \
  --sleep 0.15
```

This generates:

```text
outputs/from_route_metadata/mixvpr_dataset_by_date/
```

## Important Note

The direct full-panorama tile endpoint is currently blocked by Google with HTTP
403 responses. For that reason, this cleaned test dataset uses the official
Google Street View Static API.

The resulting images are not full 360 panoramas, but they are useful for VPR
testing because they are:

- historical;
- geolocated around the route;
- linked to the original GPS route points;
- oriented in the direction of travel;
- documented with metadata.
