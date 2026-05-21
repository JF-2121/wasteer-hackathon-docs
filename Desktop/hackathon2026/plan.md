### ThoughtProcess: Findings

The shipment data must be cleaned by calculating net weight as (entry_weight - exit_weight) and filtering out records with zero mass or non-waste categories like emergency vehicles.
LiDAR data serves as the volume reference, while shipment data provides the mass input.
Bulk density per waste code can be estimated by correlating the mass inflow from trucks with the volume change observed in LiDAR scans.
The bunker optimization relies on keeping the average calorific value at 10 MJ/kg by selecting appropriate truck loads.

MVP Implementation Plan

**1. Data Preparation**
Filter the shipment JSON for records where entry_weight exceeds exit_weight and waste_code is present.
Exclude non-waste vehicles to isolate true bunker mass flow.

**2. Volumetric Representation**
Calculate cumulative mass for each waste code at every LiDAR timestamp.

Perform linear regression on cumulative mass versus total volume to estimate the density (kg/m3) for each waste code.

**3. Optimization Logic**
Calculate the running average calorific value (MJ/kg) as new shipments are added to the bunker.
If the current average deviates from 10 MJ/kg, identify the specific waste code required to restore stability.
Verify that the suggested mass addition stays within the remaining capacity identified by the LiDAR volume data.

**4. Visualization**
Create a dual-axis chart showing the bunker volume (m3) and the rolling average calorific value (MJ/kg) to prove the system stays within the operational target of 10 MJ/kg.

**5. Delivery**
Present the estimated densities and the optimization logic in a script that processes the shipment JSON and validates the results against the LiDAR-derived volumes.