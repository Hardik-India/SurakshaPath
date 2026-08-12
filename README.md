# SurakshaPath — Predictive Road Accident Hotspot Detection & Intervention Simulator



**Smart India Hackathon 2026 — Transportation & Mobility**



SurakshaPath is a data-driven tool that identifies accident-prone road junctions in Central Kolkata and predicts how specific safety interventions (speed breakers, traffic signals, turn restrictions) would affect conflict rates — before any real-world investment is made.



Built on a real, imported Central Kolkata road network simulated in \[SUMO](https://eclipse.dev/sumo/), using simulated traffic conflicts (a "surrogate safety measure," inspired by FHWA's SSAM methodology) as a proxy for accident risk, since real accident records in India are too sparse and inconsistently geo-tagged to train on directly.



---



## What It Does



1. **Identifies conflict hotspots** across ~600+ real junctions in Central Kolkata, using SUMO-simulated near-miss ("conflict") events as a dense, statistically richer proxy for rare real-world accidents.

2. **Visualizes risk** on an interactive heatmap with a live legend, color-coded by conflict density.

3. **Lets a user click any junction** and see either why it's a safe/quiet zone, or — for conflict zones — get an automatic, written recommendation for the best available intervention.

4\. \*\*Predicts intervention outcomes\*\*: for junctions we've directly simulated, results are ground-truth (measured via repeated SUMO runs); for others, a trained ML model estimates the likely effect.



\---



\## Architecture



```

OpenStreetMap export (map.osm)

&#x20;       │

&#x20;       ▼

netconvert → central\_kolkata.net.xml  (real road network: lanes, signals, junctions)

&#x20;       │

&#x20;       ▼

SUMO simulation (full city, \~1hr) + SSM device → conflict log (central\_kolkata\_ssm.xml)

&#x20;       │

&#x20;       ▼

Node-level feature extraction + conflict mapping (build\_node\_features.py, build\_baseline\_conflicts.py)

&#x20;       │

&#x20;       ▼

Per-junction intervention testing:

&#x20; crop 300m sub-network → apply intervention (speed breaker / add signal / retime signal / turn restriction)

&#x20; → re-simulate with replicated random seeds → measure conflict change

&#x20;       │

&#x20;       ▼

Training dataset (surrogate\_training\_data.csv) → ML surrogate model

&#x20;       │

&#x20;       ▼

Flask web app (app.py) → interactive map + live "what-if" intervention predictions

```



\---



\## Tech Stack



\- \*\*Simulation\*\*: \[SUMO](https://eclipse.dev/sumo/) (Simulation of Urban Mobility), `netconvert`, `sumolib`, TraCI

\- \*\*Data/ML\*\*: Python, pandas, scikit-learn (Random Forest classifier + Ridge regression), scipy

\- \*\*Backend\*\*: Flask

\- \*\*Frontend\*\*: Leaflet.js, Leaflet.heat, vanilla JS

\- \*\*Map data\*\*: OpenStreetMap



\---



\## Project Structure



```

├── app.py                       # Flask web server

├── predict\_intervention.py      # Inference: ground-truth lookup + ML fallback

├── intervention\_tools.py        # Network modification functions (speed breaker, signal, turn restriction)

├── run\_pipeline.py              # Core per-junction scenario runner (crop → intervene → simulate)

├── crop\_subnetwork.py           # Extracts a local sub-network around a junction

├── build\_node\_features.py       # Extracts static junction features from the network

├── build\_node\_baseline.py       # Aggregates lane-level data to junction-level baseline behavior

├── build\_baseline\_conflicts.py  # Maps simulated conflicts to nearest junction (geo-matched)

├── build\_lookup.py              # Builds signal \& geo-coordinate lookup tables

├── build\_training\_dataset.py    # Assembles the final ML training dataset

├── train\_model.py               # Trains the classifier + regression surrogate models

├── check\_delta\_distribution.py  # Diagnostic: sanity-checks intervention effect distributions

├── run\_overnight.py             # Full-city, long-duration data collection script

├── run\_batch.py / run\_batch\_addsignal.py / run\_batch\_turnrestriction.py / regenerate\_full\_batch.py

│                                 # Batch scenario runners for different intervention types

├── templates/index.html         # Web app frontend markup

├── static/app.js, style.css     # Web app frontend logic \& styling

├── archive/                     # Exploratory/diagnostic scripts from development (kept for history)

├── central\_kolkata.net.xml      # Compiled SUMO network for Central Kolkata

├── map.osm                      # Raw OpenStreetMap export

├── node\_features.csv, baseline\_conflicts\_per\_node.csv, batch\_intervention\_results.csv,

│   surrogate\_training\_data.csv  # Core datasets

└── surrogate\_model\_classifier.pkl, surrogate\_model\_ridge.pkl  # Trained models

```



\---



\## How to Run



\*\*Prerequisites\*\*: \[SUMO](https://eclipse.dev/sumo/) installed with `SUMO\_HOME` set, Python 3.10+



```bash

pip install -r requirements.txt

python app.py

```



Then open `http://127.0.0.1:5000` in your browser.



To regenerate the full pipeline from scratch (not required to just run the app — all outputs are already included):



```bash

python run\_overnight.py              # full-city baseline simulation

python build\_node\_features.py

python build\_baseline\_conflicts.py

python build\_lookup.py

python build\_node\_baseline.py

python regenerate\_full\_batch.py      # intervention scenario testing

python build\_training\_dataset.py

python train\_model.py

```



---



## Methodology Notes & Known Limitations



- **Small sample size**: intervention testing was run on ~35–45 (junction × intervention) combinations due to simulation time constraints. This is enough for a proof-of-concept but not a production-grade statistical sample — the model's confidence should be read accordingly.

- **Ground-truth vs. model estimates**: for junctions we've directly simulated multiple times, predictions use the real measured average, not the ML model — the app labels which type of result you're seeing.

- **Simulated conflicts, not real accidents**: due to sparse, inconsistently geo-tagged real accident data in India, this project uses SUMO-simulated near-miss "conflicts" (Surrogate Safety Measures) as a proxy signal, consistent with FHWA's SSAM methodology.

- **Two junctions with known geometry limitations**: a small number of complex "cluster" junctions in the imported network have internal geometry SUMO's SSM device can't fully resolve for all conflicting movement pairs — conflict counts at these are likely a slight undercount.

- **Single-city, single-area scope**: current results cover Central Kolkata only, as a feasibility demonstration.



---



## Acknowledgements



- OpenStreetMap contributors, for the road network data

- Eclipse SUMO team, for the simulation platform

- FHWA's Surrogate Safety Assessment Model (SSAM), for the conflict-based safety methodology this project builds on
